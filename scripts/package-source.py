#!/usr/bin/env python3
"""Package dependency sources and the recipe for the linked GNU Emacs source."""
import argparse
import hashlib
from pathlib import Path
import re
import tarfile


def verify_sources(source):
    """Verify the MSYS2 source archives before packaging them unchanged."""
    source = Path(source)
    sums = source / "dependency-sources/SHA256SUMS"
    sizes = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not re.fullmatch(r"[0-9a-f]{64} [ *].+", line):
            raise ValueError("Invalid dependency checksum manifest")
        filename = line[66:].removeprefix("./")
        if Path(filename).name != filename or any(c in filename for c in "\\/:"):
            raise ValueError(f"Invalid dependency archive name: {filename}")
        with (sums.parent / filename).open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != line[:64]:
            raise ValueError(f"Dependency source checksum mismatch: {filename}")
        sizes.append(((sums.parent / filename).stat().st_size, filename))
    print(f"Dependency sources: {len(sizes)} archives, {sum(size for size, _ in sizes) / 1024**2:.1f} MiB")
    print("Largest dependency source archives:")
    for size, filename in sorted(sizes, reverse=True)[:10]:
        print(f"  {size / 1024**2:8.1f} MiB  {filename}")


def archive_members(source):
    source = Path(source)
    yield source
    for name in ("COPYING", "THIRD_PARTY.md", "build-recipe", "dependency-sources"):
        root = source / name
        if not root.exists():
            raise ValueError(f"Missing source distribution input: {name}")
        yield root
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root)
                if ".git" in relative.parts or "__pycache__" in relative.parts:
                    continue
                yield path


def write_archive(source, output):
    with tarfile.open(output, "w:xz", preset=6) as archive:
        for path in archive_members(source):
            relative = path.relative_to(source).as_posix()
            name = source.name if path == source else source.name + "/" + relative
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            if info.isfile():
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
            else:
                archive.addfile(info)


def package(source, output, name):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    verify_sources(source)
    archive = output / f"{name}-source.tar.xz"
    write_archive(source, archive)
    print(f"Source archive: {archive.stat().st_size:,} bytes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    package(args.source, args.output, args.name)
