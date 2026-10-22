#!/usr/bin/env bash
set -Eeuo pipefail
trap 'status=$?; printf "%s:%s: command failed (%s): %s\n" "${BASH_SOURCE[0]}" "$LINENO" "$status" "$BASH_COMMAND" >&2' ERR
export LC_ALL=C

recipe=$(cd -- "$(dirname -- "$0")/.." && pwd)
prefix=${MINGW_PREFIX:?}
install_dir="$recipe/bin"
sources="$recipe/emacs-${EMACS_VERSION}/dependency-sources"
licenses="$install_dir/licenses"
database=$(pacman-conf DBPath)
download=''
trap 'if [[ -n $download ]]; then rm -f -- "$download"; fi' EXIT
mkdir -p "$licenses" "$sources"
printf 'package\tversion\tbase\tsource\n' > "$licenses/packages.tsv"
printf 'dll\tpackage\tversion\n' > "$licenses/dlls.tsv"

# Installed database entries retain the source base for split packages.
field() {
    awk -v key="%$2%" '$0 == key { getline; print; exit }' "$1"
}

source_field() {
    awk -F ' = ' -v key="$1" '$1 ~ "^[ \t]*" key "$" { print $2; exit }'
}

verify_source() {
    local info source_base source_version source_release source_epoch
    # Reading the member also checks archive integrity. Do not execute PKGBUILD.
    info=$(tar -xOf "$1" "$base/.SRCINFO")
    source_base=$(source_field pkgbase <<< "$info")
    source_version=$(source_field pkgver <<< "$info")
    source_release=$(source_field pkgrel <<< "$info")
    source_epoch=$(source_field epoch <<< "$info")
    source_version="$source_version-$source_release"
    if [[ -n $source_epoch && $source_epoch != 0 ]]; then
        source_version="$source_epoch~$source_version"
    fi
    if [[ $source_base != "$base" || $source_version != "${version//:/~}" ]]; then
        echo "Source metadata does not match installed $package $version" >&2
        return 1
    fi
}

declare -A bundled=()
for dll in "$@"; do
    if [[ $dll != *.dll || $dll == */* || $dll == *\\* || ! -f $prefix/bin/$dll ]]; then
        printf 'Invalid runtime DLL: %q\n' "$dll" >&2
        exit 1
    fi
    package=$(pacman -Qoq "$prefix/bin/$dll")
    package_info=$(pacman -Q "$package")
    package_info=${package_info//$'\r'/}
    read -r installed version <<< "$package_info"
    if [[ -z $installed || -z $version ]]; then
        printf 'Unexpected package query for %s: %s\n' "$package" "$package_info" >&2
        exit 1
    fi
    package=$installed
    cp -- "$prefix/bin/$dll" "$install_dir/bin/"
    printf '%s\t%s\t%s\n' "$dll" "$package" "$version" >> "$licenses/dlls.tsv"
    [[ -z ${bundled[$package]+present} ]] || continue
    bundled[$package]=1
    printf 'Collecting notices and source for %s\n' "$package"
    desc="$database/local/$package-$version/desc"
    base=$(field "$desc" BASE)
    [[ -n $base ]] || { echo "Missing source package base for $package" >&2; exit 1; }
    # MSYS2 represents epochs with '~', including in source archive names.
    source_name="$base-${version//:/~}.src.tar.zst"
    url="https://repo.msys2.org/mingw/sources/$source_name"
    printf '%s\t%s\t%s\t%s\n' "$package" "$version" "$base" "$url" >> "$licenses/packages.tsv"
    mkdir -p "$licenses/$package"
    pacman -Qi "$package" > "$licenses/$package/package-info.txt"
    files=$(pacman -Ql "$package")
    while read -r owner file; do
        [[ $owner == "$package" && -f $file ]] || continue
        case "$file" in
            "$prefix/share/licenses/"*)
                [[ -s $file ]] || continue
                relative=${file#"$prefix/share/licenses/"}
                mkdir -p "$licenses/$package/$(dirname -- "$relative")"
                cp -- "$file" "$licenses/$package/$relative"
                ;;
            "$prefix/share/doc/"*)
                case "${file##*/}" in
                    COPYING*|LICENSE*|NOTICE*|AUTHORS*|README.ijg*|[Cc]opyright*)
                        [[ -s $file ]] || continue
                        relative=${file#"$prefix/share/doc/"}
                        mkdir -p "$licenses/$package/docs/$(dirname -- "$relative")"
                        cp -- "$file" "$licenses/$package/docs/$relative"
                        ;;
                esac
                ;;
        esac
    done <<< "$files"
    if [[ ! -f $sources/$source_name ]]; then
        download="$sources/$source_name.part"
        curl --fail --silent --show-error --location --retry 3 "$url" -o "$download"
        verify_source "$download"
        mv -- "$download" "$sources/$source_name"
        download=''
    else
        verify_source "$sources/$source_name"
    fi
    # MSYS2 giflib 6.1.3 omits its upstream notice from the binary package.
    # Recover it from the matching source archive without a separate download.
    if [[ $base == mingw-w64-giflib && ${version%-*} == 6.1.3 ]]; then
        download=$(mktemp)
        tar -xOf "$sources/$source_name" "$base/giflib-6.1.3.tar.gz" > "$download"
        tar -xzOf "$download" giflib-6.1.3/COPYING > "$licenses/$package/COPYING"
        tar -xzOf "$download" --wildcards 'giflib-6.1.3/*.c' 'giflib-6.1.3/*.h' |
            awk 'tolower($0) ~ /copyright/ && !seen[$0]++' > "$licenses/$package/COPYRIGHT"
        test -s "$licenses/$package/COPYING"
        test -s "$licenses/$package/COPYRIGHT"
        rm -f -- "$download"
        download=''
    fi
done

cp "$licenses/packages.tsv" "$sources/"
cp "$licenses/dlls.tsv" "$sources/"
(
    cd "$sources"
    shopt -s nullglob
    archives=(./*.src.tar.zst)
    : > SHA256SUMS
    if (( ${#archives[@]} )); then
        sha256sum "${archives[@]}" > SHA256SUMS
    fi
)
