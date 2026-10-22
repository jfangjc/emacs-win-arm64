#!/usr/bin/env python3
"""Collect Emacs runtime DLLs using the official Windows build's ntldd method."""
import argparse
import os
from pathlib import Path
import re
import subprocess


def run(command, env):
    return subprocess.run(command, check=True, capture_output=True, text=True,
                          encoding="utf-8", env=env).stdout


def collect(prefix, install):
    prefix, install = Path(prefix).resolve(), Path(install).resolve()
    directory = prefix / "bin"
    available = {path.name.lower(): path for path in directory.iterdir()
                 if path.is_file() and path.suffix.lower() == ".dll"}
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join((str(install / "bin"), str(directory), env.get("PATH", "")))
    # These libraries are loaded with LoadLibrary, so PE imports alone miss them.
    # Use the installed Emacs's version-specific names instead of another list.
    names = run([str(install / "bin/emacs.exe"), "--batch", "-Q", "--eval", r'''
(progn
  (require 'term/w32-nt)
  (dolist (entry dynamic-library-alist)
    ;; This build disables native compilation, as does its dependency bundle.
    (unless (eq (car entry) 'gccjit)
      (dolist (name (cdr entry))
        (when (stringp name) (princ name) (terpri))))))
'''], env)
    selected = {name.strip().lower() for name in names.splitlines()
                if name.strip().lower() in available}
    if not selected:
        raise ValueError("No installed DLLs match Emacs's dynamic-library-alist")
    binaries = [available[name] for name in sorted(selected)]
    binaries.extend(sorted(path for path in (install / "bin").iterdir()
                           if path.is_file() and path.suffix.lower() in {".exe", ".dll"}))
    scanned = set()
    # Walk MSYS2 imports ourselves. ntldd --recursive also descends into Windows
    # system DLLs, where optional/internal imports can be reported as missing.
    while binaries:
        binary = binaries.pop()
        if binary in scanned:
            continue
        scanned.add(binary)
        output = run([str(directory / "ntldd.exe"), "--search-dir",
                      str(directory), str(binary)], env)
        for line in output.splitlines():
            match = re.fullmatch(r"\s*(\S+\.dll)\s+=>\s+(.+?)\s*", line, re.I)
            if not match:
                continue
            name, resolved = match.groups()
            if resolved.lower() == "not found":
                if name.lower().startswith(("api-", "ext-")):
                    continue  # API-set contracts need not exist as files on disk.
                raise ValueError(f"Unresolved runtime dependency of {binary.name}: {name}")
            resolved = re.sub(r"\s+\(0x[0-9a-f]+\)$", "", resolved, flags=re.I)
            dependency = Path(resolved).resolve()
            if dependency.parent != directory:
                continue  # Windows system DLLs are supplied by Windows.
            key = dependency.name.lower()
            if key not in available:
                raise ValueError(f"Runtime DLL is missing from the MSYS2 prefix: {dependency}")
            selected.add(key)
            binaries.append(available[key])
    return [available[name].name for name in sorted(selected)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--install", type=Path, required=True)
    args = parser.parse_args()
    print("\n".join(collect(args.prefix, args.install)))
