"""Read the original nested archives without unpacking large request CSV files."""
from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib
import io
import json
import math
import sys
import tarfile
import time
import zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'M2_handoff_for_Mostafa.zip'
HANDOFF = OUT / 'handoff'
PREFIX = 'M2_handoff_for_Mostafa/'
EXPECTED_BUNDLE = '29c3f1f5d12446e420713a8f131656949c5ec5df075dc01334716ba0851943af'
TRACE = pd.read_csv(HANDOFF / 'traces/constant_50rps_130s_seed42.csv')
PUBLISHED = pd.read_csv(ROOT / 'tmp/team_m2_review/M2_code_for_server/results/studyA/runs.csv').set_index('run_id')
started = time.monotonic()


class HashReader(io.RawIOBase):
    def __init__(self, stream):
        self.stream = stream
        self.sha = hashlib.sha256()
        self.count = 0

    def readable(self):
        return True

    def read(self, size=-1):
        data = self.stream.read(size)
        self.sha.update(data)
        self.count += len(data)
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def near(a, b):
    return (pd.isna(a) and pd.isna(b)) or math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def audit_requests(stream, meta, windows):
    errors = []

    def need(condition, message):
        if not bool(condition) and message not in errors:
            errors.append(message)

    stats = Counter()
    statuses = Counter()
    classes = Counter()
    fg_frames, bg_submits, bg_completes = [], [], []
    seen = np.zeros(1024, dtype=bool)
    maximum_id = -1
    last_complete = 0
    warm = meta['warmup_ns']
    duration = meta['duration_ns']
    end = warm + duration
    hashed = HashReader(stream)
    dtype = {'req_id': 'int64', 'offset': 'int64', 'len': 'int64', 't_arrival': 'int64',
             'verified': 'int16', 'errno': 'int32', 'q_at_submit': 'int16',
             'bg_out_at_submit': 'int32', 'fg_out_at_submit': 'int32',
             'class': 'category', 'status': 'category'}
    for data in pd.read_csv(hashed, chunksize=100000, dtype=dtype):
        ids = data['req_id'].to_numpy()
        need((ids >= 0).all(), 'negative request ID')
        high = int(ids.max())
        if high >= 100_000_000:
            raise ValueError('Unexpectedly large ID; refusing excessive allocation')
        if high >= len(seen):
            larger = np.zeros(max(high + 1, len(seen) * 2), dtype=bool)
            larger[:len(seen)] = seen
            seen = larger
        need(len(np.unique(ids)) == len(ids) and not seen[ids].any(), 'duplicate request IDs')
        seen[ids] = True
        maximum_id = max(high, maximum_id)
        stats['rows'] += len(data)
        statuses.update(data['status'].value_counts().to_dict())
        classes.update(data['class'].value_counts().to_dict())
        need(data['status'].isin(['OK', 'ERR', 'REJECTED', 'UNSUBMITTED']).all(), 'unknown terminal status')
        need(data['class'].isin(['FG', 'BG']).all(), 'unknown workload class')
        need(((data['offset'] >= 0) & (data['offset'] % 4096 == 0)).all(), 'invalid request offset')
        need((data.loc[data['class'] == 'FG', 'len'] == 4096).all(), 'invalid FG size')
        need((data.loc[data['class'] == 'BG', 'len'] == meta['chunk_bytes']).all(), 'invalid BG chunk size')
        ok = data[data['status'] == 'OK']
        submitted = data[data['status'].isin(['OK', 'ERR'])]
        need((ok['verified'] == 1).all(), 'unverified successful read')
        need((ok['errno'] == 0).all(), 'successful read has errno')
        need(submitted[['t_submit', 't_complete']].notna().all().all(), 'missing submitted timestamp')
        need(((submitted['t_arrival'] <= submitted['t_submit']) &
              (submitted['t_submit'] <= submitted['t_complete'])).all(), 'out-of-order lifecycle timestamps')
        need((submitted['q_at_submit'] == meta['q']).all(), 'fixed q changed in request log')
        pending = data[data['status'].isin(['REJECTED', 'UNSUBMITTED'])]
        need(pending[['t_submit', 't_complete']].isna().all().all(), 'unsubmitted row has completion')
        fg = data[data['class'] == 'FG']
        if len(fg):
            fg_frames.append(fg.copy())
        stats['unverified'] += int((ok['verified'] != 1).sum())
        stats['fg_ok'] += int(((data['class'] == 'FG') & (data['status'] == 'OK')).sum())
        bg = submitted[submitted['class'] == 'BG']
        need(((bg['bg_out_at_submit'] >= 0) & (bg['bg_out_at_submit'] < meta['q'])).all(), 'BG quota exceeded in submission record')
        fs = submitted[submitted['class'] == 'FG']
        need(((fs['fg_out_at_submit'] >= 0) & (fs['fg_out_at_submit'] < meta['fg_quota'])).all(), 'FG quota exceeded in submission record')
        if len(bg):
            bg_submits.append(bg['t_submit'].to_numpy(dtype=np.int64))
            bg_completes.append(bg['t_complete'].to_numpy(dtype=np.int64))
        bg_ok = ok[ok['class'] == 'BG']
        # Original config and whole-file verification record specify a 2 GiB BG
        # file. All logged requests must fit fully inside it for len to be the
        # unambiguous actual count in the legacy v2 schema.
        need((bg_ok['offset'] + bg_ok['len'] <= 2048 * 1048576).all(), 'legacy short BG tail needs actual-byte evidence')
        stats['bg_ok'] += len(bg_ok)
        stats['all_bg_bytes'] += int(bg_ok['len'].sum())
        measured_bg = bg_ok[(bg_ok['t_complete'] >= warm) & (bg_ok['t_complete'] < end)]
        stats['measured_bg_bytes'] += int(measured_bg['len'].sum())
        if len(submitted):
            last_complete = max(last_complete, int(submitted['t_complete'].max()))
    need(stats['rows'] == maximum_id + 1, 'allocated request IDs have gaps')
    counts = meta['counts']
    actual = {'accepted': stats['rows'] - statuses['REJECTED'], 'rejected': statuses['REJECTED'],
              'submitted': statuses['OK'] + statuses['ERR'], 'completed_ok': statuses['OK'],
              'completed_err': statuses['ERR'], 'unsubmitted': statuses['UNSUBMITTED'],
              'fg_ok': stats['fg_ok'], 'bg_ok': stats['bg_ok'], 'scan_bytes_total': stats['all_bg_bytes']}
    for name, value in actual.items():
        need(counts.get(name) == value, 'metadata/CSV mismatch: ' + name)
    need(counts['accepted'] == counts['submitted'] + counts['unsubmitted'], 'accepted accounting mismatch')
    need(counts['submitted'] == counts['completed_ok'] + counts['completed_err'], 'submitted accounting mismatch')
    need(counts['verify_fail'] == 0 and stats['unverified'] == 0 and statuses['ERR'] == 0, 'read or verification errors')
    need(meta['accounting_ok'] is True, 'metadata accounting failed')
    need(meta['direct_io'] is True, 'direct I/O not explicitly true')
    need(meta.get('stopped_by_signal') is False, 'interrupted run')
    need(meta.get('policy') == 'fixed', 'non-fixed policy in Study A')
    need(meta.get('target_ms') is None, 'unexpected target used during fixed baselines')
    need(windows['t_end'].max() >= end, 'incomplete duration')
    need(last_complete <= windows['t_end'].max(), 'completion beyond last window')
    need((windows['q_config'] == meta['q']).all(), 'window q differs from fixed cap')
    need((windows['bg_out_max'] <= meta['q']).all(), 'window peak exceeds q')
    need(((windows['bg_out_mean'] >= 0) & (windows['bg_out_mean'] <= meta['q'] + 1e-4)).all(), 'invalid window mean')
    fg = pd.concat(fg_frames, ignore_index=True) if fg_frames else pd.DataFrame()
    if meta['mode'] != 'bg':
        expected = TRACE[TRACE['t_ns'] < end]
        need(sorted(zip(expected['t_ns'], expected['offset'])) == sorted(zip(fg['t_arrival'], fg['offset'])), 'foreground trace replay mismatch')
        need(not (fg['status'] == 'UNSUBMITTED').any(), 'FG requests left unsubmitted at normal stop')
    else:
        need(fg.empty, 'FG traffic in scanner-only run')
    if meta['mode'] == 'fg':
        need(classes['BG'] == 0, 'BG traffic in foreground-only run')
    reconstructed_max = 0
    reconstructed_mean = 0.0
    if bg_submits:
        subs = np.concatenate(bg_submits)
        comps = np.concatenate(bg_completes)
        times = np.concatenate([subs, comps])
        deltas = np.concatenate([np.ones(len(subs), dtype=np.int8), -np.ones(len(comps), dtype=np.int8)])
        order = np.lexsort((deltas, times))
        depth = np.cumsum(deltas[order])
        reconstructed_max = int(depth.max())
        need(int(depth.min()) >= 0 and int(depth[-1]) == 0, 'reconstructed BG accounting invalid')
        need(reconstructed_max <= meta['q'], 'reconstructed BG depth exceeds q')
        reconstructed_mean = float(np.maximum(0, np.minimum(comps, end) - np.maximum(subs, warm)).sum(dtype=np.int64) / duration)
        del times, deltas, order, depth, subs, comps
    w = windows[(windows['t_start'] >= warm) & (windows['t_end'] <= end)]
    if not fg.empty:
        fgm = fg[(fg['t_arrival'] >= warm) & (fg['t_arrival'] < end)]
        success = fgm[fgm['status'] == 'OK']
        lat = (success['t_complete'] - success['t_arrival']) / 1e6
        wait = (success['t_submit'] - success['t_arrival']) / 1e6
        service = (success['t_complete'] - success['t_submit']) / 1e6
    else:
        fgm = success = pd.DataFrame()
        lat = wait = service = pd.Series(dtype=float)
    metrics = {'fg_offered': len(fgm), 'fg_done': len(success),
               'fg_p50_ms': lat.quantile(.5), 'fg_p95_ms': lat.quantile(.95), 'fg_p99_ms': lat.quantile(.99),
               'fg_mean_ms': lat.mean(), 'wait_p99_ms': wait.quantile(.99), 'service_p99_ms': service.quantile(.99),
               'miss_frac': float((lat > .5).mean()) if len(lat) else math.nan,
               'rejected': int((fgm['status'] == 'REJECTED').sum()) if len(fgm) else 0,
               'errors': statuses['ERR'], 'unverified': stats['unverified'],
               'scan_mib_s': stats['measured_bg_bytes'] / 1048576 / (duration / 1e9),
               'scan_bytes': stats['measured_bg_bytes'], 'bg_out_mean': w['bg_out_mean'].mean(),
               'bg_out_max': int(w['bg_out_max'].max()) if len(w) else 0,
               'ctrl_cpu_us': w['ctrl_cpu_ns'].mean() / 1000}
    published = PUBLISHED.loc[meta['run_id']]
    metric_mismatches = {key: {'raw_recomputed': value, 'published': published[key]}
                         for key, value in metrics.items() if not near(value, published[key])}
    need(not metric_mismatches, 'published metric mismatch')
    return {'run_id': meta['run_id'], 'mode': meta['mode'], 'q': meta['q'], 'repetition': meta['repetition'],
            'rows': stats['rows'], 'request_csv_sha256': hashed.sha.hexdigest(),
            'statuses': dict(statuses), 'errors': errors, 'metrics': metrics,
            'metric_mismatches': metric_mismatches, 'reconstructed_bg_max': reconstructed_max,
            'reconstructed_bg_mean_measured': reconstructed_mean,
            'reported_window_bg_mean': metrics['bg_out_mean']}


def main():
    contexts, reports, inventory = {}, [], []
    small = OUT / 'bundle_small'
    small.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        with z.open(PREFIX + 'studyA_bundle_2026-10-30.tar.gz') as compressed:
            hashed = HashReader(compressed)
            with tarfile.open(fileobj=hashed, mode='r|gz') as tar:
                for member in tar:
                    rel = PurePosixPath(member.name)
                    if rel.is_absolute() or '..' in rel.parts or member.issym() or member.islnk():
                        raise ValueError('Unsafe archive member: ' + member.name)
                    inventory.append({'name': member.name, 'size': member.size})
                    if not member.isfile():
                        continue
                    stream = tar.extractfile(member)
                    if len(rel.parts) == 4 and rel.parts[:2] == ('logs', 'studyA'):
                        run_id, filename = rel.parts[2:]
                        context = contexts.setdefault(run_id, {})
                        if filename == 'run_meta.json':
                            data = stream.read(); context['meta'] = json.loads(data)
                        elif filename == 'windows.csv':
                            data = stream.read(); context['windows'] = pd.read_csv(io.BytesIO(data))
                        elif filename == 'requests.csv':
                            if 'meta' not in context or 'windows' not in context:
                                raise ValueError('Metadata/window order requires an indexing pass')
                            report = audit_requests(stream, context['meta'], context['windows'])
                            reports.append(report)
                            (OUT / 'runs').mkdir(exist_ok=True)
                            (OUT / 'runs' / (run_id + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
                            print(f"{len(reports)}/27 {run_id}: rows={report['rows']:,}; issues={report['errors']}", flush=True)
                            continue
                        else:
                            data = stream.read()
                    elif member.size < 5_000_000 and '__pycache__' not in rel.parts:
                        data = stream.read()
                    else:
                        continue
                    target = small.joinpath(*rel.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            # Consume any remaining compressed bytes so the hash and ZIP CRC
            # cover the entire nested archive, not only tar's logical EOF.
            while hashed.read(4 * 1024 * 1024):
                pass
            digest = hashed.sha.hexdigest()
    assert digest == EXPECTED_BUNDLE, (digest, EXPECTED_BUNDLE)
    assert len(reports) == 27 and len(contexts) == 27
    assert {r['run_id'] for r in reports} == set(PUBLISHED.index)
    groups = Counter((r['mode'], r['q'] if r['mode'] != 'fg' else 0) for r in reports)
    assert len(groups) == 9 and all(n == 3 for n in groups.values())
    common_keys = ['host', 'kernel', 'device', 'fg_path', 'bg_path', 'trace', 'fg_quota',
                   'fg_queue_cap', 'bg_queue_cap', 'chunk_bytes', 'bg_start_offset', 'cpu',
                   'window_ms', 'warmup_ns', 'duration_ns', 'direct_io', 'target_ms']
    metas = [c['meta'] for c in contexts.values()]
    common_differences = {k: sorted({str(m.get(k)) for m in metas}) for k in common_keys
                          if len({str(m.get(k)) for m in metas}) != 1}
    summary = {'archive': ARCHIVE.name, 'nested_bundle_sha256': digest, 'bundle_checksum_match': True,
               'run_count': len(reports), 'request_rows_checked': sum(r['rows'] for r in reports),
               'runs_without_issues': sum(not r['errors'] for r in reports),
               'published_metric_mismatches': {r['run_id']: r['metric_mismatches'] for r in reports if r['metric_mismatches']},
               'common_setting_differences': common_differences,
               'trace_rows': len(TRACE), 'platform': 'Babbage shared RAID; preliminary',
               'source_implementation': 'original AI-assisted reference dispatcher',
               'elapsed_seconds': time.monotonic() - started, 'reports': reports}
    (OUT / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    (OUT / 'audit_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('BUNDLE SHA256 MATCH:', digest, flush=True)
    print('FINAL:', len(reports), 'runs;', summary['request_rows_checked'], 'rows;', summary['runs_without_issues'], 'without issues', flush=True)
    print('Common-setting differences:', common_differences, flush=True)


if __name__ == '__main__':
    main()
