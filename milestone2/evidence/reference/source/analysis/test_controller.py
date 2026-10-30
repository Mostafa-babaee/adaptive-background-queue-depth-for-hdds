"""Unit tests for the policy rule (run: python3 -m unittest analysis/test_controller.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from controller import (DOWN, HOLD, SPARSE, UP, AdaptivePolicy,  # noqa: E402
                        ControllerConfig, FixedPolicy, WindowStats, make_policy)

GOOD = WindowStats(fg_samples=200, fg_misses=0)      # 0% miss: comfortable
BAD = WindowStats(fg_samples=200, fg_misses=40)      # 20% miss: too many
MID = WindowStats(fg_samples=200, fg_misses=6)       # 3%: between thresholds
SPARSE_W = WindowStats(fg_samples=10, fg_misses=10)  # below min_samples


def cfg(**kw):
    return ControllerConfig(**kw)


class TestFixed(unittest.TestCase):
    def test_never_changes(self):
        p = FixedPolicy(4)
        for w in (GOOD, BAD, SPARSE_W):
            self.assertEqual(p.next_q(w), (4, HOLD))

    def test_rejects_bad_q(self):
        with self.assertRaises(ValueError):
            FixedPolicy(3)


class TestAdaptive(unittest.TestCase):
    def test_starts_at_q_start(self):
        self.assertEqual(AdaptivePolicy(cfg(q_start=4)).q, 4)

    def test_sparse_window_holds(self):
        p = AdaptivePolicy(cfg(q_start=4))
        self.assertEqual(p.next_q(SPARSE_W), (4, SPARSE))

    def test_sparse_window_keeps_streak(self):
        p = AdaptivePolicy(cfg())
        p.next_q(GOOD); p.next_q(GOOD)
        p.next_q(SPARSE_W)
        self.assertEqual(p.next_q(GOOD), (2, UP))

    def test_step_down_on_misses(self):
        p = AdaptivePolicy(cfg(q_start=8))
        self.assertEqual(p.next_q(BAD), (4, DOWN))
        self.assertEqual(p.next_q(BAD), (2, DOWN))
        self.assertEqual(p.next_q(BAD), (1, DOWN))

    def test_never_below_one(self):
        p = AdaptivePolicy(cfg(q_start=1))
        for _ in range(5):
            q, _ = p.next_q(BAD)
            self.assertEqual(q, 1)

    def test_needs_three_good_windows_to_step_up(self):
        p = AdaptivePolicy(cfg(q_start=1, up_windows=3))
        self.assertEqual(p.next_q(GOOD), (1, HOLD))
        self.assertEqual(p.next_q(GOOD), (1, HOLD))
        self.assertEqual(p.next_q(GOOD), (2, UP))

    def test_middle_window_resets_streak(self):
        p = AdaptivePolicy(cfg(q_start=1))
        p.next_q(GOOD); p.next_q(GOOD)
        self.assertEqual(p.next_q(MID), (1, HOLD))
        p.next_q(GOOD); p.next_q(GOOD)
        self.assertEqual(p.next_q(GOOD), (2, UP))

    def test_never_above_max(self):
        p = AdaptivePolicy(cfg(q_start=8, up_windows=1))
        for _ in range(5):
            q, _ = p.next_q(GOOD)
            self.assertEqual(q, 8)

    def test_q_always_allowed_value(self):
        import random
        rnd = random.Random(1)
        p = AdaptivePolicy(cfg())
        for _ in range(2000):
            n = rnd.randint(0, 300)
            w = WindowStats(n, rnd.randint(0, n) if n else 0, scanning=rnd.random() > 0.05)
            q, a = p.next_q(w)
            self.assertIn(q, [1, 2, 4, 8])
            self.assertIn(a, [UP, DOWN, HOLD, SPARSE])

    def test_not_scanning_holds(self):
        p = AdaptivePolicy(cfg(q_start=2))
        self.assertEqual(p.next_q(WindowStats(200, 200, scanning=False)), (2, HOLD))

    def test_ablation_steps_up_every_good_window(self):
        p = make_policy("adaptive_nodamp", cfg(q_start=1))
        self.assertEqual([p.next_q(GOOD)[0] for _ in range(3)], [2, 4, 8])

    def test_exact_threshold_boundaries(self):
        c = cfg(q_start=4, miss_high=0.05, miss_low=0.01, up_windows=1)
        p = AdaptivePolicy(c)
        self.assertEqual(p.next_q(WindowStats(100, 5)), (4, HOLD))   # 5% = not above high
        self.assertEqual(p.next_q(WindowStats(100, 6)), (2, DOWN))   # 6% > high
        self.assertEqual(p.next_q(WindowStats(100, 1)), (4, UP))     # 1% = comfortable

    def test_bad_config_rejected(self):
        for bad in (dict(q_start=3), dict(miss_low=0.1, miss_high=0.05),
                    dict(levels=[4, 2]), dict(min_samples=0)):
            with self.assertRaises(ValueError):
                AdaptivePolicy(cfg(**bad))

    def test_config_file_loads(self):
        path = os.path.join(os.path.dirname(__file__), "..", "config", "adaptive.json")
        c = ControllerConfig.load(path)
        c.validate()
        self.assertEqual(c.levels, [1, 2, 4, 8])


if __name__ == "__main__":
    unittest.main()
