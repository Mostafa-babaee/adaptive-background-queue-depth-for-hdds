#!/usr/bin/env bash
# run_milestone2.sh - Milestone 2, whole team.
# Runs all of Milestone 2 on babbage with one command:
#   1 build (Mostafa)          2 all tests (Mostafa, Tariq)
#   3 disk record (Sheryar)    4 2-minute check run (Sheryar)
#   5 Study A, 27 runs (Sheryar)   6 analysis + frozen target (Tariq)
#   7 progress update (team)
#
# Usage (on babbage, from the code/ folder):
#   nohup bash run_milestone2.sh > milestone2_run.log 2>&1 &
#   tail -f milestone2_run.log          # watch; Ctrl-C only stops watching
# Options (environment variables):
#   TESTDIR=~/mt6289sproject/testdata   DEVICE=/dev/sda   SKIP_STUDY=1 (steps 1-4 only)
set -u
cd "$(dirname "$0")"
TESTDIR="${TESTDIR:-$HOME/mt6289sproject/testdata}"
DEVICE="${DEVICE:-/dev/sda}"
[ -f "$HOME/venv/bin/activate" ] && source "$HOME/venv/bin/activate"

step() { echo; echo "=== $(date '+%H:%M:%S')  $*"; }
fail() { echo "STOPPED: $*"; exit 1; }

step "1/7 build (Mostafa)"
make || fail "build failed (if liburing is missing: bash scripts/build_liburing.sh)"

step "2/7 tests (Mostafa: dispatcher, Tariq: analysis + controller)"
mkdir -p results
python3 -m unittest discover -s analysis -p 'test_*.py' -v > results/_t1.txt 2>&1; A=$?
python3 -m unittest tests/test_dispatcher.py -v > results/_t2.txt 2>&1; B=$?
tail -3 results/_t1.txt; tail -3 results/_t2.txt
{ echo "# Test results ($(date '+%Y-%m-%d %H:%M %Z'), $(hostname))"; echo; echo '```';
  grep -E " \.\.\. |^Ran|^OK|FAILED" results/_t1.txt results/_t2.txt | sed 's#^results/_t[12].txt:##'; echo '```'; } > results/test_results.md
rm -f results/_t1.txt results/_t2.txt
echo "saved results/test_results.md"
[ $A -eq 0 ] && [ $B -eq 0 ] || fail "tests failed (see results/test_results.md)"

step "3/7 disk record (Sheryar)"
bash scripts/disk_check.sh "$TESTDIR" || fail "disk check failed"

step "4/7 2-minute check run (Sheryar)"
python3 scripts/run_study_a.py --testdir "$TESTDIR" --device "$DEVICE" --quick || fail "quick check failed"

if [ "${SKIP_STUDY:-0}" = "1" ]; then echo; echo "SKIP_STUDY=1: stopping before Study A"; exit 0; fi

step "5/7 Study A: 27 runs, about 65 minutes (Sheryar)"
python3 scripts/run_study_a.py --testdir "$TESTDIR" --device "$DEVICE" || echo "WARNING: some runs failed; see above"

step "6/7 analysis and frozen target (Tariq)"
python3 analysis/study_a.py logs/studyA --freeze || fail "analysis failed"

step "7/7 progress update (team)"
python3 analysis/make_progress_update.py || fail "progress update failed"

echo
echo "ALL DONE $(date '+%H:%M:%S'). Results are in results/ (send this folder). Raw logs are in logs/studyA."
