#!/usr/bin/env bash
# Project-local Python environment only. No sudo or global Python changes.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if python3 -c 'import numpy,pandas,matplotlib' >/dev/null 2>&1; then
    printf 'Required Python packages are already available.\n'; exit 0
fi
if [[ ! -d .venv ]]; then python3 -m venv --without-pip .venv; fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    mkdir -p build
    .venv/bin/python - <<'PY'
from pathlib import Path
from urllib.request import urlopen
target = Path('build/get-pip.py')
if not target.exists():
    with urlopen('https://bootstrap.pypa.io/get-pip.py', timeout=30) as response:
        target.write_bytes(response.read())
PY
    .venv/bin/python build/get-pip.py
fi
.venv/bin/python -m pip install -r requirements.txt
printf 'Installed project-local packages. The validation script activates .venv automatically.\n'
