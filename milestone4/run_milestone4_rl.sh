#!/usr/bin/env bash
# run_milestone4_rl.sh - Milestone 4, held-out test of the RL policy on babbage.
#   1 build and all unit tests (including the RL table tests)
#   2 Python analysis tests
#   3 held-out study: 54 runs, new trace seeds 46-48, about 3 h (shared server)
#   4 analysis, plots and tables into results/m4_rl_heldout
#
# Usage (on babbage, from the milestone4 folder, in a quiet time):
#   nohup bash run_milestone4_rl.sh > milestone4_rl.log 2>&1 &
#   tail -f milestone4_rl.log          # Ctrl-C only stops watching
# Options (environment variables):
#   TESTDIR=~/mt6289sproject/testdata   DEVICE=/dev/sda
#   RESUME=logs/m3_<stamp>   continue a stopped study (steps 3 and 4 only)
set -u
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
TESTDIR="${TESTDIR:-$HOME/mt6289sproject/testdata}"
DEVICE="${DEVICE:-/dev/sda}"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate
elif [[ -f "$HOME/venv/bin/activate" ]]; then source "$HOME/venv/bin/activate"; fi

step() { echo; echo "=== $(date '+%H:%M:%S')  $*"; }
fail() { echo "STOPPED: $*"; exit 1; }

python3 -c 'import numpy,pandas,matplotlib' >/dev/null 2>&1 || fail "Python packages missing: bash scripts/setup_python.sh"
mkdir -p results

if [[ -z "${RESUME:-}" ]]; then
  step "1/4 build and unit tests"
  make clean >/dev/null 2>&1
  make || fail "build failed (if liburing is missing: bash scripts/build_liburing.sh)"
  make test-unit > results/m4_unit_tests.txt 2>&1 || fail "unit tests failed, see results/m4_unit_tests.txt"
  tail -3 results/m4_unit_tests.txt

  step "2/4 analysis tests"
  python3 -m unittest discover -s analysis -p 'test_*.py' > results/m4_py_tests.txt 2>&1 || fail "analysis tests failed"
  tail -2 results/m4_py_tests.txt
fi

step "3/4 held-out study (54 runs)"
if [[ -n "${RESUME:-}" ]]; then
  python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" \
      --studies config/studies_m4_rl.json --confirm-shared-server-load --resume "$RESUME" || fail "study stopped; resume with RESUME=$RESUME"
  LOG="$RESUME"
else
  python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" \
      --studies config/studies_m4_rl.json --confirm-shared-server-load || fail "study stopped; see the message above"
  LOG=$(ls -dt logs/* | head -1)
fi

step "4/4 analysis"
python3 analysis/study_bc.py "$LOG" --out results/m4_rl_heldout || fail "analysis failed"
echo
echo "DONE. Results: results/m4_rl_heldout   Log folder: $LOG"
