"""Q-learning v2: state adds a throughput bucket (MiB scanned in the last window),
which lets the policy tell 256 KiB from 1 MiB chunks. 4 x 3 x 3 x 3 states."""
import sys, numpy as np
sys.path.insert(0, '.')
import rl_sim as S
import train_rl as T
LV = S.LEVELS

def tb(mib):
    return 0 if mib < 4500 else (1 if mib < 6500 else 2)

class QPolicy2:
    def __init__(self, table): self.table = np.asarray(table)
    def reset(self): self.last_tb = 0
    def __call__(self, idx, m, lb, rng=None, mib=None):
        return int(self.table[idx, T.bucket_m(m), lb, tb(mib) if mib is not None else 1])

def evaluate2(sim, chunk, trace, pol, rng, seconds=130, warm=10):
    pol.reset(); idx = 0; mibs=[]; misses=[]; qs=[]; viol=0
    for t in range(seconds):
        lb = S.load_bucket(S.load_schedule(trace, t))
        m, mib = sim.window(chunk, lb, LV[idx])
        if t >= warm:
            mibs.append(mib); misses.append(m); qs.append(LV[idx]); viol += (m > 0.05)
        idx = pol(idx, m, lb, rng, mib=mib)
    n = seconds - warm
    return dict(mib_s=float(np.mean(mibs)), miss=float(np.mean(misses)), viol=viol/n, q=float(np.mean(qs)))

def train2(pool, episodes=60000, seed=3, alpha=0.1, gamma=0.9, pen=6.0, seconds=130, warm=10):
    rng = np.random.default_rng(seed); sim = S.Sim(pool, rng)
    Q = np.zeros((4, 3, 3, 3, 4))
    for ep in range(episodes):
        eps = max(0.05, 1.0 - 2.0 * ep / episodes)
        chunk, trace = T.CASES[ep % len(T.CASES)]
        idx = 0; s_prev = None; a_prev = None
        for t in range(seconds):
            lb = S.load_bucket(S.load_schedule(trace, t))
            m, mib = sim.window(chunk, lb, LV[idx])
            r = (mib/1000.0 - (pen if m > 0.05 else 0.0)) if t >= warm else 0.0
            s_cur = (idx, T.bucket_m(m), lb, tb(mib))
            if s_prev is not None:
                tgt = r + gamma * np.max(Q[s_cur])
                Q[s_prev + (a_prev,)] += alpha * (tgt - Q[s_prev + (a_prev,)])
            a = int(rng.integers(4)) if rng.random() < eps else int(np.argmax(Q[s_cur]))
            s_prev, a_prev = s_cur, a; idx = a
    return np.argmax(Q, axis=4)

if __name__ == '__main__':
    pool = S.build_pool()
    pen = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    table = train2(pool, pen=pen)
    np.save(f'table2_pen{pen}.npy', table)
    rng = np.random.default_rng(90210)
    pol = QPolicy2(table)
    print('pen', pen)
    for chunk, trace in T.CASES:
        sim = S.Sim(pool, np.random.default_rng(90210 + len(chunk)*7 + len(trace)))
        res = [evaluate2(sim, chunk, trace, pol, rng) for _ in range(1000)]
        print(f'{chunk:9s} {trace:12s} miss {np.mean([r["miss"] for r in res])*100:6.2f}  MiB/s {np.mean([r["mib_s"] for r in res]):7.0f}  q {np.mean([r["q"] for r in res]):.2f}', flush=True)
