#!/usr/bin/env bash
set -euo pipefail

recipe=$(cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$recipe/emacs-${EMACS_VERSION}"
dist="$recipe/dist"
mkdir "$source_dir"
mkdir -p "$dist"
archive="$recipe/emacs-${EMACS_VERSION}.tar.xz"
curl_args=(--fail --silent --location --show-error --retry 3)
curl "${curl_args[@]}" "$EMACS_SOURCE_URL" -o "$archive"
curl "${curl_args[@]}" "$EMACS_SOURCE_URL.sig" -o "$archive.sig"
curl "${curl_args[@]}" https://ftp.gnu.org/gnu/gnu-keyring.gpg -o "$recipe/gnu-keyring.gpg"
mkdir "$RUNNER_TEMP/emacs-gnupg"
chmod 700 "$RUNNER_TEMP/emacs-gnupg"
gpgv --quiet --homedir "$RUNNER_TEMP/emacs-gnupg" --keyring "$recipe/gnu-keyring.gpg" "$archive.sig" "$archive"
tar -xJf "$archive" -C "$source_dir" --strip-components=1
