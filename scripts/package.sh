#!/usr/bin/env bash
set -euo pipefail

recipe=$(cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$recipe/emacs-${EMACS_VERSION}"
dist="$recipe/dist"
name="emacs-${EMACS_VERSION}-${EMACS_CHANNEL}-windows-arm64"
archive="$recipe/emacs-${EMACS_VERSION}.tar.xz"
source_sha256=$(sha256sum "$archive" | cut -d ' ' -f 1)

versioned="$recipe/bin/bin/emacs-${EMACS_VERSION}.exe"
if [[ -f $versioned ]] && cmp -s "$recipe/bin/bin/emacs.exe" "$versioned"; then
  rm -- "$versioned"
fi

cp "$recipe/README.md" "$recipe/LICENSE" "$recipe/THIRD_PARTY.md" "$recipe/bin/"
cp "$source_dir/COPYING" "$recipe/bin/COPYING"
cp "$recipe/THIRD_PARTY.md" "$source_dir/"

mkdir "$source_dir/build-recipe"
cp "$recipe/build.sh" "$recipe/emacs.patch" "$recipe/emacs.manifest" \
  "$recipe/README.md" "$recipe/LICENSE" "$recipe/COPYING" \
  "$recipe/THIRD_PARTY.md" "$source_dir/build-recipe/"
cp -r "$recipe/scripts" "$recipe/.github" "$source_dir/build-recipe/"
cat > "$source_dir/build-recipe/build-info.txt" <<EOF
Emacs $EMACS_VERSION, $EMACS_CHANNEL, Windows ARM64
Source: $EMACS_SOURCE_URL
SHA-256: $source_sha256
Verification: gnu-signature
Recipe commit: $GITHUB_SHA
Run: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID
EOF
pacman -Q >> "$source_dir/build-recipe/build-info.txt"
cp -r "$recipe/bin/licenses" "$source_dir/build-recipe/"
cat >> "$source_dir/build-recipe/README.md" <<EOF

## Reconstructing Emacs $EMACS_VERSION for Windows ARM64

This archive contains MSYS2 dependency sources, license notices, and the build
recipe, including our ARM64 patch. Download the original GNU Emacs source from:

$EMACS_SOURCE_URL

SHA-256: $source_sha256
GNU signature: $EMACS_SOURCE_URL.sig

To reconstruct the modified Emacs source, extract this archive and the GNU
archive into the same parent directory. Both use emacs-$EMACS_VERSION/ as their
root directory. Then run from that parent directory:

    cd emacs-$EMACS_VERSION
    cp build-recipe/emacs.manifest nt/emacs.manifest
    patch -p1 < build-recipe/emacs.patch

The build recipe and original package versions are in build-recipe/.
The matching CI workflow is build-recipe/.github/workflows/build.yml.
Keep this archive and the linked GNU source available while distributing
the binaries.
EOF
cd "$recipe"
temporary=$(mktemp -d "$dist/.package-XXXXXX")
trap 'rm -rf -- "$temporary"' EXIT
zip -qr "$temporary/$name.zip" bin
python "$recipe/scripts/package-source.py" "$source_dir" "$temporary" --name "$name"
mv -- "$temporary/$name.zip" "$temporary/$name-source.tar.xz" "$dist/"
