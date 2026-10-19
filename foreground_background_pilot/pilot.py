#!/usr/bin/env python3
"""Short threaded-direct-read pilot. Not the C/io_uring dispatcher or an HDD benchmark."""
import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import platform
import random
import stat
import sys
import tempfile
import threading
import time

KIB = 1024
MIB = 1024 * KIB
FG_BYTES = 4 * KIB
BG_BYTES = 256 * KIB
NS = 1_000_000_000
FIELDS = ['request_id', 'workload', 'status', 'offset_bytes', 'length_bytes',
          'intended_arrival_ns', 'admitted_ns', 'job_submitted_ns', 'io_started_ns',
          'io_completed_ns', 'observed_ns', 'bytes_read', 'error',
          'foreground_outstanding_jobs', 'background_outstanding_jobs',
          'pending_foreground', 'q']


def pattern_bytes(size):
    # Same offset-dependent pattern as Milestone 1's fixture generator and C test.
    return bytes((((p >> 12) * 37 + (p & 4095) * 17 + ((p & 4095) >> 8)
                   + (p >> 20) * 53) & 255) for p in range(size))


def foreground_trace(size, seconds, rate, seed):
    """Open-loop relative arrivals and offsets, independent of completion speed."""
    rng = random.Random(seed)
    return [(index * NS // rate, rng.randrange(size // FG_BYTES) * FG_BYTES)
            for index in range(int(seconds * rate))]


def percentile(values, fraction):
    """Nearest-rank percentile; None for no observations."""
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def calculate_stats(rows, elapsed, target_ms=None):
    successful_fg = [r for r in rows if r['workload'] == 'foreground' and r['status'] == 'ok']
    latency = [(r['observed_ns'] - r['intended_arrival_ns']) / 1e6 for r in successful_fg]
    io_latency = [(r['io_completed_ns'] - r['io_started_ns']) / 1e6 for r in successful_fg]
    bg_bytes = sum(r['bytes_read'] for r in rows if r['workload'] == 'background' and r['status'] == 'ok')
    errors = sum(r['status'] not in ('ok', 'rejected') for r in rows)
    rejected = sum(r['status'] == 'rejected' for r in rows)
    return {
        'foreground_successful': len(successful_fg), 'foreground_rejected': rejected,
        'foreground_errors': sum(r['workload'] == 'foreground' and r['status'] not in ('ok', 'rejected') for r in rows),
        'background_errors': sum(r['workload'] == 'background' and r['status'] != 'ok' for r in rows),
        'errors': errors, 'foreground_p50_ms': percentile(latency, .5),
        'foreground_p95_ms': percentile(latency, .95),
        'foreground_p99_ms': percentile(latency, .99),
        'foreground_io_p50_ms': percentile(io_latency, .5),
        'foreground_target_ms': target_ms,
        'target_miss_fraction_successful_reads_only': (
            sum(value > target_ms for value in latency) / len(latency)
            if target_ms is not None and latency else None),
        'background_verified_bytes': bg_bytes,
        'background_mib_s_including_drain': bg_bytes / MIB / elapsed,
        'elapsed_seconds_including_drain': elapsed,
        'tail_estimate_warning': 'Exploratory only; short run and small sample count. Not a reliable final p99 estimate.'
    }


class DirectReader:
    """One read-only descriptor; each worker gets an anonymous page-aligned buffer."""
    def __init__(self, path, expected):
        if platform.system() != 'Linux' or not hasattr(os, 'preadv') or not hasattr(os, 'O_DIRECT'):
            raise RuntimeError('Linux with os.preadv and O_DIRECT is required; there is no buffered fallback.')
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise ValueError('Use a regular known-pattern file, not a symlink, directory, or raw device.')
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECT | os.O_NOFOLLOW | os.O_NONBLOCK)
        opened = os.fstat(self.fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size != len(expected):
            os.close(self.fd)
            raise ValueError('Opened object is not the expected size of regular file.')
        self.expected = expected
        self.local = threading.local()
        self.buffers = []
        self.lock = threading.Lock()

    def read(self, offset, length):
        started = time.monotonic_ns()
        completed = started
        amount = 0
        status, error = 'io_error', ''
        try:
            if not hasattr(self.local, 'buffer'):
                area = mmap.mmap(-1, BG_BYTES)
                self.local.buffer = area
                with self.lock:
                    self.buffers.append(area)
            area = self.local.buffer
            view = memoryview(area)[:length]
            try:
                started = time.monotonic_ns()
                amount = os.preadv(self.fd, [view], offset)
                completed = time.monotonic_ns()
            finally:
                view.release()
            if amount != length:
                status, error = 'short_read', 'Expected %d bytes; got %d' % (length, amount)
            elif area[:amount] != self.expected[offset:offset + amount]:
                status, error = 'verify_error', 'Known-pattern bytes do not match'
            else:
                status = 'ok'
        except (OSError, ValueError) as exc:
            completed = time.monotonic_ns()
            error = str(exc)
        return {'status': status, 'bytes_read': amount, 'error': error,
                'io_started_ns': started, 'io_completed_ns': completed}

    def close(self):
        # Called only after the executor has joined its worker threads.
        for area in self.buffers:
            area.close()
        self.buffers.clear()
        os.close(self.fd)


def run_case(reader, size, mode, q, seconds, rate, seed, foreground_limit,
             pending_limit, background_mib_s, target_ms=None):
    """One common scheduler for foreground-only, background-only, and mixed runs."""
    trace = foreground_trace(size, seconds, rate, seed) if mode != 'background_only' else []
    pending = deque()
    futures = {}
    rows = []
    next_arrival = 0
    next_id = len(trace) + 1
    background_offset = 0
    foreground_outstanding = background_outstanding = 0
    maximum_fg = maximum_bg = maximum_pending = 0
    # Same maximum burst and executor size for every q; q is enforced separately.
    tokens = 8 * BG_BYTES
    bytes_per_second = background_mib_s * MIB
    cpu_start = time.process_time()
    start = time.monotonic_ns()
    end = start + int(seconds * NS)
    token_clock = start
    interrupted = False

    def observe(future, request):
        observed = time.monotonic_ns()
        try:
            result = future.result()
        except Exception as exc:
            result = {'status': 'worker_error', 'bytes_read': 0, 'error': str(exc),
                      'io_started_ns': request['job_submitted_ns'], 'io_completed_ns': observed}
        rows.append(dict(request, **result, observed_ns=observed,
                         foreground_outstanding_jobs=foreground_outstanding,
                         background_outstanding_jobs=background_outstanding,
                         pending_foreground=len(pending), q=q))

    with ThreadPoolExecutor(max_workers=foreground_limit + 8) as executor:
        try:
            while True:
                # Process finished jobs before admitting/submitting more work.
                for future in list(futures):
                    if future.done():
                        request = futures.pop(future)
                        if request['workload'] == 'foreground':
                            foreground_outstanding -= 1
                        else:
                            background_outstanding -= 1
                        observe(future, request)
                now = time.monotonic_ns()
                while next_arrival < len(trace) and start + trace[next_arrival][0] <= now:
                    relative, offset = trace[next_arrival]
                    request = {'request_id': next_arrival + 1, 'workload': 'foreground',
                               'offset_bytes': offset, 'length_bytes': FG_BYTES,
                               'intended_arrival_ns': start + relative, 'admitted_ns': now}
                    next_arrival += 1
                    if len(pending) >= pending_limit:
                        rows.append(dict(request, status='rejected', observed_ns=now,
                                         bytes_read=0, error='foreground pending queue full',
                                         foreground_outstanding_jobs=foreground_outstanding,
                                         background_outstanding_jobs=background_outstanding,
                                         pending_foreground=len(pending), q=q))
                    else:
                        pending.append(request)
                        maximum_pending = max(maximum_pending, len(pending))

                while pending and foreground_outstanding < foreground_limit:
                    request = pending.popleft()
                    request['job_submitted_ns'] = time.monotonic_ns()
                    future = executor.submit(reader.read, request['offset_bytes'], FG_BYTES)
                    futures[future] = request
                    foreground_outstanding += 1
                    maximum_fg = max(maximum_fg, foreground_outstanding)

                now = time.monotonic_ns()
                tokens = min(8 * BG_BYTES, tokens + (now - token_clock) / NS * bytes_per_second)
                token_clock = now
                if mode != 'foreground_only':
                    while now < end and background_outstanding < q and tokens >= BG_BYTES:
                        request = {'request_id': next_id, 'workload': 'background',
                                   'offset_bytes': background_offset, 'length_bytes': BG_BYTES,
                                   'intended_arrival_ns': now, 'admitted_ns': now,
                                   'job_submitted_ns': time.monotonic_ns()}
                        next_id += 1
                        future = executor.submit(reader.read, background_offset, BG_BYTES)
                        futures[future] = request
                        background_outstanding += 1
                        maximum_bg = max(maximum_bg, background_outstanding)
                        tokens -= BG_BYTES
                        background_offset += BG_BYTES
                        if background_offset + BG_BYTES > size:
                            background_offset = 0
                        now = time.monotonic_ns()

                if now >= end and next_arrival == len(trace) and not pending and not futures:
                    break
                pause = .005
                if next_arrival < len(trace):
                    pause = min(pause, max(0, (start + trace[next_arrival][0] - now) / NS))
                if now < end:
                    pause = min(pause, (end - now) / NS)
                pause = max(.00005, pause)
                if futures:
                    wait(list(futures), timeout=pause, return_when=FIRST_COMPLETED)
                else:
                    time.sleep(pause)
        except KeyboardInterrupt:
            interrupted = True
            # Stop new submissions, retain every accepted pending request as an explicit error.
            while pending:
                request = pending.popleft()
                rows.append(dict(request, status='shutdown_pending', observed_ns=time.monotonic_ns(),
                                 bytes_read=0, error='Interrupted before submission',
                                 foreground_outstanding_jobs=foreground_outstanding,
                                 background_outstanding_jobs=background_outstanding,
                                 pending_foreground=len(pending), q=q))
            for future, request in list(futures.items()):
                # Drain submitted reads; shutdown does not pretend to withdraw them.
                wait([future])
                if request['workload'] == 'foreground':
                    foreground_outstanding -= 1
                else:
                    background_outstanding -= 1
                observe(future, request)
            futures.clear()

    elapsed = (time.monotonic_ns() - start) / NS
    stats = calculate_stats(rows, elapsed, target_ms)
    stats.update(mode=mode, q=q, interrupted=interrupted, foreground_offered=next_arrival,
                 foreground_trace_size=len(trace), foreground_pending_limit=pending_limit,
                 foreground_outstanding_limit=foreground_limit,
                 maximum_foreground_outstanding_jobs=maximum_fg,
                 maximum_background_outstanding_jobs=maximum_bg,
                 maximum_pending_foreground=maximum_pending,
                 process_cpu_seconds=time.process_time() - cpu_start,
                 requested_seconds=seconds, foreground_rate=rate,
                 background_rate_cap_mib_s=background_mib_s,
                 background_initial_burst_bytes=8 * BG_BYTES)
    stats['foreground_accounting_ok'] = (stats['foreground_successful'] +
        stats['foreground_rejected'] + stats['foreground_errors'] == next_arrival)
    stats['unique_request_ids_ok'] = len({row['request_id'] for row in rows}) == len(rows)
    if not stats['foreground_accounting_ok'] or not stats['unique_request_ids_ok']:
        raise RuntimeError('Request accounting or unique-ID check failed; do not interpret this run as valid.')
    return rows, stats


def save_case(directory, rows, stats):
    directory.mkdir()
    with (directory / 'requests.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (directory / 'summary.json').write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')


def number_text(value):
    return '-' if value is None else '%.3f' % value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True, help='Existing Milestone 1 known.bin; opened read-only')
    parser.add_argument('--seconds', type=int, default=5, choices=range(1, 31), metavar='1..30')
    parser.add_argument('--fg-rate', type=int, default=10, choices=range(1, 201), metavar='1..200')
    parser.add_argument('--foreground-limit', type=int, default=1, choices=range(1, 5))
    parser.add_argument('--pending-limit', type=int, default=64, choices=range(1, 1025), metavar='1..1024')
    parser.add_argument('--background-mib-s', type=int, default=8, choices=range(1, 33), metavar='1..32')
    parser.add_argument('--repetitions', type=int, default=1, choices=range(1, 4))
    parser.add_argument('--seed', type=int, default=720)
    parser.add_argument('--target-ms', type=float, default=None, help='Optional measured target, not a made-up default')
    args = parser.parse_args()
    if args.target_ms is not None and (not math.isfinite(args.target_ms) or args.target_ms <= 0):
        parser.error('--target-ms must be finite and positive')
    path = Path(args.file).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        parser.error('Supply an existing regular known-pattern fixture, not a symlink or raw device')
    size = path.stat().st_size
    if size < BG_BYTES or size > 64 * MIB or size % FG_BYTES:
        parser.error('Use a 4-KiB-aligned fixture between 256 KiB and 64 MiB; the existing 4-MiB file is suitable')
    results_parent = Path(__file__).resolve().parent / 'results'
    results_parent.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='pilot_', dir=str(results_parent)))
    manifest = {'utc': datetime.now(timezone.utc).isoformat(), 'hostname': platform.node(),
                'kernel': platform.release(), 'python': sys.version, 'file': str(path), 'file_size': size,
                'backend': 'Python ThreadPoolExecutor + os.preadv + O_DIRECT',
                'configuration': vars(args), 'input_file_writes': False,
                'input_file_open_mode': 'O_RDONLY|O_DIRECT',
                'limitations': ['Small reused fixture; controller/drive caching remains.',
                                'Thread scheduling, Python and verification overhead affect latency.',
                                'q caps outstanding read jobs, not firmware queue depth.',
                                'Rate-limited short pilot, not the final single-HDD evaluation.',
                                'No controlled cache preparation or storage isolation.'],
                'status': 'started'}
    manifest_path = output / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Results: ' + str(output), flush=True)
    reader = None
    try:
        expected = pattern_bytes(size)  # Outside each timed run; does not read the fixture.
        reader = DirectReader(str(path), expected)
        for offset in (0, size - FG_BYTES):
            result = reader.read(offset, FG_BYTES)
            if result['status'] != 'ok':
                raise RuntimeError('Direct-read preflight failed: ' + json.dumps(result))
        trace = foreground_trace(size, args.seconds, args.fg_rate, args.seed)
        manifest['foreground_trace_sha256'] = hashlib.sha256(json.dumps(trace).encode()).hexdigest()
        cases = [('foreground_only', 1), ('background_only', 1)] + [('mixed', q) for q in (1, 2, 4, 8)]
        summaries = []
        interrupted = False
        for repeat in range(1, args.repetitions + 1):
            order = cases[:]
            random.Random(args.seed + repeat).shuffle(order)
            for mode, q in order:
                name = 'repeat%d_%s_q%d' % (repeat, mode, q)
                print('Running ' + name, flush=True)
                rows, summary = run_case(reader, size, mode, q, args.seconds, args.fg_rate,
                                         args.seed, args.foreground_limit, args.pending_limit,
                                         args.background_mib_s, args.target_ms)
                summary['case'] = name
                save_case(output / name, rows, summary)
                summaries.append(summary)
                if summary['errors'] or summary['interrupted']:
                    interrupted = summary['interrupted']
                    break
                time.sleep(.25)
            if interrupted or any(item['errors'] for item in summaries):
                break
        lines = ['# Foreground/background pilot', '',
                 'Threaded direct-read prototype; exploratory functional/interference results only.', '',
                 '| Case | FG successes | FG p50 ms | FG p99 ms* | BG MiB/s | Rejected | Errors | Peak BG jobs |',
                 '|---|---:|---:|---:|---:|---:|---:|---:|']
        for item in summaries:
            lines.append('| %s | %d | %s | %s | %.3f | %d | %d | %d |' % (
                item['case'], item['foreground_successful'], number_text(item['foreground_p50_ms']),
                number_text(item['foreground_p99_ms']), item['background_mib_s_including_drain'],
                item['foreground_rejected'], item['errors'], item['maximum_background_outstanding_jobs']))
        lines += ['', '*Short-run p99 is unstable. Rejections/errors are separate from successful-read percentiles.',
                  'BG rate is capped; a common rate ceiling or small cached fixture can hide queue-depth effects.',
                  'Each run drains submitted work; throughput includes drain time. Each case starts its scan at offset zero.',
                  'No final HDD-performance, adaptive-policy, or optimal-q conclusion is supported.']
        text = '\n'.join(lines) + '\n'
        (output / 'summary.md').write_text(text, encoding='utf-8')
        (output / 'all_summaries.json').write_text(json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
        print(text)
        manifest['status'] = ('interrupted' if interrupted else 'failed' if any(s['errors'] for s in summaries) else 'completed')
        return 130 if interrupted else 1 if manifest['status'] == 'failed' else 0
    except KeyboardInterrupt:
        manifest['status'] = 'interrupted'
        print('Interrupted; retain partial logs and do not treat this as a complete comparison.', file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        manifest.update(status='blocked', error=str(exc))
        print('BLOCKED: ' + str(exc), file=sys.stderr)
        return 77
    finally:
        if reader is not None:
            reader.close()
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
