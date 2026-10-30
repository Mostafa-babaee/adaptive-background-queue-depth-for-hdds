#!/usr/bin/env python3
"""
test_dispatcher.py - Milestone 2, Mostafa Babaei.
Correctness tests for bin/dispatcher (the common C dispatcher).

Covered (Project Execution Plan, Milestone 2):
  1. verified file contents, and corrupted data is detected
  2. end-of-file: short last chunk, scan wrap-around, read past the end
  3. full pending queue: extra FG requests are REJECTED and logged
  4. read errors: a real kernel error is logged as ERR, the run continues
  5. shutdown with reads in flight (Ctrl-C and early stop): every submitted
     read completes exactly once, counters add up
  plus: background limit q and FG quota are never exceeded, request IDs are
  unique, and the same trace gives the same offered requests.

Run from the code/ folder after `make`:
    python3 -m unittest tests/test_dispatcher.py -v
Test files go in tests/_tmp (on the same disk as the code, so O_DIRECT works).
"""
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "bin", "dispatcher")
TMP = os.environ.get("DISPATCHER_TEST_DIR", os.path.join(HERE, "_tmp"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_testfiles  # noqa: E402

BLOCK = 4096
EIO, EBADF, EBADMSG = 5, 9, 74


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
    """Pattern file of any size that is a multiple of 4 KiB."""
    with open(path, "wb") as f:
        for b in range(size_bytes // BLOCK):
            f.write(make_testfiles.block_bytes(file_id, b))


class DispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(BIN):
            raise unittest.SkipTest("build first: make")
        shutil.rmtree(TMP, ignore_errors=True)
        os.makedirs(TMP)
        cls.fg = os.path.join(TMP, "fg.dat")
        cls.bg = os.path.join(TMP, "bg.dat")
        make_file(cls.fg, 8 << 20, 1)                      # 8 MiB
        make_file(cls.bg, (4 << 20) + 3 * BLOCK, 2)        # 4 MiB + 12 KiB: last chunk is short
        cls.fg_blocks = (8 << 20) // BLOCK
        cls.trace = os.path.join(TMP, "trace.csv")
        rows, t = [], 0
        for i in range(600):                               # 200/s for 3 s, fixed pattern
            t += 5_000_000
            rows.append((t, (i * 7919 % cls.fg_blocks) * BLOCK))
        write_trace(cls.trace, rows)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    def run_d(self, *args, fg=None, bg=None, trace=None, expect_exit=0, **kw):
        type(self).n += 1
        out = os.path.join(TMP, f"run{self.n}")
        cmd = [BIN, "--out", out, "--fg", fg or self.fg, "--bg", bg or self.bg,
               "--trace", trace or self.trace, "--warmup-s", "0.2", "--duration-s", "1.5",
               "--window-ms", "250", "--run-id", f"test{self.n}"] + list(args)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, expect_exit, p.stderr)
        meta = load_json(os.path.join(out, "run_meta.json"))
        return meta, read_csv(os.path.join(out, "requests.csv")), read_csv(os.path.join(out, "windows.csv"))

    def check_accounting(self, meta, reqs):
        c = meta["counts"]
        self.assertTrue(meta["accounting_ok"])
        self.assertEqual(c["accepted"], c["submitted"] + c["unsubmitted"])
        self.assertEqual(c["submitted"], c["completed_ok"] + c["completed_err"])
        ids = [r["req_id"] for r in reqs]
        self.assertEqual(len(ids), len(set(ids)), "a request was logged twice")
        self.assertEqual(len(reqs), c["accepted"] + c["rejected"])
        for r in reqs:
            if r["status"] in ("OK", "ERR"):
                self.assertTrue(r["t_submit"] and r["t_complete"], r)
                self.assertLessEqual(int(r["t_arrival"]), int(r["t_submit"]))
                self.assertLessEqual(int(r["t_submit"]), int(r["t_complete"]))

    # 1. verified contents -------------------------------------------------
    def test_verified_contents(self):
        meta, reqs, _ = self.run_d("--mode", "mixed", "--q", "4")
        self.check_accounting(meta, reqs)
        ok = [r for r in reqs if r["status"] == "OK"]
        self.assertGreater(len([r for r in ok if r["class"] == "FG"]), 100)
        self.assertGreater(len([r for r in ok if r["class"] == "BG"]), 10)
        self.assertTrue(all(r["verified"] == "1" for r in ok))
        self.assertEqual(meta["counts"]["completed_err"], 0)

    def test_corrupted_data_detected(self):
        bad = os.path.join(TMP, "fg_bad.dat")
        shutil.copy(self.fg, bad)
        with open(bad, "r+b") as f:                        # flip one byte in block 10
            f.seek(10 * BLOCK + 100)
            f.write(b"\xff")
        tr = os.path.join(TMP, "trace_bad.csv")
        write_trace(tr, [(1_000_000 * (i + 1), (10 if i % 2 else 11) * BLOCK) for i in range(40)])
        meta, reqs, _ = self.run_d("--mode", "fg", fg=bad, trace=tr)
        self.check_accounting(meta, reqs)
        errs = [r for r in reqs if r["status"] == "ERR"]
        self.assertEqual(len(errs), 20)
        self.assertTrue(all(r["errno"] == str(EBADMSG) and r["offset"] == str(10 * BLOCK) for r in errs))
        self.assertEqual(meta["counts"]["verify_fail"], 20)

    # 2. end of file ---------------------------------------------------------
    def test_end_of_file(self):
        meta, reqs, _ = self.run_d("--mode", "bg", "--q", "8")
        self.check_accounting(meta, reqs)
        self.assertGreater(meta["counts"]["scan_wraps"], 0, "scan should wrap at the end of the file")
        last = [r for r in reqs if r["class"] == "BG" and r["offset"] == str(16 * 262144) and r["status"] == "OK"]
        self.assertTrue(last, "the short last chunk was never read")
        self.assertEqual(meta["counts"]["completed_err"], 0)
        # FG reads at the last block work; a read past the end is an explicit error
        tr = os.path.join(TMP, "trace_eof.csv")
        write_trace(tr, [(1_000_000, (self.fg_blocks - 1) * BLOCK), (2_000_000, self.fg_blocks * BLOCK)])
        meta, reqs, _ = self.run_d("--mode", "fg", trace=tr)
        self.check_accounting(meta, reqs)
        by_off = {int(r["offset"]): r for r in reqs}
        self.assertEqual(by_off[(self.fg_blocks - 1) * BLOCK]["status"], "OK")
        self.assertEqual(by_off[self.fg_blocks * BLOCK]["status"], "ERR")
        self.assertEqual(by_off[self.fg_blocks * BLOCK]["errno"], str(EIO))

    # 3. full pending queue --------------------------------------------------
    def test_full_queue_rejects(self):
        tr = os.path.join(TMP, "trace_burst.csv")
        write_trace(tr, [(1000 + i, (i % self.fg_blocks) * BLOCK) for i in range(500)])
        meta, reqs, wins = self.run_d("--mode", "fg", "--fg-quota", "1", "--fg-cap", "16", trace=tr)
        self.check_accounting(meta, reqs)
        rej = [r for r in reqs if r["status"] == "REJECTED"]
        self.assertGreater(len(rej), 400)
        self.assertEqual(len(rej), meta["counts"]["rejected"])
        self.assertEqual(meta["counts"]["accepted"] + meta["counts"]["rejected"], 500)
        self.assertTrue(all(r["t_submit"] == "" for r in rej))
        self.assertEqual(int(wins[-1]["rejected_total"]), len(rej))

    # 4. read errors ---------------------------------------------------------
    def test_read_error_logged(self):
        fault = (0 * 7919 % self.fg_blocks) * BLOCK          # first trace offset (block 0)
        meta, reqs, _ = self.run_d("--mode", "mixed", "--q", "2", "--fault-offset", str(fault))
        self.check_accounting(meta, reqs)
        errs = [r for r in reqs if r["status"] == "ERR"]
        self.assertTrue(errs)
        self.assertTrue(all(r["errno"] == str(EBADF) and int(r["offset"]) == fault for r in errs))
        self.assertGreater(meta["counts"]["completed_ok"], 100, "the run must continue after an error")

    # 5. shutdown with reads in flight --------------------------------------
    def test_shutdown_ctrl_c(self):
        out = os.path.join(TMP, "run_sigint")
        p = subprocess.Popen([BIN, "--out", out, "--mode", "mixed", "--q", "8", "--fg", self.fg,
                              "--bg", self.bg, "--trace", self.trace, "--warmup-s", "0",
                              "--duration-s", "60"], stderr=subprocess.PIPE, text=True)
        time.sleep(1.0)
        p.send_signal(signal.SIGINT)
        _, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        meta = load_json(os.path.join(out, "run_meta.json"))
        reqs = read_csv(os.path.join(out, "requests.csv"))
        self.assertTrue(meta["stopped_by_signal"])
        self.check_accounting(meta, reqs)
        self.assertGreater(meta["counts"]["submitted"], 0)

    def test_shutdown_early_stop(self):
        meta, reqs, _ = self.run_d("--mode", "mixed", "--q", "8", "--stop-after-ms", "400")
        self.check_accounting(meta, reqs)
        last_t = max(int(r["t_complete"]) for r in reqs if r["t_complete"])
        self.assertLess(last_t, 2_000_000_000, "should stop soon after 0.4 s")

    # limits (Tariq: record the ACTUAL outstanding count) --------------------
    def test_q_and_quota_limits(self):
        for q in (1, 2, 4, 8):
            meta, reqs, wins = self.run_d("--mode", "mixed", "--q", str(q), "--fg-quota", "2")
            self.check_accounting(meta, reqs)
            bg = [r for r in reqs if r["class"] == "BG" and r["t_submit"]]
            fg = [r for r in reqs if r["class"] == "FG" and r["t_submit"]]
            self.assertTrue(all(int(r["bg_out_at_submit"]) < q for r in bg), f"q={q} exceeded")
            self.assertTrue(all(int(r["fg_out_at_submit"]) < 2 for r in fg), "FG quota exceeded")
            self.assertTrue(all(int(w["bg_out_max"]) <= q for w in wins))
            self.assertTrue(all(float(w["bg_out_mean"]) <= q + 1e-6 for w in wins))
            self.assertTrue(all(w["q_config"] == str(q) for w in wins))

    def test_same_trace_same_requests(self):
        _, a, _ = self.run_d("--mode", "fg")
        _, b, _ = self.run_d("--mode", "fg")
        fa = [(r["t_arrival"], r["offset"]) for r in a if r["class"] == "FG"]
        fb = [(r["t_arrival"], r["offset"]) for r in b if r["class"] == "FG"]
        self.assertEqual(sorted(fa), sorted(fb))

    def test_bad_arguments(self):
        p = subprocess.run([BIN, "--mode", "mixed", "--out", os.path.join(TMP, "x"), "--q", "9",
                            "--fg", self.fg, "--bg", self.bg, "--trace", self.trace],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
