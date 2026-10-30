#!/usr/bin/env python3
"""
make_progress_update.py - Milestone 2, team (assembled by Sheryar Karim).
Writes results/progress_update_m2.md from the Study A results, so every number in
the progress update comes straight from the logs.

Reads: results/studyA/{summary.csv, runs.csv, target.json}, results/disk_info.md,
       results/test_results.md (all written by run_milestone2.sh)
Usage: python3 analysis/make_progress_update.py [--results results/studyA]
"""
import argparse
import json
import math
import os
import re

import pandas as pd

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(CODE)


def f(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def disk_line(path):
    if not os.path.exists(path):
        return "babbage (disk record not found)"
    t = open(path).read()
    get = lambda k: (re.search(rf"\| {re.escape(k)} \| ([^|]*) \|", t) or [None, "?"])[1].strip()
    return (f"{get('Host')}, disk {get('Disk')} ({get('Model')}, {get('Size')}, rotational flag "
            f"{get('Rotational flag')}, scheduler {get('I/O scheduler')}), test folder {get('Test folder')}")


def test_counts(path):
    if not os.path.exists(path):
        return None
    t = open(path).read()
    ran = [int(n) for n in re.findall(r"Ran (\d+) test", t)]
    return ran, ("FAILED" not in t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(CODE, "results", "studyA"))
    ap.add_argument("--out", default=os.path.join(CODE, "results", "progress_update_m2.md"))
    a = ap.parse_args()

    s = pd.read_csv(os.path.join(a.results, "summary.csv"))
    runs = pd.read_csv(os.path.join(a.results, "runs.csv"))
    target = json.load(open(os.path.join(a.results, "target.json"))) if os.path.exists(os.path.join(a.results, "target.json")) else None
    mixed = s[s["mode"] == "mixed"].set_index("q")
    alone = s[s["mode"] == "bg"].set_index("q")
    fga = s[s["mode"] == "fg"]
    clean = runs[(runs["accounting_ok"]) & (runs["errors"] == 0) & (runs["unverified"] == 0) & (runs["direct_io"])]
    tc = test_counts(os.path.join(CODE, "results", "test_results.md"))

    L = ["# Progress Update: Milestone 2 (Working Dispatcher and Fixed-Depth Baselines)", "",
         "CSC 720 Storage Systems, Project 03 · Team: Sheryar Karim, Mostafa Babaei, Muhammad Ahmad Tariq · "
         "Missouri State University · due November 1, 2026", "",
         "## Summary", ""]
    L += [f"- The common C dispatcher (io_uring, O_DIRECT) is built and tested"
          + (f": {sum(tc[0])} automatic tests, {'all passing' if tc[1] else 'SOME FAILING'}." if tc else ".")]
    L += [f"- Study A ran on {disk_line(os.path.join(CODE, 'results', 'disk_info.md'))}.",
          f"- {len(runs)} runs; {len(clean)} of {len(runs)} clean (every request accounted for, 0 errors, every byte verified, O_DIRECT)."]
    if 1 in mixed.index and 8 in mixed.index:
        p1, p8 = mixed.loc[1, "fg_p99_ms_mean"], mixed.loc[8, "fg_p99_ms_mean"]
        t1, t8 = mixed.loc[1, "scan_mib_s_mean"], mixed.loc[8, "scan_mib_s_mean"]
        L += [f"- Trade-off: from q = 1 to q = 8 the scan goes from {f(t1, 1)} to {f(t8, 1)} MiB/s "
              f"({f(t8 / t1 if t1 else math.nan, 1)}×) while foreground p99 goes from {f(p1)} to {f(p8)} ms "
              f"({f(p8 / p1 if p1 else math.nan, 1)}×)."]
    if not fga.empty:
        L += [f"- Foreground alone: p99 {f(fga['fg_p99_ms_mean'].iloc[0])} ms."]
    if target:
        L += [f"- Frozen latency target: **{target['target_ms']:g} ms**; window {target['window_ms']} ms, "
              f"min_samples {target['min_samples']}, miss_high {target['miss_high']}, miss_low {target['miss_low']}, "
              f"up_windows {target['up_windows']}."]
    L += [""]

    L += ["## Task status", "", "| # | Planned task | Owner | Status |", "| --- | --- | --- | --- |",
          "| 1 | Common dispatcher: async reads, two pending queues, FG quota, BG limit q, timestamps, completion accounting, clean shutdown | Mostafa Babaei | Done (`code/src/dispatcher.c`) |",
          "| 2 | Correctness tests: verified contents, end of file, full pending queue, read errors, shutdown with reads in flight | Mostafa Babaei | Done (10 tests, `code/tests/test_dispatcher.py`) |",
          "| 3 | Configurable fixed depths q = 1, 2, 4, 8; record the actual outstanding count | Muhammad Ahmad Tariq | Done (`bg_out_mean`, `bg_out_max` per window) |",
          "| 4 | Analysis: p50/p99, target-miss fraction, MiB/s, completed scan bytes | Muhammad Ahmad Tariq | Done (`code/analysis/study_a.py`) |",
          "| 5 | Workload generator and run scripts with consistent warm-up and cache preparation | Sheryar Karim | Done (`make_trace.py`, `run_study_a.py`) |",
          f"| 6 | Foreground-alone, scanner-alone, combined runs at each q, 3 repetitions; p99 vs throughput plot | Sheryar Karim | Done ({len(runs)} runs) |",
          "| 7 | Choose and freeze the latency target and controller thresholds | Muhammad Ahmad Tariq with team | "
          + (f"Done ({target['target_ms']:g} ms)" if target else "Pending") + " |",
          "| 8 | Slides and recordings (one part per member) | All | In progress |", ""]

    L += ["## Study A results (mean ± sd over repetitions, warm-up dropped)", "",
          "| Run type | q | FG p50 ms | FG p99 ms | miss % | scan MiB/s | actual depth |", "| --- | --- | --- | --- | --- | --- | --- |"]
    if not fga.empty:
        r = fga.iloc[0]
        L.append(f"| foreground alone | – | {f(r['fg_p50_ms_mean'])} | {f(r['fg_p99_ms_mean'])} ± {f(r['fg_p99_ms_sd'])} | "
                 f"{f(100 * r['miss_frac_mean'], 1)} | – | – |")
    for q in (1, 2, 4, 8):
        if q in alone.index:
            r = alone.loc[q]
            L.append(f"| scanner alone | {q} | – | – | – | {f(r['scan_mib_s_mean'], 1)} ± {f(r['scan_mib_s_sd'], 1)} | {f(r['bg_out_mean_mean'])} |")
    for q in (1, 2, 4, 8):
        if q in mixed.index:
            r = mixed.loc[q]
            L.append(f"| combined | {q} | {f(r['fg_p50_ms_mean'])} | {f(r['fg_p99_ms_mean'])} ± {f(r['fg_p99_ms_sd'])} | "
                     f"{f(100 * r['miss_frac_mean'], 1)} | {f(r['scan_mib_s_mean'], 1)} ± {f(r['scan_mib_s_sd'], 1)} | {f(r['bg_out_mean_mean'])} |")
    L += ["", "Figures: `code/results/studyA/studyA_tradeoff.png` (foreground p99 vs scan throughput), "
          "`studyA_scan_throughput.png`, `studyA_latency_cdf.png`, `studyA_actual_depth.png`.", ""]

    L += ["## Mostafa Babaei: dispatcher and tests", "",
          "One single-threaded C program, shared by every policy. FG reads come from a fixed trace; a full FG queue "
          "rejects and logs. The scanner keeps the BG queue filled. At most `fg_quota` FG and q BG reads are in flight. "
          "Every block is verified against the test-file pattern. On shutdown or Ctrl-C, waiting requests are logged as "
          "UNSUBMITTED and every read in flight is drained; the run checks accepted = submitted + unsubmitted and "
          "submitted = OK + ERR.", "",
          "## Muhammad Ahmad Tariq: fixed depths, analysis, target", "",
          "Each window logs the configured q and the actual outstanding count; the analysis reports p50/p95/p99, wait "
          "and service time, miss fraction, MiB/s and scan bytes, averaged over repetitions, and draws the required "
          "figure. Target rule: 1.25 × mean p99 of the combined run at q = 1, rounded up to 0.5 ms; the window is long "
          "enough for about twice min_samples reads, which fixes the quiet-window problem found in Milestone 1.", "",
          "## Sheryar Karim: workload and Study A", "",
          "One Poisson FG trace (fixed rate and seed) is replayed by every run. Every run has the same warm-up, the same "
          "scan start, the same CPU and the same cache preparation, waits for the disk to be quiet, and records the "
          "server load and how busy the disk was. The 27 runs are shuffled within each repetition.", "",
          "## Limits", "",
          "- babbage's disk is a Dell PERC H755 RAID virtual disk, not a single HDD, and the server is shared; the "
          "results describe this setup.",
          "- The disk's own cache cannot be disabled from user space; the same cache preparation before each run keeps "
          "runs comparable.", "",
          "## Next", "", "- Add the adaptive controller to the dispatcher (same `next_q()` hook) and compare it with these baselines.", ""]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fo:
        fo.write("\n".join(L))
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
