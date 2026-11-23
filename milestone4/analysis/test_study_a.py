#!/usr/bin/env python3
"""
test_study_a.py - Milestone 2, Muhammad Ahmad Tariq.
Unit tests for the Study A analysis: warm-up is dropped, latency and miss
fraction are computed from the right timestamps, throughput uses only the
measured period, and the frozen target follows the documented rule.

Run: python3 -m unittest analysis/test_study_a.py -v   (from the code/ folder)
"""
import math
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import study_a  # noqa: E402

MS = 1_000_000
S = 1_000_000_000


def make_run():
    meta = {"run_id": "t", "mode": "mixed", "q": 2, "repetition": 1, "warmup_ns": 1 * S,
            "duration_ns": 2 * S, "accounting_ok": True, "direct_io": True}
    rows = []
    # warm-up FG read: must be ignored even though it is very slow
    rows.append(dict(class_="FG", t_arrival=0.5 * S, t_submit=0.5 * S, t_complete=0.5 * S + 900 * MS,
                     status="OK", verified=1, len=4096))
    # 100 measured FG reads: 90 take 2 ms, 10 take 12 ms (5 ms waiting + 7 ms service)
    for i in range(100):
        t = 1 * S + i * 10 * MS
        slow = i % 10 == 0
        rows.append(dict(class_="FG", t_arrival=t, t_submit=t + (5 * MS if slow else 0),
                         t_complete=t + (12 * MS if slow else 2 * MS), status="OK", verified=1, len=4096))
    rows.append(dict(class_="FG", t_arrival=1.5 * S, t_submit=None, t_complete=None,
                     status="REJECTED", verified=0, len=4096))
    # BG: 8 chunks of 256 KiB completed in the measured period, 4 in warm-up
    for i in range(12):
        tc = (0.2 * S + i * 0.05 * S) if i < 4 else (1.1 * S + i * 0.1 * S)
        rows.append(dict(class_="BG", t_arrival=tc - MS, t_submit=tc - MS, t_complete=tc,
                         status="OK", verified=1, len=262144))
    req = pd.DataFrame(rows).rename(columns={"class_": "class"})
    win = pd.DataFrame([dict(t_start=k * 500 * MS, t_end=(k + 1) * 500 * MS, bg_out_mean=1.5,
                             bg_out_max=2, ctrl_cpu_ns=500) for k in range(6)])
    return meta, req, win


class StudyATests(unittest.TestCase):
    def test_metrics(self):
        meta, req, win = make_run()
        m = study_a.run_metrics(meta, req, win, target_ms=5.0)
        self.assertEqual(m["fg_offered"], 101)          # 100 OK + 1 rejected, warm-up excluded
        self.assertEqual(m["fg_done"], 100)
        self.assertEqual(m["rejected"], 1)
        self.assertAlmostEqual(m["fg_p50_ms"], 2.0)
        self.assertAlmostEqual(m["fg_p99_ms"], 12.0)
        self.assertAlmostEqual(m["miss_frac"], 0.10)
        self.assertAlmostEqual(m["wait_p99_ms"], 5.0)
        self.assertAlmostEqual(m["scan_mib_s"], 8 * 0.25 / 2.0)   # 8 x 0.25 MiB over 2 s
        self.assertEqual(m["bg_out_max"], 2)
        self.assertEqual(m["errors"], 0)

    def test_no_target_gives_nan_miss(self):
        meta, req, win = make_run()
        self.assertTrue(math.isnan(study_a.run_metrics(meta, req, win, None)["miss_frac"]))

    def test_choose_target_rule(self):
        s = pd.DataFrame([{"mode": "mixed", "q": 1, "fg_p99_ms_mean": 30.2},
                          {"mode": "mixed", "q": 8, "fg_p99_ms_mean": 210.0}])
        t = study_a.choose_target(s, rate=50)
        self.assertEqual(t["target_ms"], 38.0)          # 1.25 x 30.2 = 37.75 -> 38.0
        self.assertGreaterEqual(t["window_ms"] / 1000 * 50, 2 * t["min_samples"])
        self.assertIsNone(study_a.choose_target(s[s["q"] == 8], rate=50))


if __name__ == "__main__":
    unittest.main(verbosity=2)
