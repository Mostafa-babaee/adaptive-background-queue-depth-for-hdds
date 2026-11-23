#!/usr/bin/env python3
"""
test_adaptive.py - Milestone 3, Mostafa Babaei (with Tariq's controller).
Correctness tests for the adaptive policy inside the real dispatcher
(bin/dispatcher --policy adaptive|adaptive_nodamp), with real io_uring reads.

Covered (Project Execution Plan, Milestone 3):
  1. safe limit reductions: when q drops below the reads already in flight,
     no new background read is submitted until enough of them finish
     (every BG submit has bg_out_at_submit < q_at_submit), and the drain is
     logged
  2. data integrity, errors and completion accounting on adaptive runs
     (every byte verified, accepted = submitted + unsubmitted,
     submitted = OK + ERR), also with Ctrl-C while reads are in flight
  3. controller CPU cost is measured: one controller call per window, its CPU
     time logged per window and in total
  plus: q goes up only after up_windows good windows, the no-damping ablation
  goes up after one, sparse windows hold q, q is always 1, 2, 4 or 8, the
  window log matches what the requests saw, and bad options are refused.

Run from the milestone folder after `make`:
    python3 -m unittest tests/test_adaptive.py -v
"""
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin", "dispatcher")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_testfiles  # noqa: E402

BLOCK = 4096
LEVELS = {1, 2, 4, 8}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def write_trace(path, rows):
    with open(path, "w") as f:
        f.write("t_ns,offset\n")
        for t, off in rows:
            f.write(f"{t},{off}\n")


def make_file(path, size_bytes, file_id):
    with open(path, "wb") as f:
        for b in range(size_bytes // BLOCK):
            f.write(make_testfiles.block_bytes(file_id, b))


class AdaptiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(BIN):
            raise RuntimeError("build first: make")
        base = os.environ.get("ADAPTIVE_TEST_DIR")
        if base:
            os.makedirs(base, exist_ok=False)
            cls.tmp = base
        else:
            cls.tmp = tempfile.mkdtemp(prefix="_tmp_adaptive_", dir=HERE)
        cls.fg = os.path.join(cls.tmp, "fg.dat")
        cls.bg = os.path.join(cls.tmp, "bg.dat")
        make_file(cls.fg, 8 << 20, 1)
        make_file(cls.bg, 16 << 20, 2)
        cls.fg_blocks = (8 << 20) // BLOCK
        cls.trace = os.path.join(cls.tmp, "trace.csv")
        write_trace(cls.trace, [((i + 1) * 2_500_000, (i * 7919 % cls.fg_blocks) * BLOCK)
                                for i in range(1600)])          # 400/s for 4 s
        cls.sparse_trace = os.path.join(cls.tmp, "trace_sparse.csv")
        write_trace(cls.sparse_trace, [((i + 1) * 50_000_000, (i * 31 % cls.fg_blocks) * BLOCK)
                                       for i in range(80)])     # 20/s: 2 per 100 ms window
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        if os.environ.get("ADAPTIVE_TEST_DIR"):
            print("Retained adaptive test evidence: " + cls.tmp)
        else:
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def config(self, **kw):
        cfg = {"policy": "adaptive", "levels": [1, 2, 4, 8], "q_start": 1, "window_ms": 100,
               "min_samples": 10, "target_ms": 1000.0, "miss_high": 0.05, "miss_low": 0.01,
               "up_windows": 3}
        cfg.update(kw)
        type(self).n += 1
        path = os.path.join(self.tmp, f"ctrl{self.n}.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        return path

    def run_d(self, *args, policy="adaptive", trace=None, duration="1.5", expect_exit=0, **cfg):
        cfg_path = self.config(**cfg)
        type(self).n += 1
        out = os.path.join(self.tmp, f"run{self.n}")
        cmd = [BIN, "--out", out, "--mode", "mixed", "--fg", self.fg, "--bg", self.bg,
               "--trace", trace or self.trace, "--warmup-s", "0.2", "--duration-s", duration,
               "--policy", policy, "--ctrl-config", cfg_path, "--run-id", f"adaptive{self.n}"] + list(args)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, expect_exit, p.stderr)
        meta = load_json(os.path.join(out, "run_meta.json"))
        return meta, read_csv(os.path.join(out, "requests.csv")), read_csv(os.path.join(out, "windows.csv"))

    def check_run(self, meta, reqs, wins):
        """Integrity and accounting, as for every Study B/C run."""
        c = meta["counts"]
        self.assertTrue(meta["accounting_ok"])
        self.assertEqual(c["accepted"], c["submitted"] + c["unsubmitted"])
        self.assertEqual(c["submitted"], c["completed_ok"] + c["completed_err"])
        self.assertEqual(c["completed_err"], 0)
        self.assertEqual(c["verify_fail"], 0)
        ids = [r["req_id"] for r in reqs]
        self.assertEqual(len(ids), len(set(ids)), "a request was logged twice")
        self.assertEqual(len(reqs), c["accepted"] + c["rejected"])
        ok = [r for r in reqs if r["status"] == "OK"]
        self.assertTrue(all(r["verified"] == "1" for r in ok), "unverified bytes")
        # q is always an allowed level; BG never above the q it was sent under
        for r in reqs:
            if r["t_submit"]:
                self.assertIn(int(r["q_at_submit"]), LEVELS)
                if r["class"] == "BG":
                    self.assertLess(int(r["bg_out_at_submit"]), int(r["q_at_submit"]),
                                    f"BG read {r['req_id']} sent while bg_out >= q")
                else:
                    self.assertLess(int(r["fg_out_at_submit"]), meta["fg_quota"])
        qs = [int(w["q_config"]) for w in wins]
        self.assertTrue(set(qs) <= LEVELS)
        for a, b in zip(qs, qs[1:]):
            self.assertIn(b, (a, a * 2, a // 2), "q moved more than one level in one window")
        self.assertTrue(all(int(w["bg_out_max"]) <= 8 for w in wins))
        # CPU cost: one controller call per window, logged
        self.assertEqual(meta["cpu_cost"]["ctrl_calls"], len(wins))
        self.assertEqual(meta["cpu_cost"]["ctrl_cpu_ns_total"], sum(int(w["ctrl_cpu_ns"]) for w in wins))
        self.assertGreater(meta["cpu_cost"]["process_user_ns"] + meta["cpu_cost"]["process_sys_ns"], 0)

    # 1. safe limit reductions ------------------------------------------------
    def test_safe_reduction_below_outstanding(self):
        # Every FG read misses a 1 ns target: q must step 8 -> 4 -> 2 -> 1.
        meta, reqs, wins = self.run_d(q_start=8, target_ms=0.000001, min_samples=5)
        self.check_run(meta, reqs, wins)
        qs = [int(w["q_config"]) for w in wins]
        self.assertEqual(qs[:4], [8, 4, 2, 1], "one level down per bad window")
        downs = [i for i, w in enumerate(wins) if w["action"] == "DOWN"]
        self.assertGreaterEqual(len(downs), 3, "expected three steps down")
        self.assertEqual(qs[-1], 1)
        self.assertEqual(meta["q_final"], 1)
        sr = meta["safe_reduction"]
        self.assertGreaterEqual(sr["reductions_below_outstanding"], 1,
                                "q should have been lowered below the reads in flight")
        # In the window right after a cut, the reads already in flight (more than
        # the new q) were allowed to finish; none was cancelled.
        after_cut = [wins[i + 1] for i in downs if i + 1 < len(wins)]
        self.assertTrue(any(int(w["bg_out_max"]) > int(w["q_config"]) for w in after_cut),
                        "no window shows in-flight reads above the new q")
        bg_after = [r for r in reqs if r["class"] == "BG" and r["t_submit"]
                    and int(r["q_at_submit"]) == 1]
        self.assertTrue(bg_after, "scan continues at q = 1")
        self.assertTrue(all(r["bg_out_at_submit"] == "0" for r in bg_after))

    def test_no_new_bg_until_drained(self):
        # Directly: after each cut, the first new BG submit must see bg_out < new q.
        meta, reqs, wins = self.run_d(q_start=8, target_ms=0.000001, min_samples=5)
        self.check_run(meta, reqs, wins)
        cuts = [(int(w["t_end"]), int(wins[i + 1]["q_config"]) if i + 1 < len(wins) else 1)
                for i, w in enumerate(wins) if w["action"] == "DOWN"]
        bg = sorted((int(r["t_submit"]), int(r["bg_out_at_submit"]), int(r["q_at_submit"]))
                    for r in reqs if r["class"] == "BG" and r["t_submit"])
        for t_cut, q_new in cuts:
            first = next((b for b in bg if b[0] >= t_cut), None)
            if first:
                self.assertLess(first[1], q_new)
                self.assertLessEqual(first[2], q_new)

    # 2. integrity / accounting on adaptive runs ------------------------------
    def test_adaptive_run_clean(self):
        meta, reqs, wins = self.run_d(target_ms=0.5, min_samples=10)
        self.check_run(meta, reqs, wins)
        self.assertEqual(meta["policy"], "adaptive")
        self.assertEqual(meta["controller"]["target_ms"], 0.5)
        self.assertEqual(meta["target_ms"], 0.5)
        self.assertEqual(meta["window_ms"], 100)
        self.assertGreater(meta["counts"]["bg_ok"], 0)
        self.assertGreater(meta["counts"]["fg_ok"], 400)

    def test_ctrl_c_with_reads_in_flight(self):
        cfg = self.config(q_start=8, target_ms=0.5)
        out = os.path.join(self.tmp, "run_sigint")
        p = subprocess.Popen([BIN, "--out", out, "--mode", "mixed", "--fg", self.fg, "--bg", self.bg,
                              "--trace", self.trace, "--warmup-s", "0", "--duration-s", "60",
                              "--policy", "adaptive", "--ctrl-config", cfg],
                             stderr=subprocess.PIPE, text=True)
        time.sleep(1.0)
        p.send_signal(signal.SIGINT)
        _, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 130, err)
        meta = load_json(os.path.join(out, "run_meta.json"))
        reqs = read_csv(os.path.join(out, "requests.csv"))
        wins = read_csv(os.path.join(out, "windows.csv"))
        self.assertTrue(meta["stopped_by_signal"])
        self.check_run(meta, reqs, wins)

    # controller behaviour inside the dispatcher -------------------------------
    def test_up_after_three_good_windows(self):
        meta, reqs, wins = self.run_d(target_ms=1000.0, min_samples=5)
        self.check_run(meta, reqs, wins)
        qs = [int(w["q_config"]) for w in wins]
        self.assertEqual(qs[:9], [1, 1, 1, 2, 2, 2, 4, 4, 4])
        self.assertEqual(qs[9], 8)
        self.assertEqual(meta["controller"]["up_windows"], 3)

    def test_nodamp_up_every_window(self):
        meta, reqs, wins = self.run_d(policy="adaptive_nodamp", target_ms=1000.0, min_samples=5)
        self.check_run(meta, reqs, wins)
        self.assertEqual(meta["policy"], "adaptive_nodamp")
        self.assertTrue(meta["controller"]["ablation"])
        qs = [int(w["q_config"]) for w in wins]
        self.assertEqual(qs[:4], [1, 2, 4, 8])

    def test_sparse_windows_hold(self):
        meta, reqs, wins = self.run_d(trace=self.sparse_trace, q_start=4, target_ms=0.000001,
                                      min_samples=10)
        self.check_run(meta, reqs, wins)
        scanning = [w for w in wins if int(w["fg_samples"]) < 10]
        self.assertTrue(scanning)
        self.assertTrue(all(w["q_config"] == "4" for w in wins), "sparse windows must hold q")
        self.assertGreater(meta["controller"]["n_sparse"], 5)
        self.assertEqual(meta["controller"]["n_down"], 0)

    def test_window_log_matches_requests(self):
        meta, reqs, wins = self.run_d(q_start=8, target_ms=0.000001, min_samples=5)
        self.check_run(meta, reqs, wins)
        spans = [(int(w["t_start"]), int(w["t_end"]), int(w["q_config"])) for w in wins]
        for r in reqs:
            if r["class"] == "BG" and r["t_submit"]:
                t = int(r["t_submit"])
                q = next(q for a, b, q in spans if a <= t < b or (t >= b and (a, b, q) == spans[-1]))
                self.assertEqual(int(r["q_at_submit"]), q)

    def test_bad_options(self):
        cfg = self.config()
        base = [BIN, "--mode", "mixed", "--fg", self.fg, "--bg", self.bg, "--trace", self.trace]
        cases = [
            ["--policy", "adaptive"],                                     # no config
            ["--policy", "adaptive", "--ctrl-config", cfg, "--q", "4"],   # q is from the config
            ["--policy", "adaptive", "--ctrl-config", cfg, "--window-ms", "500"],
            ["--policy", "adaptive", "--ctrl-config", cfg, "--target-ms", "0.7"],
            ["--policy", "magic", "--ctrl-config", cfg],
            ["--policy", "fixed", "--ctrl-config", cfg],
            ["--policy", "adaptive", "--ctrl-config", self.config(levels=[1, 3, 8])],
            ["--policy", "adaptive", "--ctrl-config", self.config(target_ms=None)],
        ]
        for i, extra in enumerate(cases):
            out = os.path.join(self.tmp, f"bad{i}")
            p = subprocess.run(base + extra + ["--out", out], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0, extra)

    def test_fixed_policy_unchanged(self):
        type(self).n += 1
        out = os.path.join(self.tmp, f"fixed{self.n}")
        p = subprocess.run([BIN, "--out", out, "--mode", "mixed", "--fg", self.fg, "--bg", self.bg,
                            "--trace", self.trace, "--warmup-s", "0.2", "--duration-s", "1",
                            "--q", "2", "--window-ms", "100", "--target-ms", "0.5"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        meta = load_json(os.path.join(out, "run_meta.json"))
        wins = read_csv(os.path.join(out, "windows.csv"))
        self.assertEqual(meta["policy"], "fixed")
        self.assertIsNone(meta["controller"])
        self.assertTrue(all(w["q_config"] == "2" for w in wins))
        self.assertEqual(meta["q_changes"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
