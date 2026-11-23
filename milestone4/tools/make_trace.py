#!/usr/bin/env python3
"""
make_trace.py - Milestone 2 and 3, Sheryar Karim.
Workload generator: writes a fixed foreground (FG) arrival trace.

Milestone 3 adds the alternating quiet/busy trace: --busy-rate R --phase-s S
gives S seconds at --rate (quiet), then S seconds at R (busy), and so on,
starting quiet at t = 0. Arrivals inside each phase are Poisson.

Every policy and every repetition replays the SAME trace file, so all runs get
identical offered requests (same arrival times, same offsets).

Arrivals are a Poisson process (random gaps with a fixed mean rate) from a
fixed seed. Each FG request reads one random 4 KiB block of the FG test file.

Output: CSV with header 't_ns,offset'. t_ns is nanoseconds since run start
(warm-up included), offset is bytes (4 KiB aligned).

Usage:
    python3 tools/make_trace.py --fg-file /path/fg.dat --rate 100 \
        --seconds 130 --seed 42 --out traces/constant_100rps.csv
    python3 tools/make_trace.py --fg-file /path/fg.dat --rate 50 --busy-rate 200 \
        --phase-s 20 --seconds 130 --seed 43 --out traces/alternating.csv
    # --fg-bytes N can replace --fg-file when the file is not on this machine
"""
import argparse
import os
import random
import math
import sys

BLOCK = 4096


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fg-file", help="FG test file (its size sets the offset range)")
    ap.add_argument("--fg-bytes", type=int, help="FG file size in bytes, instead of --fg-file")
    ap.add_argument("--rate", type=float, required=True, help="mean FG arrivals per second")
    ap.add_argument("--seconds", type=float, required=True, help="trace length = warm-up + duration")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--busy-rate", type=float, default=None, help="busy-phase rate (alternating trace)")
    ap.add_argument("--phase-s", type=float, default=None, help="length of each quiet / busy phase")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    size = os.path.getsize(a.fg_file) if a.fg_file else a.fg_bytes
    if not size or size < BLOCK or size % BLOCK:
        sys.exit("need --fg-file or --fg-bytes (at least 4096)")
    if not math.isfinite(a.rate) or not math.isfinite(a.seconds) or a.rate <= 0 or a.seconds <= 0:
        sys.exit("--rate and --seconds must be positive")
    if (a.busy_rate is None) != (a.phase_s is None):
        sys.exit("--busy-rate and --phase-s go together")
    if a.busy_rate is not None and not (math.isfinite(a.busy_rate) and a.busy_rate > 0 and
                                        math.isfinite(a.phase_s) and a.phase_s > 0):
        sys.exit("--busy-rate and --phase-s must be positive")
    if max(a.rate, a.busy_rate or 0) * a.seconds > 1_900_000:
        sys.exit('requested trace is too large for the dispatcher')
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}: the same trace must be reused for every run")

    rng = random.Random(a.seed)
    nblocks = size // BLOCK
    end_ns = int(a.seconds * 1e9)
    n = 0
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    if a.busy_rate is None:
        phases = [(0.0, a.seconds, a.rate)]
    else:
        phases, start, busy = [], 0.0, False
        while start < a.seconds:
            phases.append((start, min(a.seconds, start + a.phase_s), a.busy_rate if busy else a.rate))
            start += a.phase_s
            busy = not busy
    with open(a.out, "x") as f:
        f.write("t_ns,offset\n")
        for p_start, p_end, rate in phases:
            t = p_start                        # Poisson is memoryless: restart at each phase
            while True:
                t += rng.expovariate(rate)
                if t >= p_end:
                    break
                t_ns = int(t * 1e9)
                if t_ns >= end_ns:
                    break
                f.write(f"{t_ns},{rng.randrange(nblocks) * BLOCK}\n")
                n += 1
    kind = "constant" if a.busy_rate is None else f"alternating {a.rate:g}/{a.busy_rate:g} per s, {a.phase_s:g} s phases"
    print(f"wrote {a.out}: {n} requests ({kind}), {n / a.seconds:.1f}/s mean over {a.seconds:g} s, "
          f"seed {a.seed}, {nblocks} possible blocks")


if __name__ == "__main__":
    main()
