#!/usr/bin/env bash
# run_milestone3.sh - Milestone 3, whole team.
# Runs all of Milestone 3 on babbage with one command:
#   1 build (Tariq, Mostafa)        2 all tests (Tariq, Mostafa)
#   3 disk record (Sheryar)         4 2-minute check run (Sheryar)
#   5 Study B + Study C, 56 runs, about 2 h 20 min (Sheryar, Mostafa)
#   6 analysis, plots, diagnosis (Tariq)
#
# Usage (on babbage, from the milestone3 folder):
#   nohup bash run_milestone3.sh > milestone3_run.log 2>&1 &
#   tail -f milestone3_run.log          # watch; Ctrl-C only stops watching
# Options (environment variables):
#   TESTDIR=~/mt6289sproject/testdata   DEVICE=/dev/sda
#   SKIP_STUDY=1   stop after step 4 (build, tests, check run only)
#   RESUME=logs/m3_<stamp>   continue a stopped study (steps 5 and 6 only)
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
  step "1/6 build"
  if [[ -n "${LIBURING:-}" ]]; then make LIBURING="$LIBURING"
  elif [[ -f "$HOME/.local/m1-liburing-2.5/include/liburing.h" ]]; then make LIBURING="$HOME/.local/m1-liburing-2.5"
  else make; fi || fail "build failed (if liburing is missing: bash scripts/build_liburing.sh)"
  make bin/test_submission bin/test_controller >/dev/null || fail "test build failed"

  step "2/6 tests: controller (Tariq), dispatcher + safe reductions (Mostafa), analysis"
  T=results/_tests; rm -rf "$T"; mkdir -p "$T"
  ./bin/test_submission  > "$T/c_submission.txt" 2>&1; A=$?
  ./bin/test_controller  > "$T/c_controller.txt" 2>&1; B=$?
  python3 -m unittest discover -s analysis -p 'test_*.py' -v > "$T/py_analysis.txt" 2>&1; C=$?
  DISPATCHER_TEST_DIR="$PWD/tests/_tmp_m2_$(date +%s)" \
    python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v > "$T/py_dispatcher.txt" 2>&1; D=$?
  python3 -m unittest discover -s tests -p 'test_adaptive.py' -v > "$T/py_adaptive.txt" 2>&1; E=$?
  rm -rf tests/_tmp_m2_*
  { echo "# Milestone 3 test results ($(date '+%Y-%m-%d %H:%M %Z'), $(hostname))"; echo
    echo '```'
    echo "C submission scenarios:   $(tail -1 $T/c_submission.txt)"
    echo "C controller unit tests:  $(tail -1 $T/c_controller.txt)"
    for f in py_analysis py_dispatcher py_adaptive; do
      echo "$f: $(grep -E '^Ran ' $T/$f.txt | tail -1) $(tail -1 $T/$f.txt)"; done
    echo '```'; echo
    echo '## Every test'; echo '```'
    grep -hE " \.\.\. " $T/py_*.txt; echo '```'; } > results/test_results_m3.md
  cat results/test_results_m3.md | sed -n 3,10p
  [ $A -eq 0 ] && [ $B -eq 0 ] && [ $C -eq 0 ] && [ $D -eq 0 ] && [ $E -eq 0 ] || fail "tests failed (see results/_tests/)"
  echo "saved results/test_results_m3.md"

  step "3/6 disk record"
  bash scripts/disk_check.sh "$TESTDIR" || fail "disk check failed"

  step "4/6 2-minute check run (6 short runs)"
  python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" --quick \
      --confirm-shared-server-load || fail "quick check failed"
  Q=$(ls -dt logs/m3quick_* | head -1)
  python3 analysis/study_bc.py "$Q" > results/_quick_analysis.txt 2>&1 || fail "quick analysis failed (see results/_quick_analysis.txt)"
  echo "quick check OK: $Q"

  if [[ "${SKIP_STUDY:-0}" = "1" ]]; then echo; echo "SKIP_STUDY=1: stopping before Study B and C"; exit 0; fi

  step "5/6 Study B + Study C: 56 runs, about 2 h 20 min"
  python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" \
      --confirm-shared-server-load || fail "some runs failed or did not run; fix, then RESUME=$(ls -dt logs/m3_* | head -1) bash run_milestone3.sh"
else
  step "5/6 resume $RESUME"
  python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" --resume "$RESUME" \
      --confirm-shared-server-load || fail "some runs failed or did not run; fix, then RESUME=$RESUME bash run_milestone3.sh"
fi

L="${RESUME:-$(ls -dt logs/m3_* | head -1)}"
step "6/6 analysis, plots and diagnosis"
python3 analysis/study_bc.py "$L" || fail "analysis failed"
R="results/$(basename "$L")"
cp "$L/experiment.json" "$R/" 2>/dev/null
cp results/test_results_m3.md results/disk_info.md "$R/" 2>/dev/null
( cd "$L" && sha256sum */run_meta.json */windows.csv */requests.csv.gz ) > "$R/raw_logs.sha256"
( cd traces && sha256sum *.csv ) > "$R/traces.sha256"
mkdir -p "$R/traces" && cp traces/*.csv "$R/traces/"

echo
echo "ALL DONE $(date '+%H:%M:%S')."
echo "Send this folder:  $R   (summary.md, figures, tables, small time series)"
echo "Raw logs stay in:  $L   ($(du -sh "$L" | cut -f1)); keep them for the raw archive"
