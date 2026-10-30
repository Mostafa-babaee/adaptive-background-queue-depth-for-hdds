#!/usr/bin/env bash
# disk_check.sh - Milestone 2, Sheryar Karim.
# Records the server disk that holds the test folder (babbage: the same disk and
# folder as Milestone 1) and checks the two test files. It only creates a test
# file if it is missing. Read-only otherwise.
#
# Usage: bash scripts/disk_check.sh <testdir>      e.g. ~/mt6289sproject/testdata
# Output: results/disk_info.md
set -u
TESTDIR="${1:?usage: $0 <testdir>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/results/disk_info.md"
mkdir -p "$ROOT/results" "$TESTDIR"
FG_MIB=$(python3 -c "import json;print(json.load(open('$ROOT/config/workload.json'))['fg_file_mib'])")
BG_MIB=$(python3 -c "import json;print(json.load(open('$ROOT/config/workload.json'))['bg_file_mib'])")

SRC=$(df --output=source "$TESTDIR" | tail -1)
DEV=$(lsblk -no PKNAME "$SRC" 2>/dev/null | head -1)
[ -z "$DEV" ] && DEV=$(basename "$SRC")
Q=/sys/block/$DEV/queue

{
echo "# Server disk record ($(date '+%Y-%m-%d %H:%M %Z'))"
echo
echo "| Item | Value |"
echo "| --- | --- |"
echo "| Host | $(hostname) |"
echo "| Test folder | $TESTDIR |"
echo "| Partition | $SRC |"
echo "| Disk | /dev/$DEV |"
echo "| Model | $(cat /sys/block/$DEV/device/model 2>/dev/null | xargs) |"
echo "| Size | $(lsblk -dno SIZE /dev/$DEV 2>/dev/null | xargs) |"
echo "| Rotational flag | $(cat $Q/rotational 2>/dev/null) |"
echo "| I/O scheduler | $(cat $Q/scheduler 2>/dev/null) |"
echo "| Device queue depth | $(cat /sys/block/$DEV/device/queue_depth 2>/dev/null) |"
echo "| Kernel | $(uname -r) |"
echo "| CPUs | $(nproc) |"
echo "| Free space in test folder | $(df -h --output=avail "$TESTDIR" | tail -1 | xargs) |"
echo "| Users logged in | $(who | wc -l) |"
echo "| Load (1 min) | $(cut -d' ' -f1 /proc/loadavg) |"
echo
echo "Device to pass to run_study_a.py: \`--device /dev/$DEV\`"
} | tee "$OUT"

cd "$TESTDIR" || exit 1
[ -f fg.dat ] || python3 "$ROOT/tools/make_testfiles.py" fg.dat "$FG_MIB" 1
[ -f bg.dat ] || python3 "$ROOT/tools/make_testfiles.py" bg.dat "$BG_MIB" 2
ls -l fg.dat bg.dat
echo "saved $OUT"
