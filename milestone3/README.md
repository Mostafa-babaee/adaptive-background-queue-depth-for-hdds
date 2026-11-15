# Milestone 3: adaptive policy and controlled experiments

CSC 720 Storage Systems, Project 03 (Adaptive Background Queue Depth for HDDs).
Team: Sheryar Karim, Mostafa Babaei, Muhammad Ahmad Tariq. Due November 15, 2026.

This folder builds on the final Milestone 2 code (`milestone2/`, commit
fe20f47). The Milestone 2 dispatcher was supplied as an AI-assisted reference
by Ahmad and Sheryar and was reviewed, revised, integrated and tested by Mostafa.
The team used AI assistance for the Milestone 3 additions and reviewed and tested the resulting code.

## What Milestone 3 adds

| Planned task | Owner | Where |
| --- | --- | --- |
| Windowed target-miss controller: minimum sample count, hold on sparse data, q ≥ 1 while scanning, thresholds in a config file | Muhammad Ahmad Tariq | `src/controller.c`, `src/controller.h`, `config/adaptive.json` |
| No-damping ablation (q goes up after one good window) and unit tests for sparse windows and allowed q values | Muhammad Ahmad Tariq | `config/adaptive_nodamp.json`, `tests/test_controller.c`, `analysis/test_ctrl_match.py` |
| Safe limit reductions: when q drops below the reads in flight, no new background read until enough finish | Mostafa Babaei | `src/dispatcher.c` (drain logged in `run_meta.json`), `tests/test_adaptive.py` |
| Constant and alternating quiet/busy traces, identical for every policy | Sheryar Karim | `tools/make_trace.py`, `config/studies_m3.json` |
| Study B: adaptive vs fixed q = 1, 2, 4, 8 (plus the ablation), 2 traces, 3 repetitions; q, misses and cumulative scan bytes over time | Sheryar Karim | `scripts/run_study_bc.py`, `analysis/study_bc.py` |
| Study C: high-demand case, and the alternating trace with 1 MiB chunks | Sheryar Karim and Mostafa Babaei | same |
| Integrity, errors and accounting on every run; controller CPU cost | Mostafa Babaei | `analysis/validate_logs.py`, `cpu_cost` in `run_meta.json`, `ctrl_cpu_ns` in `windows.csv` |
| Diagnose oscillation and slow recovery, compare with the ablation | Muhammad Ahmad Tariq | `analysis/study_bc.py` (reversals, reaction and recovery times) |

## The controller (once per 1000 ms window)

| Situation | Action |
| --- | --- |
| scan not running | hold q |
| fewer than 25 completed FG reads | hold q and the streak (SPARSE) |
| more than 5 % of FG reads slower than 0.5 ms | one level down (8 → 4 → 2 → 1), streak = 0 |
| at most 1 % slower | streak + 1; after 3 such windows in a row, one level up |
| between 1 % and 5 % | hold, streak = 0 |

q is always 1, 2, 4 or 8. The no-damping ablation is the same rule with
up_windows = 1. The settings are the values frozen in Milestone 2 from Study A
on babbage. The team uses only the course server, so this target is final for
all Milestone 3 runs (it is not changed after seeing Study B or C).

## Reproduce the experiments

Published results and limitations are described in [the results notes](docs/RESULTS.md). See [the run instructions](RUN_STEPS.md) for Linux setup, the quick check, the full run, and the optional third Study C repetition. The quick check and full runs use shared storage and need the approved test directory and device.

## Tests

```bash
make && make bin/test_controller bin/test_submission
./bin/test_submission                     # 8 submission scenarios (Milestone 2)
./bin/test_controller                     # controller unit tests (63 checks)
python3 -m unittest discover -s analysis -p 'test_*.py' -v      # 39 tests (36 + 3 C-vs-Python)
python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v  # 15 Milestone 2 dispatcher tests
python3 -m unittest discover -s tests -p 'test_adaptive.py' -v    # 10 adaptive / safe-reduction tests
```

## Outputs

- Raw logs: `logs/m3_<stamp>/<run>/` with `run_meta.json`, `windows.csv`,
  `requests.csv.gz`, `terminal.log`; `experiment.json` has the order, the
  settings, and the trace and dispatcher checksums.
- Results to send back: `results/m3_<stamp>/` with `summary.md`, `runs.csv`,
  `summary.csv`, `phases.csv`, `timeseries/`, the figures, the test results,
  the disk record, the traces and checksums of the raw logs.

## Limits

All runs use only the course server (babbage). Its disk reports itself as a
Dell PERC H755 RAID virtual disk, and other users share it, so the results
describe this server disk. Tuning (Study A, Milestone 2) and evaluation
(Studies B and C) are separate runs; the alternating and high-demand traces are
new and were not used to choose the settings.
