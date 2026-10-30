#!/usr/bin/env python3
"""
study_a.py - Milestone 2, Muhammad Ahmad Tariq.
Analysis of Study A (fixed-depth baselines) from the dispatcher logs.

Per run (warm-up dropped, only the measured period counts):
  FG p50 / p95 / p99 latency (arrival -> complete), wait (arrival -> submit),
  service (submit -> complete), target-miss fraction, rejected requests,
  errors, unverified reads, scanner MiB/s, completed scan bytes,
  configured q and ACTUAL outstanding background reads (mean and max),
  controller CPU cost.

Then: mean and standard deviation over repetitions for every (mode, q), the
required figure (FG p99 vs scan throughput), latency CDFs, configured vs actual
depth, and the frozen latency target and controller settings.

Usage:
    python3 analysis/study_a.py logs/studyA                 # summary + plots + target
    python3 analysis/study_a.py logs/studyA --freeze        # also write config/adaptive.json
Outputs go to results/<log folder name>/.
"""
import argparse
import glob
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MIB = 1048576
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QS = (1, 2, 4, 8)
COLORS = {1: "#2a6f97", 2: "#61a5c2", 4: "#e09f3e", 8: "#9e2a2b"}


def load_run(d):
    with open(os.path.join(d, "run_meta.json")) as f:
        meta = json.load(f)
    req = pd.read_csv(os.path.join(d, "requests.csv"))
    win = pd.read_csv(os.path.join(d, "windows.csv"))
    return meta, req, win


def run_metrics(meta, req, win, target_ms):
    warm, dur = meta["warmup_ns"], meta["duration_ns"]
    end = warm + dur
    fg = req[(req["class"] == "FG") & (req["t_arrival"] >= warm) & (req["t_arrival"] < end)]
    ok = fg[fg["status"] == "OK"]
    lat = (ok["t_complete"] - ok["t_arrival"]) / 1e6
    wait = (ok["t_submit"] - ok["t_arrival"]) / 1e6
    svc = (ok["t_complete"] - ok["t_submit"]) / 1e6
    bg = req[(req["class"] == "BG") & (req["status"] == "OK") &
             (req["t_complete"] >= warm) & (req["t_complete"] < end)]
    w = win[(win["t_start"] >= warm) & (win["t_end"] <= end)]
    mode = meta["mode"]
    m = {
        "run_id": meta["run_id"], "mode": mode,
        "q": meta["q"] if mode != "fg" else 0, "rep": meta["repetition"],
        "fg_offered": len(fg), "fg_done": len(ok),
        "fg_p50_ms": lat.quantile(0.50) if len(ok) else math.nan,
        "fg_p95_ms": lat.quantile(0.95) if len(ok) else math.nan,
        "fg_p99_ms": lat.quantile(0.99) if len(ok) else math.nan,
        "fg_mean_ms": lat.mean() if len(ok) else math.nan,
        "wait_p99_ms": wait.quantile(0.99) if len(ok) else math.nan,
        "service_p99_ms": svc.quantile(0.99) if len(ok) else math.nan,
        "miss_frac": float((lat > target_ms).mean()) if (target_ms and len(ok)) else math.nan,
        "rejected": int((fg["status"] == "REJECTED").sum()),
        "errors": int((req["status"] == "ERR").sum()),
        "unverified": int(((req["status"] == "OK") & (req["verified"] != 1)).sum()),
        "scan_mib_s": bg["len"].sum() / MIB / (dur / 1e9),
        "scan_bytes": int(bg["len"].sum()),
        "bg_out_mean": w["bg_out_mean"].mean() if len(w) else math.nan,
        "bg_out_max": int(w["bg_out_max"].max()) if len(w) else 0,
        "ctrl_cpu_us": w["ctrl_cpu_ns"].mean() / 1e3 if len(w) else math.nan,
        "accounting_ok": bool(meta.get("accounting_ok", False)),
        "direct_io": bool(meta.get("direct_io", True)),
        "lat_ms": lat.values,
    }
    return m


def summarize(runs):
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "lat_ms"} for r in runs])
    cols = ["fg_p50_ms", "fg_p99_ms", "wait_p99_ms", "service_p99_ms", "miss_frac",
            "scan_mib_s", "bg_out_mean", "rejected", "errors"]
    g = df.groupby(["mode", "q"])[cols]
    s = g.mean().add_suffix("_mean").join(g.std().add_suffix("_sd")).join(df.groupby(["mode", "q"]).size().rename("reps"))
    return df, s.reset_index()


def fmt(x, nd=2):
    return "–" if (x is None or (isinstance(x, float) and math.isnan(x))) else f"{x:.{nd}f}"


def choose_target(summary, rate):
    """Frozen target: 1.25 x the mean p99 of the combined run at q = 1, rounded up
    to 0.5 ms. q = 1 is the gentlest scan, so the target is reachable while
    scanning, and larger fixed depths show whether they miss it."""
    row = summary[(summary["mode"] == "mixed") & (summary["q"] == 1)]
    if row.empty or math.isnan(row["fg_p99_ms_mean"].iloc[0]):
        return None
    target = math.ceil(1.25 * row["fg_p99_ms_mean"].iloc[0] * 2) / 2
    min_samples = 25
    window_ms = max(500, int(math.ceil(1000 * min_samples * 2 / rate / 250.0)) * 250)
    return {"target_ms": target, "window_ms": window_ms, "min_samples": min_samples,
            "miss_high": 0.05, "miss_low": 0.01, "up_windows": 3}


def plots(out, runs, summary, target):
    mixed = summary[summary["mode"] == "mixed"].set_index("q")
    alone_bg = summary[summary["mode"] == "bg"].set_index("q")
    fg_alone = summary[summary["mode"] == "fg"]

    # 1. required figure: FG p99 vs scan throughput
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for r in runs:
        if r["mode"] == "mixed":
            ax.scatter(r["scan_mib_s"], r["fg_p99_ms"], s=18, color=COLORS[r["q"]], alpha=0.35)
    for q in QS:
        if q in mixed.index:
            x, y = mixed.loc[q, "scan_mib_s_mean"], mixed.loc[q, "fg_p99_ms_mean"]
            ax.errorbar(x, y, xerr=mixed.loc[q, "scan_mib_s_sd"], yerr=mixed.loc[q, "fg_p99_ms_sd"],
                        fmt="o", ms=9, color=COLORS[q], capsize=4, label=f"fixed q={q}")
            ax.annotate(f"q={q}", (x, y), textcoords="offset points", xytext=(8, 6), fontsize=10)
    if not fg_alone.empty:
        ax.axhline(fg_alone["fg_p99_ms_mean"].iloc[0], ls="--", color="gray", lw=1)
        ax.text(ax.get_xlim()[0], fg_alone["fg_p99_ms_mean"].iloc[0], "  foreground alone", va="bottom",
                color="gray", fontsize=9)
    if target:
        ax.axhline(target["target_ms"], ls=":", color="black", lw=1)
        ax.text(ax.get_xlim()[1], target["target_ms"], f"target {target['target_ms']:g} ms  ", va="bottom",
                ha="right", fontsize=9)
    ys = [mixed.loc[q, "fg_p99_ms_mean"] for q in QS if q in mixed.index]
    if ys and min(ys) > 0 and max(ys) / min(ys) > 10:
        ax.set_yscale("log")
    ax.set_xlabel("Background scan throughput (MiB/s)")
    ax.set_ylabel("Foreground p99 latency (ms)")
    ax.set_title("Study A: foreground p99 vs scan throughput (mean ± sd, dots = runs)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "studyA_tradeoff.png"), dpi=160)
    plt.close(fig)

    # 2. scan throughput: alone vs with foreground
    fig, ax = plt.subplots(figsize=(7, 3.8))
    xs = np.arange(len(QS))
    for off, src, lab, col in ((-0.2, alone_bg, "scanner alone", "#9aa5b1"), (0.2, mixed, "with foreground", "#9e2a2b")):
        vals = [src.loc[q, "scan_mib_s_mean"] if q in src.index else 0 for q in QS]
        sds = [src.loc[q, "scan_mib_s_sd"] if q in src.index else 0 for q in QS]
        ax.bar(xs + off, vals, 0.4, yerr=sds, capsize=3, label=lab, color=col)
    ax.set_xticks(xs, [f"q={q}" for q in QS])
    ax.set_ylabel("Scan throughput (MiB/s)")
    ax.set_title("Scan throughput at each fixed depth")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "studyA_scan_throughput.png"), dpi=160)
    plt.close(fig)

    # 3. latency CDF (all repetitions pooled)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    groups = [("foreground alone", [r for r in runs if r["mode"] == "fg"], "gray")] + \
             [(f"with scan, q={q}", [r for r in runs if r["mode"] == "mixed" and r["q"] == q], COLORS[q]) for q in QS]
    for lab, rs, col in groups:
        if rs:
            lat = np.sort(np.concatenate([r["lat_ms"] for r in rs]))
            if len(lat):
                ax.plot(lat, np.arange(1, len(lat) + 1) / len(lat), label=lab, color=col)
    if target:
        ax.axvline(target["target_ms"], ls=":", color="black", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("Foreground latency (ms, log scale)")
    ax.set_ylabel("Fraction of reads")
    ax.set_title("Foreground latency distribution")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "studyA_latency_cdf.png"), dpi=160)
    plt.close(fig)

    # 4. configured vs actual outstanding background reads
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for src, lab, mk in ((alone_bg, "scanner alone", "s"), (mixed, "with foreground", "o")):
        qs = [q for q in QS if q in src.index]
        ax.plot(qs, [src.loc[q, "bg_out_mean_mean"] for q in qs], marker=mk, label=lab)
    ax.plot(QS, QS, ls="--", color="gray", lw=1, label="configured q")
    ax.set_xticks(QS)
    ax.set_xlabel("Configured q")
    ax.set_ylabel("Actual outstanding (mean)")
    ax.set_title("Configured vs actual depth")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "studyA_actual_depth.png"), dpi=160)
    plt.close(fig)


def write_md(out, df, summary, target, logdir):
    L = ["# Study A results (fixed-depth baselines)", "",
         f"Logs: `{logdir}`. Runs: {len(df)}. Warm-up dropped. Values are mean ± sd over repetitions.", ""]
    bad = df[(~df["accounting_ok"]) | (df["errors"] > 0) | (df["unverified"] > 0) | (~df["direct_io"])]
    L += [f"Integrity: {len(df) - len(bad)} of {len(df)} runs clean (accounting OK, 0 errors, all bytes verified, O_DIRECT)."
          + ("" if bad.empty else " **Check: " + ", ".join(bad["run_id"]) + "**"), ""]
    L += ["| Run type | q | reps | FG p50 ms | FG p99 ms | wait p99 ms | service p99 ms | miss % | scan MiB/s | actual depth | rejected |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    names = {"fg": "foreground alone", "bg": "scanner alone", "mixed": "combined"}
    for _, r in summary.sort_values(["mode", "q"]).iterrows():
        q = "–" if r["mode"] == "fg" else int(r["q"])
        L.append(f"| {names[r['mode']]} | {q} | {int(r['reps'])} | {fmt(r['fg_p50_ms_mean'])} | "
                 f"{fmt(r['fg_p99_ms_mean'])} ± {fmt(r['fg_p99_ms_sd'])} | {fmt(r['wait_p99_ms_mean'])} | "
                 f"{fmt(r['service_p99_ms_mean'])} | {fmt(100 * r['miss_frac_mean'], 1)} | "
                 f"{fmt(r['scan_mib_s_mean'], 1)} ± {fmt(r['scan_mib_s_sd'], 1)} | {fmt(r['bg_out_mean_mean'])} | "
                 f"{fmt(r['rejected_mean'], 0)} |")
    L += [""]
    if target:
        L += ["## Frozen latency target and controller settings", "",
              f"- **target_ms = {target['target_ms']:g}** (1.25 × mean p99 of the combined run at q = 1, rounded up to 0.5 ms)",
              f"- window_ms = {target['window_ms']}, min_samples = {target['min_samples']} "
              "(a window holds about twice min_samples at the trace rate, so quiet windows are not sparse)",
              f"- miss_high = {target['miss_high']}, miss_low = {target['miss_low']}, up_windows = {target['up_windows']}", ""]
    L += ["Figures: `studyA_tradeoff.png` (required), `studyA_scan_throughput.png`, "
          "`studyA_latency_cdf.png`, `studyA_actual_depth.png`."]
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logdir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--target-ms", type=float, default=None, help="use this target instead of choosing one")
    ap.add_argument("--freeze", action="store_true", help="write the chosen settings to config/adaptive.json")
    a = ap.parse_args()

    dirs = sorted(d for d in glob.glob(os.path.join(a.logdir, "*")) if os.path.exists(os.path.join(d, "run_meta.json")))
    if not dirs:
        raise SystemExit(f"no runs in {a.logdir}")
    loaded = [load_run(d) for d in dirs]
    rate = None
    tr = [m for m, _, _ in loaded if m["mode"] != "bg" and m.get("trace_requests")]
    if tr:
        rate = tr[0]["trace_requests"] / ((tr[0]["warmup_ns"] + tr[0]["duration_ns"]) / 1e9)

    # pass 1 without a target, to choose it; pass 2 with the target for miss fractions
    runs = [run_metrics(m, r, w, None) for m, r, w in loaded]
    _, summary = summarize(runs)
    target = {"target_ms": a.target_ms, "window_ms": 1000, "min_samples": 25, "miss_high": 0.05,
              "miss_low": 0.01, "up_windows": 3} if a.target_ms else choose_target(summary, rate or 50)
    if target:
        runs = [run_metrics(m, r, w, target["target_ms"]) for m, r, w in loaded]
    df, summary = summarize(runs)

    out = a.out or os.path.join(ROOT, "results", os.path.basename(os.path.normpath(a.logdir)))
    os.makedirs(out, exist_ok=True)
    df.to_csv(os.path.join(out, "runs.csv"), index=False)
    summary.to_csv(os.path.join(out, "summary.csv"), index=False)
    plots(out, runs, summary, target)
    write_md(out, df, summary, target, a.logdir)
    if target:
        with open(os.path.join(out, "target.json"), "w") as f:
            json.dump(target, f, indent=2)
    if a.freeze and target:
        p = os.path.join(ROOT, "config", "adaptive.json")
        with open(p) as f:
            cfg = json.load(f)
        cfg.update(target)
        cfg["_note"] = f"Frozen from Study A ({os.path.basename(os.path.normpath(a.logdir))}); do not tune on final runs"
        with open(p, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"froze settings in {p}")
    print(open(os.path.join(out, "summary.md")).read())
    print(f"outputs in {out}")


if __name__ == "__main__":
    main()
