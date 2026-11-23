"""Windowed simulator fitted to Milestone 3 per-window logs (fixed-q runs only).

Each simulated window at (chunk case, load bucket, q) draws one (miss, MiB)
pair from the logged fixed-q windows with the same chunk case, load bucket
and q. Draws are i.i.d.: persistence between windows is NOT modelled.
"""
import json, random, collections
import numpy as np

LEVELS = [1, 2, 4, 8]
TARGET_MISS = 0.05
MISS_LOW = 0.01

def load_bucket(fg):
    if fg < 100: return 0      # quiet, ~50 reads/window
    if fg < 500: return 1      # busy, ~200 reads/window
    return 2                   # overload, ~2000 reads/window

def chunk_case(study):
    return 'chunk1m' if study == 'C_chunk1m' else 'chunk256k'

def build_pool(path='windows.json', exclude_pol=('adaptive', 'adaptive_nodamp')):
    rows = json.load(open(path))
    pool = collections.defaultdict(list)
    for r in rows:
        if r['policy'] in exclude_pol: continue
        q = int(r['policy'].split('q')[1])
        key = (chunk_case(r['study']), load_bucket(r['fg']), q)
        pool[key].append((r['miss'], r['mib']))
    return {k: np.array(v) for k, v in pool.items()}

class Sim:
    def __init__(self, pool, rng):
        self.pool, self.rng = pool, rng
    def window(self, chunk, load, q):
        arr = self.pool[(chunk, load, q)]
        i = self.rng.integers(len(arr))
        return float(arr[i, 0]), float(arr[i, 1])

def load_schedule(trace, t):
    """Reads per window at second t (window = 1 s), following Milestone 3 traces."""
    if trace == 'constant': return 50
    if trace == 'alternating': return 200 if (t // 20) % 2 == 1 else 50
    if trace == 'overload': return 2000
    raise ValueError(trace)

def obs_load(fg):
    return load_bucket(fg)

def miss_bucket(m):
    if m <= MISS_LOW: return 0
    if m <= TARGET_MISS: return 1
    return 2

def run_episode(sim, chunk, trace, policy, seconds=130, warm=10, rng=None):
    """policy(state) -> next level index.  state = (q_idx, last_miss_bucket, load_bucket).
    Returns dict with measured misses, MiB and q series."""
    q_idx = 0
    last_b = 0
    tot_mib = 0.0; misses = []; qs = []; viol = 0
    for t in range(seconds):
        load = load_schedule(trace, t)
        q = LEVELS[q_idx]
        m, mib = sim.window(chunk, obs_load(load), q)
        if t >= warm:
            tot_mib += mib; misses.append(m); qs.append(q)
            if m > TARGET_MISS: viol += 1
        last_b = miss_bucket(m)
        q_idx = policy((q_idx, last_b, obs_load(load)), rng)
    return dict(mib=tot_mib, mean_miss=float(np.mean(misses)), viol_frac=viol / len(misses),
                q_mean=float(np.mean(qs)), mib_per_s=tot_mib / (seconds - warm))
