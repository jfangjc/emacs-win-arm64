#!/usr/bin/env bash
set -euo pipefail
[[ ${MINGW_PREFIX:?} == /clangarm64 ]] || { echo 'Run in CLANGARM64' >&2; exit 1; }

# Runtime dependencies for Emacs.
libraries=(
    zlib xpm-nox freetype harfbuzz gnutls libtree-sitter libxml2
    libwinpthread gmp librsvg libwebp sqlite3 lcms2 giflib libjpeg-turbo libpng libtiff
)
packages=("${libraries[@]/#/mingw-w64-clang-aarch64-}")

for attempt in 1 2 3; do
    if pacman --sync --needed --noconfirm --noprogressbar \
        mingw-w64-clang-aarch64-texinfo mingw-w64-clang-aarch64-ntldd "${packages[@]}"; then
        exit 0
    else
        status=$?
    fi
    if ((attempt < 3)); then
        delay=$((attempt * 10))
        printf 'pacman failed (%s); retrying in %s seconds (%s/3).\n' \
            "$status" "$delay" "$((attempt + 1))" >&2
        sleep "$delay"
    fi
done
exit "$status"
