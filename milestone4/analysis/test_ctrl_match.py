#!/usr/bin/env python3
"""
test_ctrl_match.py - Milestone 3, Muhammad Ahmad Tariq.
The C controller (src/controller.c, through bin/ctrl_replay) must give the same
q and action as the Python reference (analysis/controller.py) for every window
of long random sequences, for both the adaptive policy and the no-damping
ablation, using the frozen config/adaptive.json.
Run from the milestone folder after `make`.
"""
import os
import random
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from controller import AdaptivePolicy, ControllerConfig, WindowStats  # noqa: E402

REPLAY = os.path.join(ROOT, "bin", "ctrl_replay")
CFG = os.path.join(ROOT, "config", "adaptive.json")


def random_windows(seed, n=20000):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        samples = rng.choice([0, 5, 24, 25, 26, 40, 60, 100, 150])
        kind = rng.random()
        if kind < 0.5:
            misses = 0
        elif kind < 0.7:
            misses = int(samples * rng.uniform(0, 0.02))
        elif kind < 0.85:
            misses = int(samples * rng.uniform(0.02, 0.06))
        else:
            misses = int(samples * rng.uniform(0.06, 0.5))
        out.append((samples, misses, rng.random() > 0.05))
    return out


class ControllerMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(REPLAY):
            raise unittest.SkipTest("build first: make")

    def compare(self, ablation, seed):
        wins = random_windows(seed)
        text = "".join(f"{n} {m} {int(s)}\n" for n, m, s in wins)
        args = [REPLAY, CFG] + (["nodamp"] if ablation else [])
        p = subprocess.run(args, input=text, capture_output=True, text=True, check=True)
        c_out = [tuple(line.split()) for line in p.stdout.splitlines()]
        py = AdaptivePolicy(ControllerConfig.load(CFG), ablation=ablation)
        py_out = []
        for n, m, s in wins:
            q, act = py.next_q(WindowStats(n, m, s))
            py_out.append((str(q), act))
        self.assertEqual(len(c_out), len(wins))
        for i, (a, b) in enumerate(zip(c_out, py_out)):
            self.assertEqual(a, b, f"window {i}: C {a} vs Python {b}")

    def test_adaptive_matches_python(self):
        for seed in (1, 2, 3):
            self.compare(False, seed)

    def test_nodamp_matches_python(self):
        for seed in (4, 5):
            self.compare(True, seed)

    def test_frozen_config_values(self):
        cfg = ControllerConfig.load(CFG)
        self.assertEqual((cfg.target_ms, cfg.window_ms, cfg.min_samples, cfg.miss_high,
                          cfg.miss_low, cfg.up_windows, cfg.q_start, cfg.levels),
                         (0.5, 1000, 25, 0.05, 0.01, 3, 1, [1, 2, 4, 8]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
