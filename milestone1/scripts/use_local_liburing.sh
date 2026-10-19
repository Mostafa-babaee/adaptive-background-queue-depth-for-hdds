#!/usr/bin/env bash
# Source this in a new Babbage shell; it does not install or change any files.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf 'Use: source scripts/use_local_liburing.sh\n' >&2
    exit 2
fi
_m1_lib_prefix="$HOME/.local/m1-liburing-2.5"
if [[ ! -f "$_m1_lib_prefix/lib/pkgconfig/liburing.pc" ]]; then
    printf 'Local liburing metadata not found under %s\n' "$_m1_lib_prefix" >&2
    unset _m1_lib_prefix
    return 1
fi
export PKG_CONFIG_PATH="$_m1_lib_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$_m1_lib_prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset _m1_lib_prefix
pkg-config --modversion liburing
