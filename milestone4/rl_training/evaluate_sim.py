import sys, numpy as np
sys.path.insert(0, '.')
import rl_sim as S, train_rl as T

pool = S.build_pool()
table = np.load('q_table.npy')
policies = {'adaptive (Milestone 3 rule)': T.Adaptive(3), 'no damping (up=1)': T.Adaptive(1),
            'RL (trained)': T.QPolicy(table), 'fixed q=2': T.Fixed(2), 'fixed q=8': T.Fixed(8)}
N = 400
print(f'{"case":28s} {"policy":28s} {"miss %":>8s} {"viol %":>7s} {"MiB/s":>8s} {"q":>5s}')
for chunk, trace in T.CASES:
    for name, pol in policies.items():
        rng = np.random.default_rng(1000 + hash((chunk, trace)) % 1000)
        sim = S.Sim(pool, rng)
        res = [T.evaluate(sim, chunk, trace, pol, rng) for _ in range(N)]
        mm = np.mean([r['miss'] for r in res]) * 100
        vv = np.mean([r['viol'] for r in res]) * 100
        sp = np.mean([r['mib_s'] for r in res])
        qq = np.mean([r['q'] for r in res])
        print(f'{chunk+" "+trace:28s} {name:28s} {mm:8.2f} {vv:7.2f} {sp:8.0f} {qq:5.2f}')
