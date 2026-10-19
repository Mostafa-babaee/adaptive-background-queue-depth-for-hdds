#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
mkdir -p "$root/build"
compiler=${CC:-cc}
if ! command -v "$compiler" >/dev/null 2>&1; then
    printf 'BLOCKED: compiler %s not found.\n' "$compiler" >&2
    exit 77
fi
flags=(-luring)
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists liburing; then
    read -r -a flags <<< "$(pkg-config --cflags --libs liburing)"
fi
printf 'Building with %s\n' "$compiler"
# liburing 2.5 headers use extensions diagnosed by -Wpedantic.
# Keep application warnings enabled without making those header extensions fatal.
if ! "$compiler" -std=c11 -O2 -g -Wall -Wextra -Werror \
    "$root/src/smoke_read.c" -o "$root/build/smoke_read" "${flags[@]}"; then
    printf 'Build did not complete. Check compiler diagnostics and liburing development files.\n' >&2
    exit 77
fi
printf 'Built: %s/build/smoke_read\n' "$root"
