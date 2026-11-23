import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import make_testfiles


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / 'results').mkdir(exist_ok=True)

    def test_generator_handles_partial_writes(self):
        (ROOT / 'results').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as folder:
            path = Path(folder) / 'fixture.dat'
            original = os.write
            def short_write(fd, buf):
                return original(fd, buf[:10000])
            with patch('make_testfiles.os.write', side_effect=short_write):
                make_testfiles.create(str(path), 1, 1)
            self.assertEqual(path.stat().st_size, 1048576)
            make_testfiles.verify(str(path), 1)

    def test_existing_fixture_not_replaced(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as folder:
            path = Path(folder) / 'existing.dat'; path.write_bytes(b'keep')
            with self.assertRaises(SystemExit):
                make_testfiles.create(str(path), 1, 1)
            self.assertEqual(path.read_bytes(), b'keep')

    def test_invalid_fixture_size(self):
        with self.assertRaises(ValueError):
            make_testfiles.create('not_created.dat', -1, 1)

    def test_trace_repeatability_and_exclusive_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as folder:
            a, b = Path(folder) / 'a.csv', Path(folder) / 'b.csv'
            args = [sys.executable, str(ROOT / 'tools/make_trace.py'), '--fg-bytes', '1048576',
                    '--rate', '50', '--seconds', '1', '--seed', '42']
            for out in [a, b]:
                subprocess.run(args + ['--out', str(out)], check=True, capture_output=True)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            before = a.read_bytes()
            result = subprocess.run(args + ['--out', str(a)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, a.read_bytes())
