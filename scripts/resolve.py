#!/usr/bin/env python3
"""Resolve GNU Emacs versions and emit the build matrix."""
import json
import os
import re
import subprocess
import sys

BASES = {
    "stable": "https://ftp.gnu.org/gnu/emacs",
    "pretest": "https://alpha.gnu.org/gnu/emacs/pretest",
}


def version_key(value):
    numeric, separator, rc = value.partition("-rc")
    parts = list(map(int, numeric.split(".")))
    while parts and parts[-1] == 0:
        parts.pop()
    return parts, 0 if separator else 1, int(rc or 0)


def latest_version(channel):
    listing = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--retry", "3",
         BASES[channel] + "/"], check=True, capture_output=True, text=True).stdout
    versions = re.findall(r'href="emacs-([0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+)?)\.tar\.xz"', listing)
    if channel == "stable":
        versions = [version for version in versions
                    if re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", version)]
    return max(versions, key=version_key, default=None)


def resolve(scheduled, channel):
    if not scheduled and channel not in BASES:
        raise ValueError("EMACS_CHANNEL must be stable or pretest")
    tags = set()
    if scheduled:
        tags = set(subprocess.run(
            ["gh", "api", "--paginate",
             f"repos/{os.environ['GITHUB_REPOSITORY']}/releases?per_page=100",
             "--jq", ".[].tag_name"], check=True, capture_output=True, text=True).stdout.splitlines())
    builds = []
    stable_version = None
    for channel in BASES if scheduled else [channel]:
        version = latest_version(channel)
        if version is None:
            if channel == "stable" or not scheduled:
                raise ValueError(f"No {channel} source archive at {BASES[channel]}/")
            print("No pretest source archive; skipping pretest.", file=sys.stderr)
            continue
        if channel == "stable":
            stable_version = version
        elif scheduled and version_key(version) <= version_key(stable_version):
            print(f"Skipping pretest {version}; stable {stable_version} is already available", file=sys.stderr)
            continue
        tag = f"v{version}" + ("-pretest" if channel == "pretest" else "")
        if tag in tags:
            print(f"Skipping {channel} {version}; release {tag} already exists.", file=sys.stderr)
            continue
        source_url = f"{BASES[channel]}/emacs-{version}.tar.xz"
        print(f"Building {channel} {version} from {source_url}", file=sys.stderr)
        builds.append(dict(channel=channel, version=version, source_url=source_url,
                           artifact_name=f"emacs-{version}-{channel}-windows-arm64"))
    return builds


if __name__ == "__main__":
    builds = resolve(os.environ.get("GITHUB_EVENT_NAME") == "schedule",
                     os.environ.get("EMACS_CHANNEL") or "stable")
    output = ("matrix=" + json.dumps({"include": builds}) + "\n"
              "build_needed=" + str(bool(builds)).lower() + "\n")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(output)
    else:
        print(output, end="")
