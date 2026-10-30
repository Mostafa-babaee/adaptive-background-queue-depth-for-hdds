# Milestone 2 handoff: Study A evidence (for Mostafa)

From: Muhammad Ahmad Tariq · 2026-10-30
Status of these results: **preliminary shared-server check**, not HDD benchmarks.

## 1. Original Study A logs (all 27 runs)

File: `studyA_bundle_2026-10-30.tar.gz` (951 MB)
SHA-256: `29c3f1f5d12446e420713a8f131656949c5ec5df075dc01334716ba0851943af`
(also in `studyA_bundle_2026-10-30.sha256`; checked: the copy on the Mac matches the one made on babbage)

- `logs/studyA/<run_id>/run_meta.json`, `requests.csv`, `windows.csv` for all 27 runs
  (27 + 27 + 27 files), the **original files written by the dispatcher**, not regenerated.
  Run IDs start `2026-10-30T10-28_`; first run 10:28, last run 11:26 CDT.
- All 27 `run_meta.json`: `accounting_ok: true`, `verify_fail: 0`, `completed_err: 0`, `direct_io: true`.
- Terminal output: `milestone2_run.log` (in the bundle and in `terminal/` here), the full
  `nohup` output of `run_milestone2.sh` (build, tests, disk record, quick check, Study A, analysis).
  It contains one summary line per run (the dispatcher's final stderr line).
  **No separate per-run stdout/stderr files were saved**; per-run detail is in `run_meta.json`.
- Also in the bundle: `results/` (summaries, plots, `target.json`, `verify_fg.txt`, `verify_bg.txt`,
  `version_and_checksums.txt`, `test_results.md`, `disk_info.md`) and the source, configs and scripts.
  Not included: `results/progress_update_m2.md` (wrong attribution, see 4) and `bin/` (rebuild with `make`;
  its checksum is in `version_and_checksums.txt`). The bundle also contains some harmless `__pycache__` files.
- The originals are kept unchanged on babbage in `~/M2_code_for_server/logs/studyA`.

## 2. Exact workload traces

Both are in the bundle and in `traces/` here.

| Trace | SHA-256 | Used for |
| --- | --- | --- |
| `constant_50rps_130s_seed42.csv` | `b61520939455e9f03cc0c2a3f66c9a93387d0583cb6d6ac571bb6013b16f6a0c` | **All 27 Study A runs** (every `run_meta.json` points to it). 6,576 arrivals, Poisson, mean 50/s, seed 42, 130 s (10 s warm-up + 120 s), 4 KiB-aligned offsets into `fg.dat`. Header: `t_ns,offset` |
| `constant_50rps_10s_seed42.csv` | `4c308355570c29520af889ee0592a7da5bdaa5644e8f1150f3828be445d7f5e3` | Only the 9-run 2-minute check before Study A (`logs/studyA_quick`, not part of the reported results; still on babbage) |

No other traces were used.

## 3. Controller configuration: why the checksums differ

| File | SHA-256 | Content |
| --- | --- | --- |
| `config/adaptive.json` in **M2_code_for_server.zip** (original, before the run) | `8ddad9e050ce661308164db0a69e4763351ae6ed1841f319006b8d7f8b1180d1` | `target_ms: null`, `window_ms: 500`, `min_samples: 50` |
| `config/adaptive.json` **on babbage after the run** (in the bundle; copy in `config/adaptive.json.FROZEN_from_server`) | `a97e93279150e6faf96cab7d0d53e949fa16e1611d4ef23d369afa06454a0688` | `target_ms: 0.5`, `window_ms: 1000`, `min_samples: 25`, `miss_high: 0.05`, `miss_low: 0.01`, `up_windows: 3` |

- The recorded checksum (`a97e93…` in `version_and_checksums.txt`) is the **post-run** file.
  The last step of `run_milestone2.sh` (`analysis/study_a.py logs/studyA --freeze`) wrote these
  values into `config/adaptive.json` after all 27 runs had finished. That is the only source/config file
  that differs from the ZIP; all other checksums match the ZIP exactly.
- **No Study A run used `adaptive.json`.** All 27 runs were fixed-q (`policy: fixed`), and no target was
  passed to the dispatcher (`workload.json` has `target_ms: null`, so `run_meta.json` shows `target_ms: null`).
  The file is an *output* of the analysis, not an input of any run.
- How the values were chosen (by the script, automatically): `target_ms` = 1.25 × mean p99 of the combined
  q = 1 runs (0.345 ms) rounded up to 0.5 ms; `window_ms`/`min_samples` sized so a window holds about twice
  `min_samples` reads at 50 reads/s; `miss_high`, `miss_low`, `up_windows` unchanged from the Milestone 1 draft.

**Team agreement: these settings are NOT agreed or final.** They were computed from preliminary
babbage RAID data, so the 0.5 ms target reflects the RAID controller cache, not a hard disk. The team's
position is that the target and thresholds must be chosen from suitable baseline runs on the physical HDD
(department computer). Until then, treat `adaptive.json.FROZEN_from_server` as a preliminary example only.

## 4. Important context

- **Dispatcher used:** these runs used `src/dispatcher.c` from `M2_code_for_server`, a **reference dispatcher
  written with AI assistance (Claude)** to test the workload and analysis pipeline. **It is not Mostafa's
  dispatcher.** The draft `progress_update_m2.md` wrongly credits Mostafa with it, so it was left out.
- **Hardware:** babbage `/dev/sda`, Dell PERC H755 RAID virtual disk (rotational 0, queue depth 3840),
  mq-deadline; 53 users logged in, load 32.6 at start. The 2 GiB scan file fits in the controller cache,
  so throughput (2.9–5.0 GB/s) and latency (0.15–1.3 ms) are far from single-HDD values.
- **Test files:** `fg.dat` 512 MiB (file ID 1) and `bg.dat` 2 GiB (file ID 2), block pattern from
  `tools/make_testfiles.py`; both fully verified OK after the runs (`results/verify_*.txt`).

## 5. Reproduce

```
tar xzf studyA_bundle_2026-10-30.tar.gz && cd <extracted folder>
python3 analysis/study_a.py logs/studyA --out results/studyA_check     # no --freeze: does not touch config
diff results/studyA/summary.csv results/studyA_check/summary.csv
```
Full rerun (new logs, not needed for review): `make && bash run_milestone2.sh` on babbage.
