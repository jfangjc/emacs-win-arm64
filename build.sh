#!/usr/bin/env bash
set -Eeuo pipefail
trap 'status=$?; printf "%s:%s: command failed (%s): %s\n" "${BASH_SOURCE[0]}" "$LINENO" "$status" "$BASH_COMMAND" >&2' ERR

recipe=$(pwd)
source_dir="$recipe/emacs-${EMACS_VERSION}"
install_dir="$recipe/bin"
prefix=${MINGW_PREFIX:?}
[[ $prefix == /clangarm64 ]] || { echo 'Run in CLANGARM64' >&2; exit 1; }
if ! cmp -s "$recipe/COPYING" "$source_dir/COPYING"; then
    echo 'Review the changed upstream Emacs COPYING before updating the repository license copy.' >&2
    exit 1
fi

cd "$source_dir"
cp "$recipe/emacs.manifest" ./nt
if ! patch --batch --forward --fuzz=0 --quiet -Np1 -i "$recipe/emacs.patch"; then
    echo "Review emacs.patch against the Emacs $EMACS_VERSION source before building this version." >&2
    exit 1
fi

./autogen.sh

export CC=clang
export LDFLAGS="${LDFLAGS:-} -lpthread"

./configure \
    --quiet \
    --prefix="$install_dir" \
    --host="${MINGW_CHOST}" \
    --build="${MINGW_CHOST}" \
    --with-modules \
    --without-dbus \
    --without-compress-install \
    --without-native-compilation \
    --with-tree-sitter \
    --with-gnutls \
    --with-xml2 \
    --with-sqlite3 \
    --without-pop

make --silent actual-all -j "$(nproc)"
make --silent install

echo 'Collecting dependency packages, notices, and sources'
dll_output=$(python "$recipe/scripts/collect-dlls.py" \
    --prefix "$(cygpath -am "$prefix")" --install "$(cygpath -am "$install_dir")")
# Native Windows Python emits CRLF; mapfile removes LF but retains CR.
dll_output=${dll_output//$'\r'/}
mapfile -t dlls <<< "$dll_output"
printf 'Bundling %s runtime DLLs\n' "${#dlls[@]}"
bash "$recipe/scripts/bundle-dependencies.sh" "${dlls[@]}"
if [[ ! -f $install_dir/bin/libwinpthread-1.dll ]]; then
    echo 'Missing bundled runtime: libwinpthread-1.dll' >&2
    exit 1
fi

# Exclude MSYS2 from PATH so installed DLLs cannot hide an incomplete bundle.
windows=$(cygpath -u "${SYSTEMROOT:-${SystemRoot:?}}")
PATH="$install_dir/bin:$windows/System32:$windows" \
    "$install_dir/bin/emacs.exe" --batch -Q --eval "$(cat <<'ELISP'
(progn
  (unless (and (eq system-type 'windows-nt)
               (string-match-p "\\`aarch64-" system-configuration))
    (error "Expected a native Windows ARM64 build: %s" system-configuration))
  (let* ((expected (getenv "EMACS_VERSION"))
         (numeric (replace-regexp-in-string "-rc[0-9]+\\'" "" expected)))
    (unless (member emacs-version (list expected numeric))
      (error "Emacs version mismatch: expected %s, got %s" expected emacs-version)))
  (dolist (check '(treesit-available-p gnutls-available-p libxml-available-p sqlite-available-p))
    (unless (and (fboundp check) (funcall check))
      (error "Bundled runtime unavailable: %s. Review dependency DLL names and APIs" check)))
  (require 'image)
  (dolist (type '(xpm gif jpeg png tiff svg webp))
    (unless (image-type-available-p type)
      (error "Bundled image support unavailable: %s. Review dependency DLL names and APIs" type)))
  (message "Windows ARM64 runtime checks passed for Emacs %s" emacs-version))
ELISP
)"
