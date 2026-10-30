#!/usr/bin/env python3
"""
run_study_a.py - Milestone 2, Sheryar Karim.
Runs Study A (fixed-depth baselines) on the server disk with the same set-up for every run.

For each repetition (default 3) it runs, in a shuffled order:
    foreground alone            (FG trace only, no scan)
    scanner alone   at q = 1, 2, 4, 8
    combined        at q = 1, 2, 4, 8   (FG trace + scan)
= 27 runs for 3 repetitions. Every run uses the SAME trace file, the same
scan start offset, the same CPU, the same warm-up and the same cache preparation.

Before every run:
  1. cache preparation: read the far end of bg.dat (cache_flush_mib) with O_DIRECT,
     as a common read-only preparation; this does not guarantee identical
     hardware cache contents and does not change global cache settings
  2. idle check: wait (up to 60 s) until the disk is idle (busy < 5 %) for 3 s;
     babbage is shared, so the busy level is written to run_meta.json notes
  3. record the 1-minute load average (the dispatcher writes it to run_meta.json)

Usage (from the code/ folder, after `make`):
    python3 scripts/run_study_a.py --testdir ~/mt6289sproject/testdata --device /dev/sda
    python3 scripts/run_study_a.py --testdir ... --quick      # 2-minute check, not for results
"""
import argparse
import datetime as dt
import json
import os
import random
import hashlib
import uuid
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "dispatcher")
QS = (1, 2, 4, 8)


def sh(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


def git_commit():
    p = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return p.stdout.strip() or "unknown"


def disk_busy(device, seconds=1.0):
    """Percent of time the device was busy, from /proc/diskstats."""
    name = os.path.basename(device) if device else None
    if not name:
        return 0.0

    def ticks():
        with open("/proc/diskstats") as f:
            for line in f:
                p = line.split()
                if p[2] == name:
                    return int(p[12])                      # ms spent doing I/O
        return None

    a = ticks()
    if a is None:
        return 0.0
    time.sleep(seconds)
    b = ticks()
    return 100.0 * (b - a) / (seconds * 1000.0)


def wait_idle(device, limit=5.0, need=3, max_wait=60):
    ok, start = 0, time.time()
    while ok < need:
        busy = disk_busy(device)
        ok = ok + 1 if busy < limit else 0
        if time.time() - start > max_wait:
            print(f"   note: disk still {busy:.0f} % busy after {max_wait} s (shared server); running anyway")
            return busy
    return 0.0


def prepare_cache(bg_path, flush_mib):
    """Read-only common preparation. No global cache changes, no sudo."""
    if flush_mib <= 0:
        return {'method': 'none', 'success': True, 'global_cache_flush': False}
    size = os.path.getsize(bg_path)
    skip = max(0, size // (1 << 20) - flush_mib)
    result = subprocess.run(['dd', 'if=' + bg_path, 'of=/dev/null', 'bs=1M',
                             'count=' + str(flush_mib), 'skip=' + str(skip), 'iflag=direct'],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Read-only preparation failed: ' + result.stderr)
    return {'method': 'direct-read-tail', 'mib': flush_mib, 'success': True,
            'global_cache_flush': False, 'hardware_cache_state_guaranteed': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--testdir", required=True, help="folder with fg.dat and bg.dat")
    ap.add_argument("--device", default="", help="disk device, e.g. /dev/sda on babbage (for the idle check and logs)")
    ap.add_argument("--workload", default=os.path.join(ROOT, "config", "workload.json"))
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--group", default="studyA")
    ap.add_argument("--quick", action="store_true", help="short check run, not for results")
    ap.add_argument("--seed", type=int, default=1, help="seed for the run order")
    ap.add_argument('--confirm-shared-server-load', action='store_true',
                    help='Confirm this sustained uncapped study is permitted on the shared server')
    a = ap.parse_args()
    if not a.confirm_shared_server_load:
        ap.error('Confirm the permitted test directory and sustained workload before using --confirm-shared-server-load')
    if a.reps is not None and a.reps < 1:
        ap.error('--reps must be positive')

    with open(a.workload) as f:
        w = json.load(f)
    if a.quick:
        w.update(warmup_s=2, duration_s=8, cache_flush_mib=64)
        a.group = a.group + "_quick"
    reps = a.reps or (1 if a.quick else w.get("repetitions", 3))
    fg = os.path.join(a.testdir, w["fg_file"])
    bg = os.path.join(a.testdir, w["bg_file"])
    for p in (fg, bg, BIN):
        if not os.path.exists(p):
            sys.exit(f"missing {p} (make the test files and run `make` first)")

    seconds = w["warmup_s"] + w["duration_s"]
    if hasattr(os, 'sched_getaffinity') and w['cpu'] >= 0 and w['cpu'] not in os.sched_getaffinity(0):
        sys.exit('Configured CPU is not in the allowed affinity mask; choose an allowed CPU consistently.')
    trace = os.path.join(ROOT, "traces", f"constant_{w['fg_rate']:g}rps_{seconds:g}s_seed{w['trace_seed']}.csv")
    if not os.path.exists(trace):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_trace.py"), "--fg-file", fg,
                        "--rate", str(w["fg_rate"]), "--seconds", str(seconds),
                        "--seed", str(w["trace_seed"]), "--out", trace], check=True)

    if not a.group or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.group):
        ap.error('--group must be a simple name')
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + '_' + uuid.uuid4().hex[:8]
    logroot = os.path.join(ROOT, 'logs', a.group + '_' + stamp)
    os.makedirs(logroot, exist_ok=False)
    rng = random.Random(a.seed)
    plan = []
    for rep in range(1, reps + 1):
        runs = [("fg", None)] + [("bg", q) for q in QS] + [("mixed", q) for q in QS]
        rng.shuffle(runs)
        plan += [(rep, m, q) for m, q in runs]

    est = len(plan) * (seconds + 20) / 60
    print(f"Study A: {len(plan)} runs, about {est:.0f} minutes. Logs: {logroot}")
    commit = git_commit()
    trace_sha = hashlib.sha256(open(trace, 'rb').read()).hexdigest()
    with open(os.path.join(logroot, 'experiment.json'), 'x') as f:
        json.dump({'configuration': w, 'order': plan, 'git_commit': commit,
                   'trace_sha256': trace_sha, 'platform': 'Babbage shared RAID; preliminary',
                   'dispatcher_sha256': hashlib.sha256(open(BIN, 'rb').read()).hexdigest(),
                   'quick': a.quick, 'seed': a.seed}, f, indent=2)
    failed = 0
    for i, (rep, mode, q) in enumerate(plan, 1):
        name = f"{mode}_alone" if mode == "fg" else (f"bg_alone_q{q}" if mode == "bg" else f"mixed_q{q}")
        run_id = f"{stamp}_{name}_rep{rep}"
        out = os.path.join(logroot, run_id)
        if os.path.exists(out):
            raise RuntimeError('Refusing existing output directory: ' + out)
        print(f"[{i}/{len(plan)}] {run_id}")
        preparation = prepare_cache(bg, w.get("cache_flush_mib", 0))
        busy = wait_idle(a.device)
        cmd = [BIN, "--mode", mode, "--fg", fg, "--bg", bg, "--trace", trace,
               "--q", str(q or 1), "--chunk", str(w["chunk_bytes"]),
               "--fg-quota", str(w["fg_quota"]), "--fg-cap", str(w["fg_queue_cap"]),
               "--bg-cap", str(w["bg_queue_cap"]), "--window-ms", str(w["window_ms"]),
               "--warmup-s", str(w["warmup_s"]), "--duration-s", str(w["duration_s"]),
               "--bg-start", str(w["bg_start_offset"]), "--cpu", str(w["cpu"]),
               "--run-id", run_id, "--group", a.group, "--rep", str(rep),
               "--device", a.device or "unknown", "--git", commit, "--out", out,
               "--notes", f"disk busy before run: {busy:.0f} %"]
        if w.get("target_ms"):
            cmd += ["--target-ms", str(w["target_ms"])]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if not os.path.isdir(out):
            sys.exit('Dispatcher setup failed: ' + p.stderr)
        with open(os.path.join(out, 'terminal.log'), 'x') as f:
            f.write(json.dumps(cmd) + '\n' + p.stdout + p.stderr)
        meta_path = os.path.join(out, 'run_meta.json')
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            meta.update(trace_sha256=trace_sha, cache_preparation=preparation)
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        print("   " + (p.stderr.strip().splitlines() or ["(no output)"])[-1])
        if p.returncode != 0:
            failed += 1
            print(f"   FAILED (exit {p.returncode})")
            break
        time.sleep(2)

    print(f"done: {i - failed} OK, {failed} failed, {len(plan) - i} not run")
    print(f"next: python3 analysis/study_a.py {logroot}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
