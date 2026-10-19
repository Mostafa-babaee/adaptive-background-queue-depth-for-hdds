#!/usr/bin/env python3
"""Linux integration tests for the milestone smoke test, not HDD benchmarks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from create_fixture import approved_directory, create_file  # noqa: E402


def run_case(command, expected, directory, name, token=None):
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, timeout=60)
        output = process.stdout + '\n' + process.stderr
        code = process.returncode
        status = 'PASS' if code == expected and (token is None or token in output) else 'FAIL'
        if code == 77:
            status = 'BLOCKED'
    except subprocess.TimeoutExpired as exc:
        code, status = None, 'FAIL'
        output = 'Timed out after 60 seconds. This is not a successful completion.\n'
        for part in (exc.stdout, exc.stderr):
            if part:
                output += part.decode(errors='replace') if isinstance(part, bytes) else part
    except OSError as exc:
        code, status, output = None, 'BLOCKED', str(exc)
    log = directory / (name + '.log')
    log.write_text('command=' + json.dumps(command) + '\nexpected_exit=' + str(expected)
                   + '\nactual_exit=' + str(code) + '\n\n' + output, encoding='utf-8')
    record = {'test': name, 'status': status, 'expected_exit': expected,
              'actual_exit': code, 'log': str(log)}
    print(status + ': ' + name, flush=True)
    return record


def save_summary(directory, records, fixture_directory=None, metadata=None):
    summary = {'host': platform.node(), 'platform': platform.platform(),
               'utc': datetime.now(timezone.utc).isoformat(),
               'fixture_directory': str(fixture_directory) if fixture_directory else None,
               'fixture_metadata': metadata, 'tests': records,
               'note': 'Functional checks only. No HDD placement or performance conclusion.'}
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    lines = ['# Milestone 1 test results', '', 'Host: ' + summary['host'],
             'UTC: ' + summary['utc'], '', '| Test | Outcome |', '|---|---|']
    lines.extend('| ' + record['test'] + ' | ' + record['status'] + ' |' for record in records)
    lines += ['', 'Fixtures: ' + str(fixture_directory), '', summary['note'], '']
    (directory / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Results: ' + str(directory), flush=True)
    if fixture_directory:
        print('Fixtures retained: ' + str(fixture_directory), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-dir', required=True)
    parser.add_argument('--confirm-approved', action='store_true')
    args = parser.parse_args()
    if not args.confirm_approved:
        parser.error('Use --confirm-approved only after confirming the team HDD test directory.')
    if platform.system() != 'Linux':
        parser.exit(77, 'BLOCKED: this integration suite requires Linux and liburing.\n')
    try:
        parent = approved_directory(args.approved_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, 'Invalid test directory: ' + str(exc) + '\n')
    (ROOT / 'results').mkdir(exist_ok=True)
    results = Path(tempfile.mkdtemp(prefix='suite_', dir=str(ROOT / 'results')))
    records = [run_case(['bash', str(ROOT / 'scripts' / 'build.sh')], 0, results, 'build')]
    if records[0]['status'] != 'PASS':
        save_summary(results, records)
        return 77 if records[0]['status'] == 'BLOCKED' else 1
    try:
        fixtures = Path(tempfile.mkdtemp(prefix='mostafa_m1_', dir=str(parent)))
        known = fixtures / 'known.bin'
        digest = create_file(known, 4 * 1024 * 1024)
        metadata = {'known_size': known.stat().st_size, 'known_sha256': digest,
                    'pattern': 'milestone1-offset-pattern-v1'}
        (fixtures / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    except (OSError, ValueError) as exc:
        records.append({'test': 'fixture_setup', 'status': 'BLOCKED', 'detail': str(exc)})
        save_summary(results, records)
        return 77

    binary = str(ROOT / 'build' / 'smoke_read')
    first = run_case([binary, str(known), '0', '4096', '1'], 0, results,
                     'read_first_4k', 'PASS: 1 reads completed and verified.')
    records.append(first)
    if first['status'] == 'PASS':
        try:
            empty = fixtures / 'empty.bin'
            partial = fixtures / 'partial.bin'
            corrupt = fixtures / 'corrupt.bin'
            create_file(empty, 0)
            create_file(partial, 6144)
            create_file(corrupt, 4096)
            with corrupt.open('r+b') as stream:
                stream.write(b'\xff')  # pattern byte at offset 0 is 0
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            records.append({'test': 'negative_fixture_setup', 'status': 'BLOCKED', 'detail': str(exc)})
            save_summary(results, records, fixtures, metadata)
            return 77
        cases = [
            ('read_offset_repeated', [str(known), '4096', '4096', '8'], 0, 'PASS: 8 reads'),
            ('read_256k', [str(known), '3145728', '262144', '1'], 0, 'PASS: 1 reads'),
            ('read_last_4k', [str(known), str(4 * 1024 * 1024 - 4096), '4096'], 0, 'PASS: 1 reads'),
            ('missing_file', [str(fixtures / 'does_not_exist.bin')], 3, None),
            ('directory_rejected', [str(fixtures)], 4, 'Rejected'),
            ('invalid_offset', [str(known), '1'], 2, 'Usage:'),
            ('invalid_length', [str(known), '0', '4095'], 2, 'Usage:'),
            ('invalid_count', [str(known), '0', '4096', '0'], 2, 'Usage:'),
            ('read_at_eof', [str(known), str(4 * 1024 * 1024)], 7, 'SHORT_READ'),
            ('read_empty', [str(empty)], 7, 'SHORT_READ'),
            ('read_partial_last_block', [str(partial), '4096'], 7, 'SHORT_READ'),
            ('detect_corruption', [str(corrupt)], 8, 'VERIFY_ERROR'),
        ]
        for name, arguments, expected, token in cases:
            records.append(run_case([binary] + arguments, expected, results, name, token))
    else:
        records.append({'test': 'remaining_tests', 'status': 'NOT_RUN',
                        'detail': 'Initial verified direct read did not pass; inspect its log first.'})

    with known.open('rb') as stream:
        after = hashlib.sha256(stream.read()).hexdigest()
    records.append({'test': 'original_fixture_unchanged',
                    'status': 'PASS' if after == digest else 'FAIL'})
    save_summary(results, records, fixtures, metadata)
    if any(record['status'] == 'FAIL' for record in records):
        return 1
    if any(record['status'] != 'PASS' for record in records):
        return 77
    return 0


if __name__ == '__main__':
    sys.exit(main())
