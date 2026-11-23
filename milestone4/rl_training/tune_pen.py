import sys, numpy as np
sys.path.insert(0, '.')
import rl_sim as S, train_rl as T
pool = S.build_pool()
for pen in [float(x) for x in sys.argv[1:]]:
    table, _ = T.train(pool, episodes=40000, seed=7, pen=pen)
    pol = T.QPolicy(table)
    tot = []
    for chunk, trace in T.CASES:
        rng = np.random.default_rng(555)
        sim = S.Sim(pool, rng)
        res = [T.evaluate(sim, chunk, trace, pol, rng) for _ in range(300)]
        tot.append((chunk, trace, np.mean([r['miss'] for r in res])*100, np.mean([r['mib_s'] for r in res])))
    print('pen', pen, ' | '.join(f'{c[-4:]} {t[:4]} miss {m:.2f} MiB/s {s:.0f}' for c, t, m, s in tot), flush=True)
    np.save(f'table_pen{pen}.npy', table)
