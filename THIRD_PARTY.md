# Third-party software

## Emacs

Upstream Emacs code is copyright the Free Software Foundation, Inc.
The modified program uses GPL version 3 or later. See `COPYING`.
The GNU Emacs Manual uses GFDL version 1.3 or later, with its stated invariant
sections and cover texts. Preserve upstream notices and manual licenses.

Modified by Jason Fang, first recorded on 2026-10-15, for Windows ARM64 and
tree-sitter DLL lookup. See `emacs.patch` and `emacs.manifest`.
Original contributions use MIT. See `LICENSE`.

## Libraries

This software is based in part on the work of the Independent JPEG Group.

For dependencies offering GPL version 2 or later, these builds use version 3.
Dependency notices and package/DLL inventories are in `licenses/`.
The Inno Setup engine's license and version are in `licenses/inno-setup/`.

## Source

Each release includes dependency sources, the ARM64 patch and the build recipe.
The original GNU Emacs source URL and hash are recorded in `build-recipe/README.md`
and linked in the release notes. Follow that README to reconstruct the
modified source. Keep both the archive and the linked source available while
distributing the binaries.

Dependency DLLs come from unmodified MSYS2 packages. Following the official
Windows build's packaging approach, `ntldd` identifies runtime DLL dependencies.
Only the packages supplying those DLLs are collected. Matching MSYS2 source
package archives are distributed unchanged under `dependency-sources/`.
Their package base and version are checked against installed packages, and their
SHA-256 hashes are recorded.
Installed package license and notice files are copied into `licenses/`.

To rebuild a dependency, extract its MSYS2 source package archive and follow its
`PKGBUILD` using MSYS2 CLANGARM64. Upstream sources and build dependencies may
need to be downloaded as specified by that recipe.
See `build-recipe/README.md` in the dependency source archive.
