#!/usr/bin/env python3
"""
run_study_bc.py - Milestone 3, Sheryar Karim (Study C with Mostafa Babaei).
Runs Study B and Study C on the server disk with the same set-up for every run.

Study B: adaptive, no-damping ablation and fixed q = 1, 2, 4, 8 on two traces
         (constant load, alternating quiet/busy), 3 repetitions   = 36 runs
Study C: (a) demanding overload trace, fixed q = 1, 2, 4, 8 and adaptive
         (b) alternating trace with a second chunk size (1 MiB), same policies
         2 repetitions each                                       = 20 runs
Settings: config/studies_m3.json (studies, traces), config/workload.json
(files, quota, warm-up, duration, CPU, cache preparation) and
config/adaptive.json / adaptive_nodamp.json (frozen controller settings).

Every policy replays the SAME trace file (identical offered requests), with the
same scan start, CPU, warm-up, window (1000 ms) and latency target (0.5 ms),
so fixed and adaptive runs are measured the same way. Inside each repetition
of each study the run order is shuffled.

Before every run (as in Milestone 2): read-only cache preparation, wait until
the disk is quiet (up to 60 s), check that there is enough free space.
After every run: requests.csv is compressed to requests.csv.gz (the analysis
reads it directly) because babbage's /home is shared and small.

Usage (from the milestone3 folder, after `make`):
    python3 scripts/run_study_bc.py --testdir ~/mt6289sproject/testdata --device /dev/sda \
        --confirm-shared-server-load
    ... --quick        # about 2 minutes, 6 short runs, only a check
    ... --resume logs/m3_<stamp>   # continue a stopped study, skipping finished runs
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "dispatcher")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from run_study_a import disk_busy, wait_idle, prepare_cache, git_commit  # noqa: E402,F401

MIN_FREE_GB = 3.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def trace_path(name, t, seconds):
    if "busy_rate" in t:
        return os.path.join(ROOT, "traces", f"alternating_{t['rate']:g}-{t['busy_rate']:g}rps_"
                                            f"{t['phase_s']:g}s_{seconds:g}s_seed{t['seed']}.csv")
    return os.path.join(ROOT, "traces", f"constant_{t['rate']:g}rps_{seconds:g}s_seed{t['seed']}.csv")


def make_trace(name, t, seconds, fg):
    path = trace_path(name, t, seconds)
    if not os.path.exists(path):
        cmd = [sys.executable, os.path.join(ROOT, "tools", "make_trace.py"), "--fg-file", fg,
               "--rate", str(t["rate"]), "--seconds", str(seconds), "--seed", str(t["seed"]), "--out", path]
        if "busy_rate" in t:
            cmd += ["--busy-rate", str(t["busy_rate"]), "--phase-s", str(t["phase_s"])]
        subprocess.run(cmd, check=True)
    return path


def free_gb(path):
    return shutil.disk_usage(path).free / 1e9


def gzip_file(path):
    with open(path, "rb") as src, gzip.open(path + ".gz", "xb", compresslevel=4) as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    os.remove(path)


def build_plan(cfg, quick, seed):
    rng = random.Random(seed)
    plan = []
    if quick:
        for study, trace, policy in cfg["quick"]["runs"]:
            plan.append({"study": study, "trace": trace, "policy": policy, "rep": 1})
        return plan
    for study, s in cfg["studies"].items():
        for rep in range(1, s["reps"] + 1):
            runs = [{"study": study, "trace": tr, "policy": p, "rep": rep}
                    for tr in s["traces"] for p in s["policies"]]
            rng.shuffle(runs)
            plan += runs
    return plan


def run_name(r):
    pol = r["policy"].replace("fixed:", "fixed_q")
    return f"{r['study']}_{r['trace']}_{pol}_rep{r['rep']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--testdir", required=True, help="folder with fg.dat and bg.dat")
    ap.add_argument("--device", default="", help="disk device, e.g. /dev/sda on babbage")
    ap.add_argument("--workload", default=os.path.join(ROOT, "config", "workload.json"))
    ap.add_argument("--studies", default=os.path.join(ROOT, "config", "studies_m3.json"))
    ap.add_argument("--quick", action="store_true", help="short check run, not for results")
    ap.add_argument("--resume", default=None, help="log folder of a stopped study to continue")
    ap.add_argument("--seed", type=int, default=3, help="seed for the run order")
    ap.add_argument("--only-rep", type=int, nargs="+", default=None,
                    help="run only these repetition numbers (e.g. 3 to add a third repetition to a study)")
    ap.add_argument("--confirm-shared-server-load", action="store_true",
                    help="confirm this sustained study is permitted on the shared server")
    a = ap.parse_args()
    if not a.confirm_shared_server_load:
        ap.error("add --confirm-shared-server-load to confirm the long study may run on the shared server")

    with open(a.workload) as f:
        w = json.load(f)
    with open(a.studies) as f:
        cfg = json.load(f)
    if a.quick:
        w.update({k: cfg["quick"][k] for k in ("warmup_s", "duration_s", "cache_flush_mib")})
    fg = os.path.join(a.testdir, w["fg_file"])
    bg = os.path.join(a.testdir, w["bg_file"])
    for p in (fg, bg, BIN):
        if not os.path.exists(p):
            sys.exit(f"missing {p} (make the test files and run `make` first)")
    if hasattr(os, "sched_getaffinity") and w["cpu"] >= 0 and w["cpu"] not in os.sched_getaffinity(0):
        sys.exit("Configured CPU is not in the allowed affinity mask")

    ctrl_files = {"adaptive": os.path.join(ROOT, "config", "adaptive.json"),
                  "adaptive_nodamp": os.path.join(ROOT, "config", "adaptive_nodamp.json")}
    for p in ctrl_files.values():
        with open(p) as f:
            k = json.load(f)
        if k.get("target_ms") != cfg["target_ms"] or k.get("window_ms") != cfg["window_ms"]:
            sys.exit(f"{p}: target_ms/window_ms differ from {a.studies}; the frozen settings must match")

    # Traces are always the full 130 s files, so quick runs replay the same traces.
    seconds = 10 + 120
    traces = {n: make_trace(n, t, seconds, fg) for n, t in cfg["traces"].items()}
    trace_sha = {n: sha256(p) for n, p in traces.items()}

    commit = git_commit()
    if a.resume:
        logroot = a.resume
        with open(os.path.join(logroot, "experiment.json")) as f:
            exp = json.load(f)
        plan, stamp, w, cfg = exp["order"], exp["stamp"], exp["workload"], exp["studies"]
        if exp["trace_sha256"] != trace_sha or exp["dispatcher_sha256"] != sha256(BIN):
            sys.exit("cannot resume: traces or dispatcher changed since the study started")
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
        logroot = os.path.join(ROOT, "logs", ("m3quick_" if a.quick else "m3_") + stamp)
        os.makedirs(logroot, exist_ok=False)
        plan = build_plan(cfg, a.quick, a.seed)
        if a.only_rep:
            plan = [r for r in plan if r["rep"] in a.only_rep]
        with open(os.path.join(logroot, "experiment.json"), "x") as f:
            json.dump({"stamp": stamp, "workload": w, "studies": cfg, "order": plan, "git_commit": commit,
                       "traces": {n: os.path.basename(p) for n, p in traces.items()},
                       "trace_sha256": trace_sha, "dispatcher_sha256": sha256(BIN),
                       "controller_configs": {n: json.load(open(p)) for n, p in ctrl_files.items()},
                       "platform": "Babbage shared RAID (Dell PERC H755); preliminary, not a single HDD",
                       "quick": a.quick, "seed": a.seed}, f, indent=2)

    est = len(plan) * (w["warmup_s"] + w["duration_s"] + 20) / 60
    print(f"Milestone 3 studies: {len(plan)} runs, about {est:.0f} minutes. Logs: {logroot}")
    done = failed = skipped = 0
    for i, r in enumerate(plan, 1):
        name = run_name(r)
        run_id = f"{stamp}_{name}"
        out = os.path.join(logroot, name)
        if os.path.exists(os.path.join(out, "run_meta.json")) and os.path.exists(os.path.join(out, "requests.csv.gz")):
            skipped += 1
            continue
        if os.path.exists(out):                    # half-finished run from a stop: keep it aside
            os.rename(out, out + f".incomplete_{int(time.time())}")
        if free_gb(logroot) < MIN_FREE_GB:
            print(f"STOPPED: less than {MIN_FREE_GB} GB free on {logroot}. Free space, then use --resume {logroot}")
            sys.exit(1)
        study = cfg["studies"][r["study"]]
        print(f"[{i}/{len(plan)}] {name}")
        preparation = prepare_cache(bg, w.get("cache_flush_mib", 0))
        busy = wait_idle(a.device)
        cmd = [BIN, "--mode", "mixed", "--fg", fg, "--bg", bg, "--trace", traces[r["trace"]],
               "--chunk", str(study["chunk_bytes"]),
               "--fg-quota", str(w["fg_quota"]), "--fg-cap", str(w["fg_queue_cap"]),
               "--bg-cap", str(w["bg_queue_cap"]),
               "--warmup-s", str(w["warmup_s"]), "--duration-s", str(w["duration_s"]),
               "--bg-start", str(w["bg_start_offset"]), "--cpu", str(w["cpu"]),
               "--run-id", run_id, "--group", r["study"], "--rep", str(r["rep"]),
               "--device", a.device or "unknown", "--git", commit, "--out", out,
               "--notes", f"trace {r['trace']}; disk busy before run: {busy:.0f} %"]
        if r["policy"].startswith("fixed:"):
            cmd += ["--policy", "fixed", "--q", r["policy"].split(":")[1],
                    "--window-ms", str(cfg["window_ms"]), "--target-ms", str(cfg["target_ms"])]
        else:
            cmd += ["--policy", r["policy"], "--ctrl-config", ctrl_files[r["policy"]]]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if not os.path.isdir(out):
            sys.exit("Dispatcher setup failed: " + p.stderr)
        with open(os.path.join(out, "terminal.log"), "x") as f:
            f.write(json.dumps(cmd) + "\n" + p.stdout + p.stderr)
        meta_path = os.path.join(out, "run_meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            meta.update(trace_sha256=trace_sha[r["trace"]], trace_name=r["trace"], study=r["study"],
                        policy_spec=r["policy"], cache_preparation=preparation,
                        requests_sha256=sha256(os.path.join(out, "requests.csv")))
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
        print("   " + (p.stderr.strip().splitlines() or ["(no output)"])[-1])
        if p.returncode != 0:
            failed += 1
            print(f"   FAILED (exit {p.returncode}). Logs kept in {out}. Fix, then: --resume {logroot}")
            break
        gzip_file(os.path.join(out, "requests.csv"))
        done += 1
        time.sleep(2)

    left = len(plan) - done - skipped - failed
    print(f"done: {done} OK, {skipped} already done, {failed} failed, {left} not run")
    print(f"next: python3 analysis/study_bc.py {logroot}")
    sys.exit(1 if failed or left else 0)


if __name__ == "__main__":
    main()
