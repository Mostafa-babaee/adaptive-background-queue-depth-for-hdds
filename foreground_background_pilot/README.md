# Foreground/background pilot

This is a separate Python worker-thread prototype using Linux direct reads. It is additional work beyond the first milestone, rather than the final C/io_uring dispatcher.

Portable checks:

```bash
python3 -m unittest -v test_pilot
```

Run on Linux using the deterministic known.bin created by the milestone1 suite:

```bash
python3 pilot.py --file /path/to/known.bin --seconds 10 --fg-rate 10 --background-mib-s 8 --repetitions 3
```

Use `python3 pilot.py --help` for all settings. Results are saved to a fresh folder under `results/`.

The recorded run is in `server_evidence/pilot_jq_1doyv/`. It contains 18 cases with raw request logs, summaries, and run configuration. Queue depths 1, 2, 4, and 8 cap background worker jobs; the foreground trace and worker-pool limit are shared across policies. The input file is read only. Background scanning wraps at the end of the small fixture.

The common 8 MiB/s rate cap and initial burst explain the similar background rates. The results establish working scheduling and accounting, but do not identify the best queue depth. See the main README for project status.
