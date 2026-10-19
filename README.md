# Adaptive Background Queue Depth for HDDs

CSC 720: Storage Systems — Project 03.

We are studying how background read queue depth affects foreground latency and background throughput. The planned system uses 4 KiB random foreground reads and 256 KiB sequential background reads. Fixed depths of 1, 2, 4, and 8 will provide baselines for an adaptive controller.

## Team

| Member | Primary responsibility |
|---|---|
| Mostafa Babaei | Common C/io_uring dispatcher, read correctness, design review, and presentation assembly |
| Muhammad Ahmad Tariq | Fixed and adaptive policies, controller settings and tests, and video coordination |
| Sheryar Karim | Linux/HDD setup, workloads, experiment automation, logs, plots, and report coordination |

Each member contributes to the report and presents their own work. This initial snapshot contains Mostafa's Milestone 1 work and an additional foreground/background pilot. Other team components will be added as they are completed.

## Contents

- `docs/project_plan.pdf`: submitted execution plan.
- `docs/DISPATCHER_DESIGN.md`: proposed dispatcher design.
- `docs/DISPATCHER_DESIGN_REVIEW.md`: short design review and progress.
- `milestone1/`: C smoke reader, deterministic fixture generator, tests, and original server evidence.
- `foreground_background_pilot/`: separate Python pilot, portable tests, and saved results.
- `presentation/`: final Mostafa slide deck with speaker notes, plus the speaking script.
- `video/`: recording instructions. The demo video has not been added yet.

## Completed results

The C smoke test passed all 15 recorded suite checks, including expected-error checks and the unchanged-fixture check. The 12 portable unit tests also passed. See [the server summary](milestone1/server_evidence/suite_u8pyzzi_/summary.md).

The separate Python pilot passed 11 portable tests and completed 18 server cases: foreground alone, background alone, and mixed reads at four background depths, each repeated three times. The saved cases report no read errors or rejected requests. See [the pilot summary](foreground_background_pilot/server_evidence/pilot_jq_1doyv/summary.md).

The C reader currently submits one read at a time; the complete two-queue C dispatcher is the next implementation step. The Python pilot uses worker threads with direct reads. Its queue depth caps submitted background jobs. The small fixture, capped background rate, and short runs mean these results do not select an optimal queue depth or establish final HDD performance. Adaptive control and optional reinforcement learning remain future work.

## Run the portable tests

Python 3 is enough for these checks; they do not issue real disk reads.

```bash
python3 -m unittest discover -s milestone1/tests -v
cd foreground_background_pilot
python3 -m unittest -v test_pilot
```

## Build and run the Linux smoke suite

Use Linux, a C compiler, and liburing development files. The recorded Babbage run used liburing 2.5. If using Mostafa's existing local installation, source `milestone1/scripts/use_local_liburing.sh` first; otherwise use your system's liburing installation.

```bash
cd milestone1
bash scripts/build.sh
python3 tests/run_tests.py --approved-dir /path/to/approved/project-directory --confirm-approved
```

Replace the path with the directory assigned to your team. The suite creates its own small deterministic fixtures and saves new logs under `milestone1/results/`. Use regular project files rather than raw devices. The supplied environment log records the initial setup before liburing was installed.

## Repeat the pilot on Linux

Use the `known.bin` path printed by the smoke suite:

```bash
cd foreground_background_pilot
python3 pilot.py --file /path/to/known.bin --seconds 10 --fg-rate 10 --background-mib-s 8 --repetitions 3
```

This creates a new result directory. The original server evidence is retained under `server_evidence/`; its absolute paths identify the original run environment.

## Presentation and video

Open `presentation/Milestone1_Mostafa_Babaei.pptx` to see the speaker notes. The repository's measured claims are supported by the linked smoke and pilot evidence. Additional measurements shown in the presentation should be accompanied by their original logs when available.

A demo recording still needs to be made and linked here before the video submission is complete.
