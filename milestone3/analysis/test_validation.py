"""Regression tests for admission to final summaries and target freezing."""
import copy
import unittest
import pandas as pd
from validate_logs import validate_run, validate_dataset
import study_a


def valid_run(mode='mixed', q=1, rep=1):
    meta = dict(run_id=f'{mode}_{q}_{rep}', mode=mode, q=q, repetition=rep,
                warmup_ns=0, duration_ns=1_000_000_000, accounting_ok=True, direct_io=True,
                stopped_by_signal=False, run_status='completed', fg_quota=4,
                fg_queue_cap=256, bg_queue_cap=16, chunk_bytes=262144, window_ms=500,
                fg_path='fg.dat', bg_path='bg.dat', trace='trace.csv', cpu=1, device='/dev/sda',
                bg_start_offset=0)
    rows = []
    if mode != 'bg':
        rows.append(dict(req_id=1, **{'class': 'FG'}, offset=0, len=4096, t_arrival=0,
                         t_submit=100, t_complete=200, status='OK', errno=0, verified=1,
                         q_at_submit=q, bg_out_at_submit=0, fg_out_at_submit=0))
    if mode != 'fg':
        rows.append(dict(req_id=2, **{'class': 'BG'}, offset=0, len=262144, t_arrival=0,
                         t_submit=100, t_complete=300, status='OK', errno=0, verified=1,
                         q_at_submit=q, bg_out_at_submit=0, fg_out_at_submit=0))
    req = pd.DataFrame(rows)
    meta['counts'] = dict(accepted=len(req), rejected=0, submitted=len(req),
                          completed_ok=len(req), completed_err=0, unsubmitted=0,
                          fg_ok=int(mode != 'bg'), bg_ok=int(mode != 'fg'), verify_fail=0,
                          scan_bytes_total=262144 if mode != 'fg' else 0)
    windows = pd.DataFrame([dict(t_start=0, t_end=1_000_000_000, q_config=q,
                                 bg_out_max=1, bg_out_mean=.5, ctrl_cpu_ns=10)])
    trace = pd.DataFrame([dict(t_ns=0, offset=0)])
    return meta, req, windows, trace


class ValidationTests(unittest.TestCase):
    def test_valid_run(self):
        self.assertEqual(validate_run(*valid_run()), [])

    def test_interrupt_rejected(self):
        m, r, w, t = valid_run(); m['stopped_by_signal'] = True
        self.assertTrue(validate_run(m, r, w, t))

    def test_early_end_rejected(self):
        m, r, w, t = valid_run(); w.loc[0, 't_end'] = 500
        self.assertTrue(validate_run(m, r, w, t))

    def test_missing_direct_flag_rejected(self):
        m, r, w, t = valid_run(); del m['direct_io']
        self.assertTrue(validate_run(m, r, w, t))

    def test_duplicate_id_rejected(self):
        m, r, w, t = valid_run(); r.loc[1, 'req_id'] = 1
        self.assertTrue(validate_run(m, r, w, t))

    def test_wrong_trace_rejected(self):
        m, r, w, t = valid_run(); t.loc[0, 'offset'] = 4096
        self.assertTrue(validate_run(m, r, w, t))

    def test_missing_trace_rejected(self):
        m, r, w, _ = valid_run()
        self.assertTrue(validate_run(m, r, w))

    def test_inconsistent_counters_rejected(self):
        m, r, w, t = valid_run(); m['counts']['submitted'] += 1
        self.assertTrue(validate_run(m, r, w, t))

    def test_legacy_tail_ambiguity_rejected(self):
        m, r, w, t = valid_run(); m['counts']['scan_bytes_total'] = 12288
        self.assertTrue(validate_run(m, r, w, t))

    def test_actual_tail_bytes_used_by_metrics(self):
        m, r, w, t = valid_run()
        r['bytes_read'] = [4096, 12288]
        r['t_admit'] = [50, 50]; r['t_verify'] = [400, 400]
        m['counts']['scan_bytes_total'] = 12288
        self.assertEqual(validate_run(m, r, w, t), [])
        metrics = study_a.run_metrics(m, r, w, None)
        self.assertEqual(metrics['scan_bytes'], 12288)
        self.assertEqual(metrics['scan_mib_s'], 12288 / 1048576)

    def test_invalid_run_excluded_before_summary(self):
        m, r, w, _ = valid_run(); m['accounting_ok'] = False
        metrics = study_a.run_metrics(m, r, w, None)
        with self.assertRaises(ValueError):
            study_a.summarize([metrics])

    def test_full_dataset_and_missing_repetition(self):
        metas = [valid_run(mode, q, rep)[0] for rep in (1, 2, 3)
                 for mode, q in [('fg', 1)] + [(m, q) for m in ('bg', 'mixed') for q in (1, 2, 4, 8)]]
        self.assertEqual(validate_dataset(metas), [])
        self.assertTrue(validate_dataset(metas[:-1]))

    def test_duplicate_repetition(self):
        metas = [valid_run(mode, q, rep)[0] for rep in (1, 2, 3)
                 for mode, q in [('fg', 1)] + [(m, q) for m in ('bg', 'mixed') for q in (1, 2, 4, 8)]]
        metas[-1]['repetition'] = 2
        self.assertTrue(validate_dataset(metas))
