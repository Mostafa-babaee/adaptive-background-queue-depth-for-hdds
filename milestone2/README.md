# Milestone 2: dispatcher and fixed-depth baselines

CSC 720, Project 03. Mostafa Babaei, Muhammad Ahmad Tariq, and Sheryar Karim.

This package adopts the integrated AI-assisted reference dispatcher supplied by Ahmad and Sheryar. It connects separate verifiable foreground/background files, workload traces, fixed-depth policies, window logs and analysis. The revised source includes additional safety and correctness changes. Mostafa's earlier standalone dispatcher is a separate implementation; its evidence is retained separately.

## Evidence and status

- `src/`, `analysis/`, `scripts/`, `tools/`, `tests/`: revised integrated implementation.
- `evidence/reference/source/`: original reference snapshot supplied by the teammates, before integration fixes.
- `evidence/reference/results/`: unchanged reported 27-run aggregate results, figures, hardware record and original server test report. They describe Babbage's shared PERC RAID storage, not a single physical HDD.
- `evidence/mostafa_initial/`: initial standalone-dispatcher evidence. Its passing tests do not validate this revised implementation.
- `docs/LOCAL_VALIDATION.md`: earlier authoring-computer checks.
- `docs/LINUX_VALIDATION.md` and `evidence/linux_validation/`: completed Babbage validation and matching source receipt.
- `submission/PROGRESS_UPDATE.md`: Milestone 2 progress report.

The complete original handoff has now been checked: all 27 runs passed an independent audit of 48,746,023 request records, and 459 recomputed metric values match the published per-run results. Checksums, original traces and configuration history are verified. See docs/HANDOFF_AUDIT.md and evidence/handoff_validation/. The large raw archive is retained separately.

The current revision passed Babbage Linux validation: eight C submission scenarios, 36 Python tests and 15 Linux dispatcher tests, with no skips. All 18 source hashes in the downloaded receipt match. See docs/LINUX_VALIDATION.md. The 0.5 ms target is a provisional reference-RAID calibration; it is not a team-approved physical-HDD target.

## First run on Babbage

Extract into a new folder named `milestone2_integrated`. Keep the existing `2nd_milestone` and reference files.

```bash
cd "$HOME/milestone2_integrated"
bash scripts/setup_python.sh
bash run_milestone2.sh
```

setup_python.sh uses existing analysis packages when available. Otherwise it creates `.venv` in this project and installs requirements there, with no sudo. If the distro lacks pip in the new environment, it uses the official bootstrap at https://bootstrap.pypa.io/get-pip.py . Internet access is needed only for missing packages.

The validation script detects Mostafa's existing `$HOME/.local/m1-liburing-2.5` installation. To choose a different prefix, set LIBURING explicitly. It builds the binaries, runs eight C submission scenarios, the Python controller/analysis/validation tests and the Linux dispatcher tests. It keeps raw cases and stdout/stderr in a fresh results/validation_* directory and writes a source-checksummed validation.json only after all checks pass. It does not run the 27 experiments, create large input files, freeze targets, change schedulers or flush global caches.

## Build and test manually

```bash
make LIBURING="$HOME/.local/m1-liburing-2.5"
make test-unit
python3 -m unittest discover -s analysis -p 'test_*.py' -v
DISPATCHER_TEST_DIR="$PWD/results/my_new_test_directory" python3 -m unittest discover -s tests -p 'test_dispatcher.py' -v
```

The test directory must not exist. About 12 MiB of fixture data plus request logs are retained there. Input files are ordinary disposable files; do not pass raw devices.

## Run a single demo

Use the small FG/BG fixture paths printed by the Linux test suite. They use this program's MAGIC/file-ID/block-ID pattern. The old known.bin uses a different pattern and cannot be used with this dispatcher.

```bash
bin/dispatcher --mode mixed --fg /path/to/fg.dat --bg /path/to/bg.dat \
  --trace /path/to/trace.csv --out results/a_new_demo_directory \
  --q 4 --warmup-s 0 --duration-s 2
```

Run `bin/dispatcher --help` for the interface. Foreground traces have header `t_ns,offset`; times are relative CLOCK_MONOTONIC nanoseconds. The normal end drains accepted pending reads; an interruption records pending reads as UNSUBMITTED and drains submitted reads. Exit 0 means completed with no read/verification errors, 130 means interrupted/early-stop, and another nonzero status means failed/incomplete. A missing final run_meta.json means incomplete, never successful.

## Later controlled Study A runs

Use a team/instructor-approved directory containing generated and verified fg.dat and bg.dat. Confirm permitted sustained load and set the same allowed CPU for all conditions. There is no automatic experiment in the validation command.

```bash
python3 scripts/run_study_a.py --testdir /approved/test-directory --device /dev/sda \
  --quick --confirm-shared-server-load
```

The quick run is a functional preliminary check. For the full Study A omit --quick only when the sustained study is permitted. The script uses unique experiment/run paths and never deletes an existing run. Its direct-read preparation is logged and does not guarantee identical drive/RAID cache contents. It does not issue sudo or write to drop_caches.

For a complete, validated 27-run dataset:

```bash
python3 analysis/study_a.py /path/to/experiment --trace-dir /path/to/original/traces
```

The analysis requires all nine conditions, three unique repetitions, consistent common configuration, original traces, successful complete runs, explicit direct I/O and independent row-level accounting. It refuses invalid datasets. Only use --freeze when the team deliberately chooses that validated platform's calibration. The adaptive and no-damping configs then receive identical thresholds, with up_windows=1 only for the ablation. Adaptive integration remains Milestone 3 work.

## Reproducing the supplied reference

The historical reference source and its supplied checksums/results are retained under evidence/reference. Its original scripts have the issues documented in docs/CHANGES.md; do not run its old all-in-one script. Use the revised runner for future work, and retain the distinction between the original measured build and this revised build.

Original archive SHA-256: `e4c36ce95bdc97d4bb642dd6f25e3011abd1c7a8ae910231581937e1baa82823`.

## Team roles and license

Mostafa owns dispatcher integration, correctness checks, repository/reproduction instructions and his presentation segment. Ahmad owns policy/reference settings and analysis. Sheryar owns workload generation, experiment execution, hardware records and report assembly. The baseline package identifies an AI-assisted reference implementation; authorship and results must be described consistently.

The team's original source and associated software documentation are under the MIT license. Third-party material retains its own terms.
