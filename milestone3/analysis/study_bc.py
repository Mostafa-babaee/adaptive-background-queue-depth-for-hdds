#!/usr/bin/env python3
"""
study_bc.py - Milestone 3, Muhammad Ahmad Tariq (plots with Sheryar Karim,
integrity and CPU cost with Mostafa Babaei).
Analysis of Study B (adaptive vs. all fixed depths) and Study C (overload and
second chunk size) from the dispatcher logs.

Every run is first checked (analysis/validate_logs.py): accounting, every byte
verified, no errors, offered requests equal to the trace, q within the allowed
levels, and no BG read sent while bg_out >= q (safe limit reductions).

Per run (warm-up dropped): FG p50/p95/p99, target-miss fraction (0.5 ms),
rejected requests, scan MiB/s and bytes, mean q, time at each q, q changes,
direction reversals (oscillation), controller CPU per window, process CPU,
drains after q cuts. For the alternating trace also per phase (quiet / busy):
miss fraction and mean q, the reaction time (busy start -> first step down) and
the recovery time (busy end -> q back at its level before the busy phase).

Usage:
    python3 analysis/study_bc.py logs/m3_<stamp>
Outputs go to results/<log folder name>/ (summary.md, CSV tables, figures and
small per-run time series, so the slides do not need the raw logs).
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

from validate_logs import validate_run, read_trace  # noqa: E402

MIB = 1048576
GIB = 1 << 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICIES = ["fixed:1", "fixed:2", "fixed:4", "fixed:8", "adaptive", "adaptive_nodamp"]
LABEL = {"fixed:1": "fixed q=1", "fixed:2": "fixed q=2", "fixed:4": "fixed q=4", "fixed:8": "fixed q=8",
         "adaptive": "adaptive", "adaptive_nodamp": "no-damping ablation"}
COLOR = {"fixed:1": "#2a6f97", "fixed:2": "#61a5c2", "fixed:4": "#e09f3e", "fixed:8": "#9e2a2b",
         "adaptive": "#111111", "adaptive_nodamp": "#8e44ad"}
STUDY_NAME = {"B": "Study B", "C_overload": "Study C: overload", "C_chunk1m": "Study C: 1 MiB chunks"}


def policy_of(meta):
    if meta.get("policy_spec"):
        return meta["policy_spec"]
    return f"fixed:{meta['q']}" if meta.get("policy", "fixed") == "fixed" else meta["policy"]


def load_run(d):
    with open(os.path.join(d, "run_meta.json")) as f:
        meta = json.load(f)
    p = os.path.join(d, "requests.csv.gz")
    req = pd.read_csv(p if os.path.exists(p) else os.path.join(d, "requests.csv"))
    win = pd.read_csv(os.path.join(d, "windows.csv"))
    return meta, req, win


def phases_of(trace_cfg, total_s):
    """[(start_s, end_s, 'quiet'|'busy')] for an alternating trace, else None."""
    if not trace_cfg or "busy_rate" not in trace_cfg:
        return None
    out, t, busy = [], 0.0, False
    while t < total_s:
        out.append((t, min(total_s, t + trace_cfg["phase_s"]), "busy" if busy else "quiet"))
        t += trace_cfg["phase_s"]
        busy = not busy
    return out


def reversals(qs):
    d = [b - a for a, b in zip(qs, qs[1:]) if b != a]
    return sum(1 for x, y in zip(d, d[1:]) if (x > 0) != (y > 0))


def run_metrics(meta, req, win, target_ms, trace_cfg):
    warm, dur = meta["warmup_ns"], meta["duration_ns"]
    end = warm + dur
    fg = req[(req["class"] == "FG") & (req["t_arrival"] >= warm) & (req["t_arrival"] < end)]
    ok = fg[fg["status"] == "OK"]
    lat = (ok["t_complete"] - ok["t_arrival"]) / 1e6
    bg = req[(req["class"] == "BG") & (req["status"] == "OK") &
             (req["t_complete"] >= warm) & (req["t_complete"] < end)]
    w = win[(win["t_start"] >= warm) & (win["t_end"] <= end)].copy()
    qs = w["q_config"].tolist()
    span_s = (w["t_end"] - w["t_start"]).sum() / 1e9 if len(w) else math.nan
    m = {
        "run_id": meta["run_id"], "study": meta.get("study", meta.get("group")),
        "trace": meta.get("trace_name", "?"), "policy": policy_of(meta), "rep": meta["repetition"],
        "chunk_kib": meta["chunk_bytes"] // 1024,
        "fg_offered": len(fg), "fg_done": len(ok),
        "fg_p50_ms": lat.quantile(0.50) if len(ok) else math.nan,
        "fg_p95_ms": lat.quantile(0.95) if len(ok) else math.nan,
        "fg_p99_ms": lat.quantile(0.99) if len(ok) else math.nan,
        "miss_frac": float((lat > target_ms).mean()) if len(ok) else math.nan,
        "rejected": int((fg["status"] == "REJECTED").sum()),
        "errors": int((req["status"] == "ERR").sum()),
        "unverified": int(((req["status"] == "OK") & (req["verified"] != 1)).sum()),
        "scan_mib_s": bg["bytes_read"].sum() / MIB / (dur / 1e9),
        "scan_gib": bg["bytes_read"].sum() / GIB,
        "q_mean": float(np.mean(qs)) if qs else math.nan,
        "bg_out_mean": w["bg_out_mean"].mean() if len(w) else math.nan,
        "q_changes": int(sum(1 for a, b in zip(qs, qs[1:]) if a != b)),
        "reversals": reversals(qs),
        "reversals_per_min": reversals(qs) / (span_s / 60) if span_s else math.nan,
        "sparse_windows": int((w["action"] == "SPARSE").sum()) if "action" in w else 0,
        "fg_pending_mean": w["fg_pending_len"].mean() if len(w) else math.nan,
        "fg_pending_max": int(w["fg_pending_len"].max()) if len(w) else 0,
        "bg_pending_mean": w["bg_pending_len"].mean() if len(w) else math.nan,
        "ctrl_cpu_us_mean": w["ctrl_cpu_ns"].mean() / 1e3 if len(w) else math.nan,
        "ctrl_cpu_us_max": w["ctrl_cpu_ns"].max() / 1e3 if len(w) else math.nan,
        "process_cpu_s": (meta.get("cpu_cost", {}).get("process_user_ns", 0) +
                          meta.get("cpu_cost", {}).get("process_sys_ns", 0)) / 1e9,
        "reductions_below_out": meta.get("safe_reduction", {}).get("reductions_below_outstanding", 0),
        "drain_ms_max": meta.get("safe_reduction", {}).get("drain_ns_max", 0) / 1e6,
        "accounting_ok": bool(meta.get("accounting_ok")), "direct_io": meta.get("direct_io") is True,
    }
    for q in (1, 2, 4, 8):
        m[f"time_q{q}"] = float(np.mean([x == q for x in qs])) if qs else math.nan

    # small time series for plots and slides
    ts = pd.DataFrame({
        "t_s": (win["t_end"] / 1e9).round(3), "q": win["q_config"], "fg_samples": win["fg_samples"],
        "miss_frac": win["miss_frac"], "action": win.get("action", "HOLD"),
        "bg_out_mean": win["bg_out_mean"],
        "bg_out_max": win["bg_out_max"], "fg_pending": win["fg_pending_len"],
        "scan_gib": (win["scan_bytes_total"] / GIB).round(4),
    })
    ts["measured"] = (win["t_start"] >= warm) & (win["t_end"] <= end)

    phase_rows = []
    ph = phases_of(trace_cfg, end / 1e9)
    if ph:
        lat_t = ok["t_arrival"] / 1e9
        for kind in ("quiet", "busy"):
            sel = np.zeros(len(ok), bool)
            wsel = np.zeros(len(w), bool)
            for s, e, k in ph:
                if k == kind:
                    sel |= ((lat_t >= max(s, warm / 1e9)) & (lat_t < e)).values
                    wsel |= ((w["t_start"] / 1e9 >= s) & (w["t_end"] / 1e9 <= e)).values
            m[f"{kind}_miss_frac"] = float((lat[sel] > target_ms).mean()) if sel.any() else math.nan
            m[f"{kind}_q_mean"] = float(w["q_config"][wsel].mean()) if wsel.any() else math.nan
        # reaction and recovery at each transition inside the measured period
        wt = list(zip(win["t_start"] / 1e9, win["t_end"] / 1e9, win["q_config"], win.get("action", "HOLD")))
        for i, (s, e, k) in enumerate(ph):
            if s < warm / 1e9 or s == 0 or not m["policy"].startswith("adaptive"):
                continue
            q_before = next((q for a, b, q, _ in reversed(wt) if b <= s + 1e-9), None)
            if k == "busy":
                first_down = next((b for a, b, q, act in wt if a >= s - 1e-9 and b <= e + 1e-9 and act == "DOWN"), None)
                phase_rows.append({"run_id": m["run_id"], "policy": m["policy"], "rep": m["rep"],
                                   "transition_s": s, "kind": "quiet->busy",
                                   "reaction_s": (first_down - s) if first_down else math.nan,
                                   "recovery_s": math.nan, "q_before": q_before})
            else:
                # q level just before the previous busy phase began
                prev_busy_start = ph[i - 1][0]
                q_target = next((q for a, b, q, _ in reversed(wt) if b <= prev_busy_start + 1e-9), None)
                back = next((b for a, b, q, _ in wt if a >= s - 1e-9 and q_target is not None and q >= q_target), None)
                rec = 0.0 if (q_before is not None and q_target is not None and q_before >= q_target) else \
                    ((back - s) if back is not None and back <= e + 1e-9 else math.nan)
                phase_rows.append({"run_id": m["run_id"], "policy": m["policy"], "rep": m["rep"],
                                   "transition_s": s, "kind": "busy->quiet", "reaction_s": math.nan,
                                   "recovery_s": rec, "q_before": q_before})
        reacts = [r["reaction_s"] for r in phase_rows if r["kind"] == "quiet->busy"]
        m["reaction_s_mean"] = float(np.nanmean(reacts)) if any(not math.isnan(x) for x in reacts) else math.nan
        recs = [r["recovery_s"] for r in phase_rows if r["kind"] == "busy->quiet"]
        m["recovery_s_mean"] = float(np.nanmean(recs)) if recs and any(not math.isnan(x) for x in recs) else math.nan
        m["recovery_missed"] = int(sum(1 for x in recs if math.isnan(x)))
    return m, ts, phase_rows


def fmt(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def summarize(df):
    cols = ["fg_p50_ms", "fg_p99_ms", "miss_frac", "scan_mib_s", "scan_gib", "q_mean", "q_changes",
            "reversals_per_min", "rejected", "bg_out_mean", "fg_pending_mean", "fg_pending_max", "ctrl_cpu_us_mean", "ctrl_cpu_us_max", "process_cpu_s",
            "quiet_miss_frac", "busy_miss_frac", "quiet_q_mean", "busy_q_mean",
            "reaction_s_mean", "recovery_s_mean"]
    cols = [c for c in cols if c in df]
    g = df.groupby(["study", "trace", "policy"])[cols]
    s = g.mean().add_suffix("_mean").join(g.std().add_suffix("_sd")).join(
        df.groupby(["study", "trace", "policy"]).size().rename("reps"))
    return s.reset_index()


def best_fixed(summary, study, trace, miss_high):
    """Fixed depth with the highest scan rate whose mean miss fraction is within miss_high."""
    f = summary[(summary.study == study) & (summary.trace == trace) & summary.policy.str.startswith("fixed")]
    f = f[f.miss_frac_mean <= miss_high]
    return None if f.empty else f.sort_values("scan_mib_s_mean").iloc[-1]


def shade_phases(ax, ph, t0, t1):
    if ph:
        for s, e, k in ph:
            if k == "busy" and e > t0 and s < t1:
                ax.axvspan(max(s, t0), min(e, t1), color="#f3d5d5", alpha=0.6, lw=0)


def plot_timeseries(out, tsd, df, study, trace, ph, target, miss_high, fname):
    pols = [p for p in POLICIES if ((df.study == study) & (df.trace == trace) & (df.policy == p)).any()]
    if not pols:
        return
    fig, axs = plt.subplots(3, 1, figsize=(9, 7.5), sharex=True)
    for p in pols:
        row = df[(df.study == study) & (df.trace == trace) & (df.policy == p)].sort_values("rep").iloc[0]
        ts = tsd[row["run_id"]]
        ts = ts[ts.measured]
        lw = 2.2 if p.startswith("adaptive") else 1.2
        axs[0].step(ts.t_s, ts.q, where="post", color=COLOR[p], lw=lw, label=LABEL[p])
        axs[1].plot(ts.t_s, 100 * ts.miss_frac, color=COLOR[p], lw=lw, alpha=0.9)
        axs[2].plot(ts.t_s, ts.scan_gib - ts.scan_gib.iloc[0], color=COLOR[p], lw=lw)
    t0, t1 = min(v[v.measured].t_s.min() for v in tsd.values()), max(v[v.measured].t_s.max() for v in tsd.values())
    for ax in axs:
        shade_phases(ax, ph, t0 - 1, t1)
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("background q")
    axs[0].set_yscale("log", base=2)
    axs[0].set_yticks([1, 2, 4, 8], ["1", "2", "4", "8"])
    axs[1].axhline(100 * miss_high, ls=":", color="black", lw=1)
    axs[1].set_ylabel("target misses (%)")
    axs[1].set_ylim(bottom=0)
    axs[2].set_ylabel("cumulative scan (GiB)")
    axs[2].set_xlabel("time since start (s); warm-up dropped" + ("; shaded = busy phase" if ph else ""))
    axs[0].legend(loc="upper left", fontsize=8, ncol=3)
    axs[0].set_title(f"{STUDY_NAME.get(study, study)}, {trace} trace: q, target misses (> {target:g} ms) "
                     "and scan progress (repetition 1)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out, fname), dpi=150)
    plt.close(fig)


def plot_tradeoff(out, df, summary, study, traces, ycol, ylabel, fname, target=None, miss_high=None):
    traces = [t for t in traces if (summary.trace == t).any() and (summary.study == study).any()]
    if not traces:
        return
    fig, axs = plt.subplots(1, len(traces), figsize=(6.2 * len(traces), 4.4), squeeze=False)
    for ax, tr in zip(axs[0], traces):
        s = summary[(summary.study == study) & (summary.trace == tr)].set_index("policy")
        d = df[(df.study == study) & (df.trace == tr)]
        scale = 100 if ycol == "miss_frac" else 1
        for p in POLICIES:
            if p not in s.index:
                continue
            dd = d[d.policy == p]
            ax.scatter(dd.scan_mib_s, scale * dd[ycol], s=14, color=COLOR[p], alpha=0.35)
            x, y = s.loc[p, "scan_mib_s_mean"], scale * s.loc[p, f"{ycol}_mean"]
            ax.errorbar(x, y, xerr=s.loc[p, "scan_mib_s_sd"], yerr=scale * s.loc[p, f"{ycol}_sd"],
                        fmt="D" if p.startswith("adaptive") else "o", ms=8, color=COLOR[p], capsize=3,
                        label=LABEL[p])
        if ycol == "miss_frac" and miss_high is not None:
            ax.axhline(100 * miss_high, ls=":", color="black", lw=1)
        if ycol == "fg_p99_ms" and target is not None:
            ax.axhline(target, ls=":", color="black", lw=1)
        ax.set_title(f"{STUDY_NAME.get(study, study)}: {tr} trace", fontsize=10)
        ax.set_xlabel("Background scan throughput (MiB/s)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
    axs[0][0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, fname), dpi=150)
    plt.close(fig)


def plot_ablation(out, df, tsd, ph):
    d = df[(df.study == "B") & df.policy.isin(["adaptive", "adaptive_nodamp"])]
    if d.empty:
        return
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [2.2, 1]})
    for p in ("adaptive", "adaptive_nodamp"):
        r = d[(d.policy == p) & (d.trace == "alternating")].sort_values("rep")
        if r.empty:
            continue
        ts = tsd[r.iloc[0]["run_id"]]
        ts = ts[ts.measured]
        axs[0].step(ts.t_s, ts.q, where="post", color=COLOR[p], lw=2, label=LABEL[p])
    if len(axs[0].lines):
        shade_phases(axs[0], ph, axs[0].get_xlim()[0], axs[0].get_xlim()[1])
    axs[0].set_yscale("log", base=2)
    axs[0].set_yticks([1, 2, 4, 8], ["1", "2", "4", "8"])
    axs[0].set_xlabel("time since start (s); shaded = busy phase")
    axs[0].set_ylabel("background q")
    axs[0].set_title("Alternating trace: adaptive vs no damping (repetition 1)", fontsize=10)
    axs[0].legend(fontsize=8)
    axs[0].grid(alpha=0.3)
    traces = [t for t in ("constant", "alternating") if (d.trace == t).any()]
    x = np.arange(len(traces))
    for k, p in enumerate(("adaptive", "adaptive_nodamp")):
        g = d[d.policy == p].groupby("trace")["reversals_per_min"]
        vals = [g.mean().get(t, 0) for t in traces]
        sds = [g.std().get(t, 0) for t in traces]
        axs[1].bar(x + (k - 0.5) * 0.38, vals, 0.38, yerr=np.nan_to_num(sds), capsize=3, color=COLOR[p], label=LABEL[p])
    axs[1].set_xticks(x, traces)
    axs[1].set_ylabel("q direction reversals per minute")
    axs[1].set_title("Oscillation", fontsize=10)
    axs[1].grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "ablation_oscillation.png"), dpi=150)
    plt.close(fig)


def write_md(out, df, summary, phases, logdir, target, miss_high, cfg):
    L = ["# Milestone 3 results: Study B and Study C", "",
         f"Logs: `{logdir}`. Runs: {len(df)}. Warm-up dropped. Mean ± sd over repetitions. "
         f"Latency target {target:g} ms, window {cfg.get('window_ms', '?')} ms, a miss = FG read slower than the target.", ""]
    bad = df[(~df.accounting_ok) | (df.errors > 0) | (df.unverified > 0) | (~df.direct_io)]
    L += [f"**Integrity: {len(df) - len(bad)} of {len(df)} runs clean** (accounting OK, 0 errors, every byte "
          "verified, O_DIRECT, offered requests equal to the trace, no BG read sent while bg_out ≥ q).", ""]
    for study in ("B", "C_overload", "C_chunk1m"):
        s = summary[summary.study == study]
        if s.empty:
            continue
        L += [f"## {STUDY_NAME[study]}", ""]
        for tr in s.trace.unique():
            t = s[s.trace == tr].set_index("policy")
            L += [f"### {tr} trace", "",
                  "| Policy | reps | FG p50 ms | FG p99 ms | miss % | scan MiB/s | scan GiB | mean q | q changes | reversals/min | rejected |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
            for p in POLICIES:
                if p in t.index:
                    r = t.loc[p]
                    L.append(f"| {LABEL[p]} | {int(r.reps)} | {fmt(r.fg_p50_ms_mean)} | {fmt(r.fg_p99_ms_mean)} ± {fmt(r.fg_p99_ms_sd)} | "
                             f"{fmt(100 * r.miss_frac_mean, 1)} ± {fmt(100 * r.miss_frac_sd, 1)} | "
                             f"{fmt(r.scan_mib_s_mean, 0)} ± {fmt(r.scan_mib_s_sd, 0)} | {fmt(r.scan_gib_mean, 0)} | "
                             f"{fmt(r.q_mean_mean)} | {fmt(r.q_changes_mean, 1)} | {fmt(r.reversals_per_min_mean)} | {fmt(r.rejected_mean, 0)} |")
            L.append("")
            if "quiet_miss_frac_mean" in t and not t["quiet_miss_frac_mean"].isna().all():
                L += ["Per phase (alternating trace):", "",
                      "| Policy | quiet miss % | busy miss % | quiet mean q | busy mean q | reaction s | recovery s |",
                      "| --- | --- | --- | --- | --- | --- | --- |"]
                for p in POLICIES:
                    if p in t.index:
                        r = t.loc[p]
                        L.append(f"| {LABEL[p]} | {fmt(100 * r.quiet_miss_frac_mean, 1)} | {fmt(100 * r.busy_miss_frac_mean, 1)} | "
                                 f"{fmt(r.quiet_q_mean_mean)} | {fmt(r.busy_q_mean_mean)} | "
                                 f"{fmt(r.get('reaction_s_mean_mean', math.nan), 1)} | {fmt(r.get('recovery_s_mean_mean', math.nan), 1)} |")
                L += ["", "Reaction = busy phase starts → first step down. Recovery = busy phase ends → q back at "
                      "its level from before the busy phase. – = never happened in the phase.", ""]
            bf = best_fixed(summary, study, tr, miss_high)
            if "adaptive" in t.index:
                a = t.loc["adaptive"]
                if bf is not None:
                    L += [f"**Comparison:** the best fixed depth that keeps misses ≤ {100 * miss_high:g} % is "
                          f"{LABEL[bf.policy]} ({fmt(100 * bf.miss_frac_mean, 1)} % misses, {fmt(bf.scan_mib_s_mean, 0)} MiB/s). "
                          f"Adaptive: {fmt(100 * a.miss_frac_mean, 1)} % misses, {fmt(a.scan_mib_s_mean, 0)} MiB/s "
                          f"({fmt(100 * (a.scan_mib_s_mean / bf.scan_mib_s_mean - 1), 0)} % scan rate vs that fixed depth).", ""]
                else:
                    L += [f"**Comparison:** no fixed depth keeps misses ≤ {100 * miss_high:g} % on this trace. "
                          f"Adaptive: {fmt(100 * a.miss_frac_mean, 1)} % misses, {fmt(a.scan_mib_s_mean, 0)} MiB/s.", ""]
    L += ["## Actual depth and pending queues (Study B)", "",
          "| Trace | Policy | configured q (mean) | actual BG in flight (mean) | FG pending (mean / max) |",
          "| --- | --- | --- | --- | --- |"]
    for _, r in summary[summary.study == "B"].sort_values(["trace", "policy"]).iterrows():
        L.append(f"| {r.trace} | {LABEL[r.policy]} | {fmt(r.q_mean_mean)} | {fmt(r.bg_out_mean_mean)} | "
                 f"{fmt(r.fg_pending_mean_mean)} / {fmt(r.fg_pending_max_mean, 0)} |")
    L.append("")
    ad = df[df.policy.str.startswith("adaptive")]
    if not ad.empty:
        L += ["## Controller CPU cost and safe reductions", "",
              f"- Controller decision: mean {fmt(ad.ctrl_cpu_us_mean.mean())} µs per window, "
              f"max {fmt(ad.ctrl_cpu_us_max.max())} µs (one decision per {cfg.get('window_ms', '?')} ms window).",
              f"- Whole dispatcher process CPU per run: adaptive {fmt(ad.process_cpu_s.mean(), 1)} s, "
              f"fixed {fmt(df[~df.policy.str.startswith('adaptive')].process_cpu_s.mean(), 1)} s.",
              f"- Cuts of q below the reads already in flight: {int(ad.reductions_below_out.sum())} in total; "
              f"longest drain {fmt(ad.drain_ms_max.max(), 3)} ms; in every run no BG read was sent while bg_out ≥ q.", ""]
    nd = summary[(summary.study == "B") & summary.policy.isin(["adaptive", "adaptive_nodamp"])]
    if not nd.empty:
        L += ["## Diagnosis: oscillation and recovery (adaptive vs no-damping ablation)", "",
              "| Trace | Policy | q changes | reversals/min | time at q=1/2/4/8 (%) | miss % | scan MiB/s |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for _, r in nd.sort_values(["trace", "policy"]).iterrows():
            d = df[(df.study == "B") & (df.trace == r.trace) & (df.policy == r.policy)]
            tq = "/".join(fmt(100 * d[f"time_q{q}"].mean(), 0) for q in (1, 2, 4, 8))
            L.append(f"| {r.trace} | {LABEL[r.policy]} | {fmt(r.q_changes_mean, 1)} | {fmt(r.reversals_per_min_mean)} | "
                     f"{tq} | {fmt(100 * r.miss_frac_mean, 1)} | {fmt(r.scan_mib_s_mean, 0)} |")
        L += ["", "A reversal is q going up then down (or down then up). Many reversals = oscillation.", ""]
    L += ["Figures: `B_constant_timeseries.png`, `B_alternating_timeseries.png`, `B_tradeoff_miss.png`, "
          "`B_tradeoff_p99.png`, `ablation_oscillation.png`, `C_overload.png`, `C_chunk1m.png`, "
          "`C_chunk1m_timeseries.png`, `C_overload_timeseries.png`.", "",
          "Platform note: all runs use only the course server (babbage). Its disk is a shared Dell PERC H755 "
          "RAID virtual disk. The 0.5 ms target was frozen from Study A (Milestone 2) on the same server, "
          "before these evaluation runs."]
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logdir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--trace-dir", default=os.path.join(ROOT, "traces"))
    a = ap.parse_args()

    with open(os.path.join(a.logdir, "experiment.json")) as f:
        exp = json.load(f)
    cfg = exp["studies"]
    target = cfg["target_ms"]
    miss_high = exp["controller_configs"]["adaptive"]["miss_high"]
    dirs = sorted(d for d in glob.glob(os.path.join(a.logdir, "*"))
                  if os.path.isdir(d) and ".incomplete_" not in d and os.path.exists(os.path.join(d, "run_meta.json")))
    if not dirs:
        raise SystemExit(f"no runs in {a.logdir}")
    rows, tsd, phase_rows = [], {}, []
    for d in dirs:
        meta, req, win = load_run(d)
        trace = read_trace(meta, a.trace_dir)
        problems = validate_run(meta, req, win, trace)
        if problems:
            raise SystemExit(f"Invalid run {d}: " + "; ".join(problems))
        if meta.get("target_ms") != target:
            raise SystemExit(f"{d}: target_ms {meta.get('target_ms')} differs from {target}")
        m, ts, ph = run_metrics(meta, req, win, target, cfg["traces"].get(meta.get("trace_name")))
        rows.append(m)
        tsd[m["run_id"]] = ts
        phase_rows += ph
        print(f"ok  {os.path.basename(d)}  p99 {fmt(m['fg_p99_ms'])} ms  miss {fmt(100 * m['miss_frac'], 1)} %  "
              f"scan {fmt(m['scan_mib_s'], 0)} MiB/s  mean q {fmt(m['q_mean'])}")
        del req, win, trace
    df = pd.DataFrame(rows)
    summary = summarize(df)

    out = a.out or os.path.join(ROOT, "results", os.path.basename(os.path.normpath(a.logdir)))
    os.makedirs(os.path.join(out, "timeseries"), exist_ok=True)
    df.to_csv(os.path.join(out, "runs.csv"), index=False)
    summary.to_csv(os.path.join(out, "summary.csv"), index=False)
    pd.DataFrame(phase_rows).to_csv(os.path.join(out, "phases.csv"), index=False)
    for rid, ts in tsd.items():
        ts.to_csv(os.path.join(out, "timeseries", f"{rid}.csv"), index=False)

    alt = phases_of(cfg["traces"].get("alternating"), 130)
    plot_timeseries(out, tsd, df, "B", "constant", None, target, miss_high, "B_constant_timeseries.png")
    plot_timeseries(out, tsd, df, "B", "alternating", alt, target, miss_high, "B_alternating_timeseries.png")
    plot_timeseries(out, tsd, df, "C_chunk1m", "alternating", alt, target, miss_high, "C_chunk1m_timeseries.png")
    plot_timeseries(out, tsd, df, "C_overload", "overload", None, target, miss_high, "C_overload_timeseries.png")
    plot_tradeoff(out, df, summary, "B", ["constant", "alternating"], "miss_frac",
                  f"Target misses (% of FG reads > {target:g} ms)", "B_tradeoff_miss.png", miss_high=miss_high)
    plot_tradeoff(out, df, summary, "B", ["constant", "alternating"], "fg_p99_ms",
                  "Foreground p99 latency (ms)", "B_tradeoff_p99.png", target=target)
    plot_tradeoff(out, df, summary, "C_overload", ["overload"], "miss_frac",
                  f"Target misses (% > {target:g} ms)", "C_overload.png", miss_high=miss_high)
    plot_tradeoff(out, df, summary, "C_chunk1m", ["alternating"], "miss_frac",
                  f"Target misses (% > {target:g} ms)", "C_chunk1m.png", miss_high=miss_high)
    plot_ablation(out, df, tsd, alt)
    write_md(out, df, summary, phase_rows, a.logdir, target, miss_high, cfg)
    print(open(os.path.join(out, "summary.md")).read())
    print(f"outputs in {out}")


if __name__ == "__main__":
    main()
