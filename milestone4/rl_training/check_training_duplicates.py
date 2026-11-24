"""Evaluate the frozen RL policy with and without exact training duplicates."""
from collections import defaultdict
from pathlib import Path
import json

import numpy as np
import rl_sim as S
import train_rl as T


def evaluate_pool(rows, table, episodes=1000):
    pool = defaultdict(list)
    for row in rows:
        if row['policy'] in ('adaptive', 'adaptive_nodamp'):
            continue
        key = (S.chunk_case(row['study']), S.load_bucket(row['fg']),
               int(row['policy'].split('q')[1]))
        pool[key].append((row['miss'], row['mib']))
    pool = {key: np.asarray(values) for key, values in pool.items()}
    output = {}
    for chunk, trace in T.CASES:
        rng = np.random.default_rng(90210 + len(chunk) * 7 + len(trace))
        sim, policy = S.Sim(pool, rng), T.QPolicy(table)
        samples = [T.evaluate(sim, chunk, trace, policy, rng)
                   for _ in range(episodes)]
        output[chunk + ' ' + trace] = {
            key: float(np.mean([sample[key] for sample in samples]))
            for key in samples[0]
        }
    return output


def main():
    folder = Path(__file__).resolve().parent
    rows = json.loads((folder / 'windows.json').read_text())
    unique, seen = [], set()
    for row in rows:
        key = json.dumps(row, sort_keys=True)
        if key not in seen:
            unique.append(row)
            seen.add(key)
    table = np.load(folder / 'rl_table_frozen.npy')
    print(json.dumps({
        'original': evaluate_pool(rows, table),
        'deduplicated': evaluate_pool(unique, table),
    }, indent=2))


if __name__ == '__main__':
    main()
