#!/usr/bin/env python3
"""Publish a portable ZIP, installer and source archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
from urllib.parse import urlencode

sys.dont_write_bytecode = True
BUILD_NAME = r"emacs-[0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+)?-(?:stable|pretest)-windows-arm64"


class BuildArtifactsUnavailable(ValueError):
    pass


def gh(*args):
    return subprocess.run(["gh", *args], check=True, text=True, capture_output=True).stdout


def release(tag):
    result = subprocess.run(["gh", "api", f"repos/{os.environ['GH_REPO']}/releases/tags/{tag}"],
                            text=True, capture_output=True)
    if result.returncode:
        if "(HTTP 404)" in result.stderr:
            return None
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def latest_build():
    repository = os.environ["GH_REPO"]
    query = urlencode({"branch": os.environ["DEFAULT_BRANCH"], "status": "success", "per_page": 100})
    pages = json.loads(gh("api", "--paginate", "--slurp",
                          f"repos/{repository}/actions/workflows/build.yml/runs?{query}"))
    runs = [run for page in pages for run in page["workflow_runs"]]
    for run in sorted(runs, key=lambda item: item["run_number"], reverse=True):
        if run.get("event") not in {"schedule", "workflow_dispatch"}:
            continue
        try:
            return select_build(str(run["id"]))
        except BuildArtifactsUnavailable:
            continue
    raise ValueError("No successful default-branch Build has complete, unexpired artifacts. Run Build first.")


def select_build(run_id):
    """Select complete artifacts from a successful default-branch Build run."""
    run_id = run_id.strip()
    if not run_id:
        if os.environ.get("GITHUB_EVENT_NAME") == "workflow_run":
            raise ValueError("Automatic releases require the triggering Build run ID")
        return latest_build()
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("Enter the numeric Build run ID from its Actions URL")
    repository = os.environ["GH_REPO"]
    run = json.loads(gh("api", f"repos/{repository}/actions/runs/{run_id}"))
    if (run.get("path", "").split("@", 1)[0] != ".github/workflows/build.yml" or
            (run.get("head_repository") or {}).get("full_name") != repository or
            run.get("head_branch") != os.environ["DEFAULT_BRANCH"] or
            run.get("event") not in {"schedule", "workflow_dispatch"}):
        raise ValueError("Select a Build run from this repository's default branch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("The selected Build run must have completed successfully")
    commit = run.get("head_sha", "")
    if len(commit) not in (40, 64) or not re.fullmatch(r"[0-9a-f]+", commit):
        raise ValueError("The selected Build run has no valid source commit")
    automatic = os.environ.get("GITHUB_EVENT_NAME") == "workflow_run"
    if automatic and run["event"] != "schedule":
        raise ValueError("Only scheduled builds publish automatically")
    pages = json.loads(gh("api", "--paginate", "--slurp",
                          f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"))
    artifacts = {}
    for page in pages:
        for artifact in page["artifacts"]:
            name = artifact["name"]
            if name in artifacts:
                raise ValueError(f"Duplicate build artifact: {name}")
            artifacts[name] = artifact
    names = {name for name in artifacts if re.fullmatch(BUILD_NAME, name)}
    if not names and (not automatic or artifacts):
        raise BuildArtifactsUnavailable("No application artifacts remain for this Build run; run Build again")
    for name in names:
        if artifacts[name].get("expired", False):
            raise BuildArtifactsUnavailable(f"Expired artifact: {name}. Run Build again.")
    return {"run_id": run_id, "commit": commit, "publish": str(bool(names)).lower()}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def upstream_source(path, version, channel):
    """Read the original GNU source URL and checksum recorded by the build."""
    base = ("https://ftp.gnu.org/gnu/emacs" if channel == "stable" else
            "https://alpha.gnu.org/gnu/emacs/pretest")
    expected_url = f"{base}/emacs-{version}.tar.xz"
    with tarfile.open(path, "r|xz") as archive:
        first = archive.next()
        if first is None or first.name != f"emacs-{version}" or not first.isdir():
            raise ValueError("Source archive does not match the Emacs version")
        for member in archive:
            if member.name != f"emacs-{version}/build-recipe/build-info.txt":
                continue
            if not member.isfile() or member.size > 1024**2:
                raise ValueError("Invalid source build information")
            text = archive.extractfile(member).read().decode("utf-8")
            urls = re.findall(r"^Source: (.+)$", text, re.M)
            checksums = re.findall(r"^SHA-256: ([0-9a-f]{64})$", text, re.M)
            if (not text.startswith(f"Emacs {version}, {channel}, Windows ARM64\n") or
                    urls != [expected_url] or len(checksums) != 1):
                raise ValueError("GNU source metadata does not match the release")
            return urls[0], checksums[0]
    raise ValueError("Missing GNU source URL and checksum in the source archive")


def check_tag(tag, commit):
    repository = os.environ["GH_REPO"]
    refs = json.loads(gh("api", f"repos/{repository}/git/matching-refs/tags/{tag}"))
    for ref in refs:
        if ref["ref"] != f"refs/tags/{tag}":
            continue
        target = ref["object"]
        while target["type"] == "tag":
            target = json.loads(gh("api", f"repos/{repository}/git/tags/{target['sha']}"))["object"]
        if target["type"] != "commit" or target["sha"] != commit:
            raise ValueError(f"Tag {tag} points to a different commit than the selected Build")


def publish(artifacts):
    commit = os.environ.get("RELEASE_COMMIT") or os.environ["GITHUB_SHA"]
    artifacts = Path(artifacts)
    bundles = sorted(artifacts.glob("emacs-*-windows-arm64"))
    # download-artifact v7 extracts a single match directly into its output path.
    if (artifacts / "SHA256SUMS").is_file():
        bundles.insert(0, artifacts)
    if not bundles:
        raise ValueError("No build artifacts found. Download a complete Build run first.")
    for bundle in bundles:
        sums = bundle / "SHA256SUMS"
        expected = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not re.fullmatch(r"[0-9a-f]{64} [ *].+", line):
                raise ValueError("Invalid release checksum manifest")
            value, filename = line[:64], line[66:].removeprefix("./")
            if filename in expected or any(c in filename for c in "\\/:") or filename in {"", ".", ".."}:
                raise ValueError("Invalid release checksum manifest")
            expected[filename] = value
        portables = [filename for filename in expected if filename.endswith(".zip")]
        if len(portables) != 1:
            raise ValueError("Release checksum inventory must contain one portable ZIP")
        name = Path(portables[0]).stem
        match = re.fullmatch(r"emacs-([0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+)?)-(stable|pretest)-windows-arm64", name)
        if not match:
            raise ValueError(f"Invalid release name: {name}")
        version, channel = match.groups()
        tag = f"v{version}" + ("-pretest" if channel == "pretest" else "")
        files = [bundle / f"{name}.zip", bundle / f"{name}-setup.exe",
                 bundle / f"{name}-source.tar.xz"]
        if set(expected) != {p.name for p in files}:
            raise ValueError("Release checksum inventory is incomplete")
        for path in files:
            if path.stat().st_size >= 2 * 1024**3:
                raise ValueError(f"Release asset must be below GitHub's 2 GiB limit: {path.name}")
            if digest(path) != expected[path.name]:
                raise ValueError(f"Release checksum mismatch: {path}")
        source_url, source_sha256 = upstream_source(files[2], version, channel)
        check_tag(tag, commit)
        old = release(tag)
        if old and old["draft"]:
            raise ValueError(f"Review or remove the existing draft before retrying: {tag}")
        public_names = ("emacs-arm64.zip", "emacs-arm64-setup.exe", "emacs-arm64-source.tar.xz")
        if old:
            assets = {asset["name"]: asset for asset in old["assets"]}
            if (set(assets) != set(public_names) or any(
                    assets[name].get("digest") != "sha256:" + digest(path) or
                    assets[name]["size"] != path.stat().st_size
                    for name, path in zip(public_names, files))):
                raise ValueError(f"{tag} already exists with different or unverifiable assets. "
                                 "Use a new revision tag for a dependency rebuild; existing releases are not overwritten.")
            print(f"{tag} already contains these exact artifacts")
            continue
        # Keep the release in a draft until all three assets have uploaded.
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            public_files = [work / name for name in public_names]
            for original, destination in zip(files, public_files):
                shutil.copyfile(original, destination)
            checksums = "".join(f"{digest(path)}  {path.name}\n" for path in public_files)
            notes = work / "notes.md"
            notes.write_text(
                "Unofficial build for Windows 11 ARM64.\n\n"
                f"GNU Emacs source: [emacs-{version}.tar.xz]({source_url}).\n\n"
                f"GNU source SHA-256: `{source_sha256}`.\n\n"
                "The source archive contains dependency sources, the ARM64 patch and the build recipe. "
                "See build-recipe/README.md inside it to reconstruct the modified Emacs source.\n\n"
                f"SHA-256:\n```text\n{checksums}```\n", encoding="utf-8")
            gh("release", "create", tag, "--target", commit, "--draft", "--latest=false",
               "--title", f"Emacs {version}", "--notes-file", str(notes),
               *(["--prerelease"] if channel == "pretest" else []), *map(str, public_files))
        gh("release", "edit", tag, "--draft=false", "--latest" if channel == "stable" else "--latest=false")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="?", default="artifacts")
    parser.add_argument("--build-run", help="Select a successful Build run; an empty value selects the latest")
    args = parser.parse_args()
    if args.build_run is not None:
        selected = select_build(args.build_run)
        print(f"Selected Build run {selected['run_id']} at {selected['commit']}")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("".join(f"{key}={value}\n" for key, value in selected.items()))
    else:
        publish(args.artifacts)
