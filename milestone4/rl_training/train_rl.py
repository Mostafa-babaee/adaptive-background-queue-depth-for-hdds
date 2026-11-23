"""Tabular Q-learning for the background queue depth, trained in rl_sim.

State after window t:   s = (idx_t, bucket(miss_t), load_bucket_t)   [4 x 3 x 3]
Action:                 a = index of q for window t+1               [4]
Reward for window t+1:  MiB scanned / 1000  minus PEN if miss > 5 %
Only the controller's own observables are used (miss and reads per window).
"""
import sys
import numpy as np
sys.path.insert(0, '.')
import rl_sim as S

LV = S.LEVELS
CASES = [('chunk256k', 'constant'), ('chunk256k', 'alternating'), ('chunk256k', 'overload'),
         ('chunk1m', 'alternating')]           # (chunk1m, overload) has no logged data

def bucket_m(m):
    return 0 if m <= 0.01 else (1 if m <= 0.05 else 2)

class Adaptive:
    """Milestone 3 rule with the same numbers as controller.py."""
    def __init__(self, up=3):
        self.up = up; self.streak = 0
    def reset(self):
        self.streak = 0
    def __call__(self, idx, m, lb, rng=None):
        if m > 0.05:
            self.streak = 0; return max(idx - 1, 0)
        if m <= 0.01:
            self.streak += 1
            if self.streak >= self.up:
                self.streak = 0; return min(idx + 1, 3)
            return idx
        self.streak = 0; return idx

class Fixed:
    def __init__(self, q): self.idx = LV.index(q)
    def reset(self): pass
    def __call__(self, idx, m, lb, rng=None): return self.idx

class QPolicy:
    def __init__(self, table): self.table = np.asarray(table)
    def reset(self): pass
    def __call__(self, idx, m, lb, rng=None):
        return int(self.table[idx, bucket_m(m), lb])

def evaluate(sim, chunk, trace, policy, rng, seconds=130, warm=10):
    policy.reset()
    idx = 0; mibs = []; misses = []; qs = []; viol = 0
    for t in range(seconds):
        lb = S.load_bucket(S.load_schedule(trace, t))
        m, mib = sim.window(chunk, lb, LV[idx])
        if t >= warm:
            mibs.append(mib); misses.append(m); qs.append(LV[idx]); viol += (m > 0.05)
        idx = policy(idx, m, lb, rng)
    n = seconds - warm
    return dict(mib_s=float(np.mean(mibs)), miss=float(np.mean(misses)),
                viol=viol / n, q=float(np.mean(qs)))

def train(pool, episodes=40000, seed=1, alpha=0.1, gamma=0.9, pen=20.0, seconds=130, warm=10):
    rng = np.random.default_rng(seed)
    sim = S.Sim(pool, rng)
    Q = np.zeros((4, 3, 3, 4))
    for ep in range(episodes):
        eps = max(0.05, 1.0 - 2.0 * ep / episodes)
        chunk, trace = CASES[ep % len(CASES)]
        idx = 0; s_prev = None; a_prev = None
        for t in range(seconds):
            lb = S.load_bucket(S.load_schedule(trace, t))
            m, mib = sim.window(chunk, lb, LV[idx])
            r = (mib / 1000.0 - (pen if m > 0.05 else 0.0)) if t >= warm else 0.0
            s_cur = (idx, bucket_m(m), lb)
            if s_prev is not None:
                target = r + gamma * np.max(Q[s_cur])
                Q[s_prev + (a_prev,)] += alpha * (target - Q[s_prev + (a_prev,)])
            if rng.random() < eps: a = int(rng.integers(4))
            else: a = int(np.argmax(Q[s_cur]))
            s_prev, a_prev = s_cur, a
            idx = a
    table = np.argmax(Q, axis=3)
    return table, Q

if __name__ == '__main__':
    pool = S.build_pool()
    table, Q = train(pool)
    np.save('q_table.npy', table)
    print('greedy table [idx][miss_bucket][load_bucket] -> next idx')
    for i in range(4):
        print(LV[i], [[int(table[i, b, l]) for l in range(3)] for b in range(3)])
