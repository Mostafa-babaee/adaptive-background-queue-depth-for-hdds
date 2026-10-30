#!/usr/bin/env python3
"""
make_trace.py - Milestone 2, Sheryar Karim.
Workload generator: writes a fixed foreground (FG) arrival trace.

Every policy and every repetition replays the SAME trace file, so all runs get
identical offered requests (same arrival times, same offsets).

Arrivals are a Poisson process (random gaps with a fixed mean rate) from a
fixed seed. Each FG request reads one random 4 KiB block of the FG test file.

Output: CSV with header 't_ns,offset'. t_ns is nanoseconds since run start
(warm-up included), offset is bytes (4 KiB aligned).

Usage:
    python3 tools/make_trace.py --fg-file /path/fg.dat --rate 100 \
        --seconds 130 --seed 42 --out traces/constant_100rps.csv
    # --fg-bytes N can replace --fg-file when the file is not on this machine
"""
import argparse
import os
import random
import sys

BLOCK = 4096


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fg-file", help="FG test file (its size sets the offset range)")
    ap.add_argument("--fg-bytes", type=int, help="FG file size in bytes, instead of --fg-file")
    ap.add_argument("--rate", type=float, required=True, help="mean FG arrivals per second")
    ap.add_argument("--seconds", type=float, required=True, help="trace length = warm-up + duration")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    size = os.path.getsize(a.fg_file) if a.fg_file else a.fg_bytes
    if not size or size < BLOCK:
        sys.exit("need --fg-file or --fg-bytes (at least 4096)")
    if a.rate <= 0 or a.seconds <= 0:
        sys.exit("--rate and --seconds must be positive")
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}: the same trace must be reused for every run")

    rng = random.Random(a.seed)
    nblocks = size // BLOCK
    end_ns = int(a.seconds * 1e9)
    t = 0.0
    n = 0
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        f.write("t_ns,offset\n")
        while True:
            t += rng.expovariate(a.rate)
            t_ns = int(t * 1e9)
            if t_ns >= end_ns:
                break
            f.write(f"{t_ns},{rng.randrange(nblocks) * BLOCK}\n")
            n += 1
    print(f"wrote {a.out}: {n} requests, {n / a.seconds:.1f}/s over {a.seconds:g} s, "
          f"seed {a.seed}, {nblocks} possible blocks")


if __name__ == "__main__":
    main()
