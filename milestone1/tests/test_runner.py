#!/usr/bin/env python3
"""Portable checks that the log runner does not mislabel failures as passes."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_tests import run_case


class OutcomeTests(unittest.TestCase):
    def outcome(self, code, expected, text='', token=None):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, '-c',
                       'import sys; print(' + repr(text) + '); sys.exit(' + str(code) + ')']
            result = run_case(command, expected, Path(directory), 'outcome', token)
            self.assertTrue((Path(directory) / 'outcome.log').is_file())
            return result['status']

    def test_success_requires_expected_exit(self):
        self.assertEqual(self.outcome(0, 0), 'PASS')

    def test_expected_short_read_error_can_pass(self):
        self.assertEqual(self.outcome(7, 7, 'SHORT_READ', 'SHORT_READ'), 'PASS')

    def test_unexpected_error_fails(self):
        self.assertEqual(self.outcome(6, 0), 'FAIL')

    def test_missing_verification_marker_fails(self):
        self.assertEqual(self.outcome(0, 0, 'unverified', 'PASS:'), 'FAIL')

    def test_environment_blocker_is_not_a_pass(self):
        self.assertEqual(self.outcome(77, 0), 'BLOCKED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
