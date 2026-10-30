#!/usr/bin/env bash
# Validation only. Long shared-server experiments are a separate explicit action.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate
elif [[ -f "$HOME/venv/bin/activate" ]]; then source "$HOME/venv/bin/activate"; fi
if ! python3 -c 'import numpy,pandas,matplotlib' >/dev/null 2>&1; then
    printf 'Python analysis dependencies are missing. Run: bash scripts/setup_python.sh\n' >&2
    exit 1
fi
mkdir -p results
stamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence=$(mktemp -d "$PWD/results/validation_${stamp}_XXXXXX")
printf 'Evidence directory: %s\n' "$evidence"
if [[ -n "${LIBURING:-}" ]]; then
    make LIBURING="$LIBURING"
elif [[ -f "$HOME/.local/m1-liburing-2.5/include/liburing.h" ]]; then
    make LIBURING="$HOME/.local/m1-liburing-2.5"
else
    make
fi
make test-unit | tee "$evidence/submission_tests.log"
python3 -m unittest discover -s analysis -p 'test_*.py' -v 2>&1 | tee "$evidence/analysis_tests.log"
export DISPATCHER_TEST_DIR="$evidence/dispatcher_cases"
python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v 2>&1 | tee "$evidence/dispatcher_tests.log"
python3 tools/write_validation.py "$evidence"
printf '\nValidation finished. Keep and download: %s\n' "$evidence"
printf 'This command does not run Study A, freeze targets, or change disk configuration.\n'
