#!/usr/bin/env bash
# build_liburing.sh - builds liburing into $HOME/local without root.
# Only needed if check_tools.sh says liburing is missing.
set -e
PREFIX="$HOME/local"
SRC="$HOME/src/liburing"
mkdir -p "$HOME/src"
[ -d "$SRC" ] || git clone --depth 1 https://github.com/axboe/liburing "$SRC"
cd "$SRC"
./configure --prefix="$PREFIX"
make -j"$(nproc)"
make install
echo
echo "liburing installed in $PREFIX"
echo "The Makefile picks it up automatically. To run binaries:"
echo "  export LD_LIBRARY_PATH=$PREFIX/lib:\$LD_LIBRARY_PATH"
