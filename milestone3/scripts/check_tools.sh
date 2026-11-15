#!/usr/bin/env bash
# check_tools.sh - Milestone 1, Mostafa Babaei.
# Checks that everything the project needs is on the server and appends the
# result to results/tools_check.md. Prints what is missing and how to fix it.
set -u
OUT="$(dirname "$0")/../results/tools_check.md"
mkdir -p "$(dirname "$OUT")"
ok=0; missing=()

line() { printf '| %s | %s | %s |\n' "$1" "$2" "$3"; }

{
echo "# Toolchain check"
echo
echo "Checked: $(date '+%Y-%m-%d %H:%M %Z') on $(hostname)"
echo
echo "| Tool | Status | Detail |"
echo "| --- | --- | --- |"

if command -v gcc >/dev/null; then line gcc OK "$(gcc --version | head -1)"
else line gcc MISSING "ask instructor"; missing+=(gcc); fi

if command -v make >/dev/null; then line make OK "$(make --version | head -1)"
else line make MISSING "ask instructor"; missing+=(make); fi

KV=$(uname -r); KMAJ=${KV%%.*}; KMIN=$(echo "$KV" | cut -d. -f2)
if [ "$KMAJ" -gt 5 ] || { [ "$KMAJ" -eq 5 ] && [ "$KMIN" -ge 6 ]; }; then
  line "kernel >= 5.6 (io_uring)" OK "$KV"
else line "kernel >= 5.6 (io_uring)" OLD "$KV: use libaio fallback"; missing+=(kernel); fi

if [ -r /proc/sys/kernel/io_uring_disabled ]; then
  D=$(cat /proc/sys/kernel/io_uring_disabled)
  if [ "$D" = 0 ]; then line io_uring_disabled OK "0"
  else line io_uring_disabled BLOCKED "value $D: ask instructor or use libaio"; missing+=(io_uring); fi
else line io_uring_disabled OK "sysctl absent (not disabled)"; fi

LU=""
for p in /usr/include /usr/local/include "$HOME/local/include" "$HOME/.local/m1-liburing-2.5/include"; do
  [ -r "$p/liburing.h" ] && LU="$p" && break
done
if [ -n "$LU" ]; then line liburing OK "$LU/liburing.h"
else line liburing MISSING "run scripts/build_liburing.sh (no root needed)"; missing+=(liburing); fi

if [ -r /usr/include/libaio.h ]; then line "libaio (fallback)" OK "/usr/include/libaio.h"
else line "libaio (fallback)" absent "only needed if io_uring fails"; fi

if command -v python3 >/dev/null; then
  line python3 OK "$(python3 --version 2>&1)"
  for m in numpy pandas matplotlib; do
    if python3 -c "import $m" 2>/dev/null; then
      line "python: $m" OK "$(python3 -c "import $m; print($m.__version__)")"
    else line "python: $m" MISSING "bash scripts/setup_python.sh"; missing+=("$m"); fi
  done
else line python3 MISSING "ask instructor"; missing+=(python3); fi

for t in iostat filefrag smartctl git; do
  if command -v $t >/dev/null; then line "$t" OK "$(command -v $t)"
  else line "$t" absent "optional"; fi
done
echo
if [ ${#missing[@]} -eq 0 ]; then echo "**Result: everything required is available.**"
else echo "**Result: missing: ${missing[*]}**"; fi
} > "$OUT"

cat "$OUT"
