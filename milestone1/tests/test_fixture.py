#!/usr/bin/env python3
"""Portable tests of fixture generation only; these do not test Linux I/O."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from create_fixture import approved_directory, create_file, expected_byte, pattern_bytes


class FixtureTests(unittest.TestCase):
    def test_known_pattern_values(self):
        self.assertEqual(expected_byte(0), 0)
        self.assertEqual(expected_byte(1), 17)
        self.assertEqual(expected_byte(256), 1)
        self.assertEqual(expected_byte(4096), 37)
        self.assertEqual(expected_byte(1048576), 53)

    def test_slices_preserve_absolute_offsets(self):
        content = pattern_bytes(0, 13000)
        self.assertEqual(content[4096:8192], pattern_bytes(4096, 4096))
        self.assertEqual(content[4093:4113], pattern_bytes(4093, 20))

    def test_file_size_content_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.bin'
            digest = create_file(path, 70000)
            data = path.read_bytes()
            self.assertEqual(data, pattern_bytes(0, 70000))
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())

    def test_existing_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.bin'
            path.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                create_file(path, 4096)
            self.assertEqual(path.read_bytes(), b'original')

    def test_empty_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.bin'
            self.assertEqual(create_file(path, 0), hashlib.sha256(b'').hexdigest())
            self.assertEqual(path.stat().st_size, 0)

    def test_root_directory_rejected(self):
        with self.assertRaises(ValueError):
            approved_directory(Path.cwd().anchor)

    def test_negative_size_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'negative.bin'
            with self.assertRaises(ValueError):
                create_file(path, -1)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
