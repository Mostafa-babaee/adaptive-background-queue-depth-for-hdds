#!/usr/bin/env bash
set -u
set -o pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P) || exit 2
mkdir -p "$root/results" || exit 2
log=$(mktemp "$root/results/environment_XXXXXX.log") || exit 2
exec > >(tee "$log") 2>&1
printf 'Milestone 1 environment check\nUTC: '
date -u '+%Y-%m-%dT%H:%M:%SZ'
hostname
whoami
uname -a
printf '\nCompiler commands\n'
for tool in cc gcc g++ clang make pkg-config python3; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf '%s: %s\n' "$tool" "$(command -v "$tool")"
        "$tool" --version 2>&1 | head -n 1 || true
    else
        printf '%s: NOT FOUND\n' "$tool"
    fi
done
printf '\nLibrary metadata (optional pkg-config)\n'
if command -v pkg-config >/dev/null 2>&1; then
    pkg-config --modversion liburing 2>&1 || true
    pkg-config --modversion libaio 2>&1 || true
fi
printf '\nCompile and link liburing probe (not executed)\n'
compiler=${CC:-cc}
probe=$(mktemp -d "$root/results/library_probe_XXXXXX") || exit 2
cat > "$probe/probe.c" <<'C'
#include <liburing.h>
int main(void) {
    struct io_uring ring;
    int result = io_uring_queue_init(2, &ring, 0);
    if (result == 0) io_uring_queue_exit(&ring);
    return result != 0;
}
C
flags=(-luring)
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists liburing; then
    read -r -a flags <<< "$(pkg-config --cflags --libs liburing)"
fi
if command -v "$compiler" >/dev/null 2>&1 &&
   "$compiler" -std=c11 -Wall -Wextra "$probe/probe.c" -o "$probe/probe" "${flags[@]}"; then
    printf 'liburing compile/link: PASS. Runtime permission still needs the smoke test.\n'
else
    printf 'liburing compile/link: BLOCKED. Keep diagnostics; ask about required development packages.\n'
fi
printf '\nPython plotting imports\n'
if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import importlib
import sys
print('Python:', sys.version.split()[0])
for name in ('matplotlib', 'numpy'):
    try:
        module = importlib.import_module(name)
        print(name + ': available ' + getattr(module, '__version__', ''))
    except Exception as exc:
        print(name + ': unavailable: ' + str(exc))
PY
fi
printf '\nLimits and io_uring policy (where readable)\n'
ulimit -l
for setting in /proc/sys/kernel/io_uring_disabled /proc/sys/kernel/io_uring_group; do
    if [[ -r "$setting" ]]; then
        printf '%s: ' "$setting"
        cat "$setting"
    fi
done
printf '\nSaved log: %s\n' "$log"
printf 'No packages installed and no storage configuration changed.\n'
