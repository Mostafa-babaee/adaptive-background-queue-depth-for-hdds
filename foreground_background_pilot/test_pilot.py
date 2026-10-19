"""Portable scheduler/analysis tests with a fake I/O backend, not server measurements."""
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch
import pilot
from pilot import (BG_BYTES, FG_BYTES, MIB, NS, calculate_stats, foreground_trace,
                   pattern_bytes, percentile, run_case, save_case)


class FakeReader:
    def __init__(self, delay=.002, status='ok'):
        self.delay = delay
        self.status = status

    def read(self, offset, length):
        started = time.monotonic_ns()
        time.sleep(self.delay)
        return {'status': self.status, 'bytes_read': length if self.status == 'ok' else 0,
                'error': '' if self.status == 'ok' else 'injected verification error',
                'io_started_ns': started, 'io_completed_ns': time.monotonic_ns()}


class PilotTests(unittest.TestCase):
    def run_small(self, mode='mixed', q=2, seconds=.08, rate=50, reader=None, pending=64):
        return run_case(reader or FakeReader(), 4 * MIB, mode, q, seconds, rate,
                        720, 1, pending, 8)

    def test_foreground_schedule_does_not_depend_on_policy(self):
        first = foreground_trace(4 * MIB, 5, 10, 720)
        self.assertEqual(first, foreground_trace(4 * MIB, 5, 10, 720))
        self.assertEqual(len(first), 50)
        self.assertEqual(first[1][0], NS // 10)
        self.assertTrue(all(offset % FG_BYTES == 0 for _, offset in first))

    def test_fixture_pattern_matches_milestone_values(self):
        data = pattern_bytes(4097)
        self.assertEqual([data[0], data[1], data[256], data[4096]], [0, 17, 1, 37])

    def test_nearest_rank_and_empty_percentile(self):
        self.assertIsNone(percentile([], .99))
        self.assertEqual(percentile([4, 1, 3, 2], .5), 2)
        self.assertEqual(percentile([4, 1, 3, 2], .99), 4)

    def test_foreground_only_has_no_background_reads(self):
        rows, stats = self.run_small(mode='foreground_only')
        self.assertEqual(stats['foreground_offered'], 4)
        self.assertEqual(stats['foreground_successful'], 4)
        self.assertTrue(all(row['workload'] == 'foreground' for row in rows))
        self.assertEqual(stats['background_verified_bytes'], 0)

    def test_background_only_has_no_foreground_reads(self):
        rows, stats = self.run_small(mode='background_only')
        self.assertEqual(stats['foreground_offered'], 0)
        self.assertIsNone(stats['foreground_p99_ms'])
        self.assertTrue(rows)
        self.assertTrue(all(row['workload'] == 'background' for row in rows))

    def test_mixed_caps_ids_and_timestamps(self):
        rows, stats = self.run_small(reader=FakeReader(.008))
        self.assertLessEqual(stats['maximum_foreground_outstanding_jobs'], 1)
        self.assertEqual(stats['maximum_background_outstanding_jobs'], 2)
        self.assertTrue(stats['foreground_accounting_ok'])
        self.assertTrue(stats['unique_request_ids_ok'])
        self.assertEqual(len({row['request_id'] for row in rows}), len(rows))
        for row in rows:
            self.assertLessEqual(row['intended_arrival_ns'], row['admitted_ns'])
            self.assertLessEqual(row['admitted_ns'], row['job_submitted_ns'])
            self.assertLessEqual(row['job_submitted_ns'], row['io_started_ns'])
            self.assertLessEqual(row['io_started_ns'], row['io_completed_ns'])
            self.assertLessEqual(row['io_completed_ns'], row['observed_ns'])

    def test_overload_rejections_are_retained(self):
        rows, stats = self.run_small(mode='foreground_only', seconds=.03,
                                     rate=1000, reader=FakeReader(.01), pending=1)
        self.assertEqual(stats['foreground_offered'], 30)
        self.assertGreater(stats['foreground_rejected'], 0)
        self.assertEqual(len(rows), 30)
        self.assertTrue(stats['foreground_accounting_ok'])

    def test_failed_reads_not_counted_as_success_or_progress(self):
        rows, stats = self.run_small(reader=FakeReader(status='verify_error'))
        self.assertGreater(stats['errors'], 0)
        self.assertEqual(stats['background_verified_bytes'], 0)
        self.assertEqual(stats['foreground_successful'], 0)
        self.assertIsNone(stats['foreground_p99_ms'])
        self.assertTrue(stats['foreground_accounting_ok'])

    def test_no_default_target_and_explicit_target_denominator(self):
        rows = [dict(workload='foreground', status='ok', intended_arrival_ns=0,
                     observed_ns=2_000_000, io_started_ns=0, io_completed_ns=1_000_000,
                     bytes_read=4096)]
        self.assertIsNone(calculate_stats(rows, 1)['target_miss_fraction_successful_reads_only'])
        self.assertEqual(calculate_stats(rows, 1, 1)['target_miss_fraction_successful_reads_only'], 1)

    def test_result_files_do_not_overwrite_existing_case(self):
        rows, stats = self.run_small(mode='foreground_only', seconds=.02, rate=50)
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parent)) as parent:
            directory = Path(parent) / 'case'
            save_case(directory, rows, stats)
            original = (directory / 'requests.csv').read_bytes()
            with self.assertRaises(FileExistsError):
                save_case(directory, rows, stats)
            self.assertEqual((directory / 'requests.csv').read_bytes(), original)

    def test_interrupt_is_marked_and_submitted_work_is_drained(self):
        actual_wait = pilot.wait
        calls = [0]
        def interrupt_once(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise KeyboardInterrupt()
            return actual_wait(*args, **kwargs)
        with patch('pilot.wait', side_effect=interrupt_once):
            rows, stats = self.run_small(reader=FakeReader(.008))
        self.assertTrue(stats['interrupted'])
        self.assertTrue(stats['foreground_accounting_ok'])
        self.assertTrue(stats['unique_request_ids_ok'])
        self.assertTrue(rows)


if __name__ == '__main__':
    unittest.main(verbosity=2)
