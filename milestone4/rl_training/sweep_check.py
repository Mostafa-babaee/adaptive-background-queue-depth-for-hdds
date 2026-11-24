"""Evaluate each saved penalty-sweep table with the frozen evaluation seeds."""
from pathlib import Path

import numpy as np
import rl_sim as S
import train_rl as T


def main():
    folder = Path(__file__).resolve().parent
    pool = S.build_pool(folder / 'windows.json')
    for path in sorted(folder.glob('table_pen*.npy')):
        policy = T.QPolicy(np.load(path))
        results = []
        for chunk, trace in T.CASES:
            rng = np.random.default_rng(90210 + len(chunk) * 7 + len(trace))
            sim = S.Sim(pool, rng)
            samples = [T.evaluate(sim, chunk, trace, policy, rng)
                       for _ in range(1000)]
            misses = np.mean([sample['miss'] for sample in samples]) * 100
            speed = np.mean([sample['mib_s'] for sample in samples])
            results.append(f'{chunk} {trace}: {misses:.2f}% {speed:.0f}')
        print(path.name, ' | '.join(results), flush=True)


if __name__ == '__main__':
    main()
