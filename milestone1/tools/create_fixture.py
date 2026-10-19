#!/usr/bin/env python3
"""Create a new, known-pattern regular file. Existing files are never replaced."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def expected_byte(position):
    within = position & 4095
    return ((position >> 12) * 37 + within * 17 + (within >> 8)
            + (position >> 20) * 53) & 255


def pattern_bytes(offset, length):
    return bytes(expected_byte(position) for position in range(offset, offset + length))


def approved_directory(value):
    directory = Path(value).expanduser().resolve(strict=True)
    if not directory.is_dir() or directory == Path(directory.anchor):
        raise ValueError('Supply an existing approved test directory, not a file or filesystem root.')
    return directory


def create_file(path, size):
    """Exclusive create, bounded chunk writes, fsync, return content SHA-256."""
    path = Path(path)
    if size < 0 or size > 64 * 1024 * 1024:
        raise ValueError('Fixture size must be between 0 and 64 MiB.')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(str(path), flags, 0o600)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, 'wb') as stream:
        position = 0
        while position < size:
            chunk = pattern_bytes(position, min(65536, size - position))
            stream.write(chunk)
            digest.update(chunk)
            position += len(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-dir', required=True)
    parser.add_argument('--confirm-approved', action='store_true')
    parser.add_argument('--size-mib', type=int, default=4, choices=range(1, 65), metavar='1..64')
    args = parser.parse_args()
    if not args.confirm_approved:
        parser.error('Confirm the permitted directory with the course team/instructor, then use --confirm-approved.')
    try:
        parent = approved_directory(args.approved_dir)
        directory = Path(tempfile.mkdtemp(prefix='mostafa_m1_', dir=str(parent)))
        path = directory / 'known.bin'
        digest = create_file(path, args.size_mib * 1024 * 1024)
        record = {'file': str(path), 'size_bytes': path.stat().st_size,
                  'sha256': digest, 'pattern': 'milestone1-offset-pattern-v1'}
        (directory / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(record, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, 'Fixture setup failed: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
