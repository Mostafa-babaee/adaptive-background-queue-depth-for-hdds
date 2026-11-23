# Milestone 4: learned queue-depth policy

CSC 720 Storage Systems, Project 03. Mostafa Babaei, Muhammad Ahmad Tariq, and Sheryar Karim.

The dispatcher supports a frozen tabular reinforcement-learning policy alongside fixed depths, the adaptive controller, and the no-damping variant. The RL policy selects a background depth from 1, 2, 4, and 8 using the current depth, foreground miss bucket, and foreground sample-count bucket. Its 36-entry table was trained offline with Q-learning and is compiled into the C dispatcher.

The course experiments use the professor-approved Babbage shared Dell PERC RAID storage. This snapshot includes source, training inputs and tables, simulator output, and short VM smoke-test logs.

## Contents

- `src/`: common io_uring dispatcher, adaptive controller, and frozen RL policy.
- `tests/` and `analysis/test_*.py`: C and Python correctness checks.
- `analysis/`: request-log validation and Study A/B/C analysis, including RL runs.
- `config/`: policy settings and experiment configurations.
- `scripts/` and `tools/`: workload generation, experiments, and table export.
- `rl_training/`: simulator, training scripts, training windows, and saved tables.
- `evidence/`: simulator evaluation, penalty sweep, and short VM read-test evidence.

## Build and test on Linux

Use a C compiler, liburing, and Python 3. If the analysis dependencies are missing, run `bash scripts/setup_python.sh`, then activate `.venv` if that script creates it.

```bash
make
make test
```

For an existing local liburing installation, build with `make LIBURING=/path/to/liburing-prefix`. Babbage's existing `$HOME/.local/m1-liburing-2.5` installation is detected by the Makefile.

`make test-unit` runs the C submission, adaptive-controller, and RL table checks. `make test` also runs the Python analysis suite and Linux dispatcher integration tests. The RL table tests cover bucket boundaries, sparse windows, scanning state, and action mapping.

## Short RL demonstration

From this folder, create fresh disposable files and replay a short foreground trace.

```bash
mkdir -p results
DEMO_DIR=$(mktemp -d "$PWD/results/rl_demo_XXXXXX")
python3 tools/make_testfiles.py "$DEMO_DIR/fg.dat" 8 1
python3 tools/make_testfiles.py "$DEMO_DIR/bg.dat" 16 2
python3 tools/make_trace.py --fg-file "$DEMO_DIR/fg.dat" --rate 50 \
  --seconds 12 --seed 49 --out "$DEMO_DIR/trace.csv"
bin/dispatcher --mode mixed --policy rl --window-ms 1000 --target-ms 0.5 \
  --fg "$DEMO_DIR/fg.dat" --bg "$DEMO_DIR/bg.dat" --trace "$DEMO_DIR/trace.csv" \
  --warmup-s 2 --duration-s 10 --out "$DEMO_DIR/run"
python3 -m json.tool "$DEMO_DIR/run/run_meta.json"
cat "$DEMO_DIR/run/windows.csv"
```

The RL table is compiled from `src/rl_table.h`. The matching `config/rl_policy.json` records the state definition and table values. The example explicitly selects the trained policy's 1000 ms window and 0.5 ms latency threshold.

## Training and simulator evaluation

```bash
cd rl_training
python3 evaluate_frozen.py
```

The evaluator reads `windows.json` and `rl_table_frozen.npy`. The simulator samples from the supplied window records with replacement. The frozen table matches `table_pen6.0.npy`, the C header, and the JSON table. The supplied evaluation output is in `evidence/simulator/eval_frozen.txt`.

To reproduce the penalty-6 training settings, run the following from `rl_training/`:

```bash
python3 - <<'PY'
import numpy as np
import rl_sim
import train_rl

table, scores = train_rl.train(rl_sim.build_pool(), episodes=40000, seed=1, pen=6.0)
np.save('rl_table_retrained.npy', table)
PY
```

## Controlled experiments

Set `TESTDIR` to the approved directory containing verified `fg.dat` and `bg.dat` files. Set `DEVICE` to the device backing that directory. With permission to generate sustained load on the shared server, run:

```bash
TESTDIR=/approved/test-directory DEVICE=/dev/test-device bash run_milestone4_rl.sh
```

The script builds, runs unit and analysis tests, executes the 54-run experiment in `config/studies_m4_rl.json`, and analyzes the resulting logs. It uses seeds 46, 47, and 48. Generated experiment output goes under `logs/` and `results/`.

For an existing raw run folder, the analysis entry point is:

```bash
python3 analysis/study_bc.py /path/to/experiment --out results/my_analysis
```

## Included evidence

`evidence/vm_smoke/` contains short RL and adaptive runs from the supplied VM test, with request logs, window logs, metadata, and traces. `evidence/penalty_sweep/` and `evidence/simulator/` contain the supplied simulation results. The top-level `MANIFEST.sha256` records the exact files in this publication.

The team used AI assistance for the implementation and reviewed and tested the resulting code. Software licensing follows [LICENSE](LICENSE).
