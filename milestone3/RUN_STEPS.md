# Run Milestone 3 on Linux

Use Bash, a C compiler, liburing development files, and Python 3. From this folder, run `bash scripts/setup_python.sh` if the analysis packages are missing. Set `LIBURING` to your liburing installation prefix if needed. For a build and functional tests, run `make test` with the Python dependencies active. See [README.md](README.md) for individual tests.

For the experiment commands, set `TESTDIR` to your approved directory containing the verified `fg.dat` and `bg.dat` fixtures. Set `DEVICE` to the device backing that directory. The experiment commands below run on a shared server and require permission to generate sustained load there.

```bash
export TESTDIR=/path/to/approved/test-directory
export DEVICE=/dev/path-to-test-device
SKIP_STUDY=1 bash run_milestone3.sh
```

That command builds, tests, and runs the six-case quick check. For the full 56-run experiment and analysis, run `bash run_milestone3.sh` with the same environment. It writes raw logs under `logs/` and generated results under `results/`. The original Babbage run took about two and a half hours. To resume an unfinished run, set `RESUME` to its existing `logs/m3_...` directory when calling the script.

To collect the third repetition of the two Study C comparisons in a new log folder, use the review package runner:

```bash
python3 scripts/run_study_bc.py --testdir "$TESTDIR" --device "$DEVICE" \
  --studies config/studies_m3_rep3.json --only-rep 3 --confirm-shared-server-load
```

This adds ten runs. Combine and analyze their evidence separately before reporting a three-repetition dataset. The published summaries reflect the supplied 56 runs.
