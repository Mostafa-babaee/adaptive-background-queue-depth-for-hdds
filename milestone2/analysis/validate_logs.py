"""Validation gates for measured Study A logs; aggregate CSVs are not raw evidence."""
from pathlib import Path
import hashlib
import math
import pandas as pd

QS = (1, 2, 4, 8)


def validate_run(meta, req, win, trace=None):
    problems = []

    def need(ok, message):
        if not bool(ok):
            problems.append(message)

    required_meta = {'run_id', 'mode', 'q', 'repetition', 'warmup_ns', 'duration_ns',
                     'accounting_ok', 'direct_io', 'counts', 'fg_quota', 'fg_queue_cap',
                     'bg_queue_cap', 'chunk_bytes', 'stopped_by_signal'}
    missing = required_meta - meta.keys()
    if missing:
        return ['missing metadata: ' + ', '.join(sorted(missing))]
    columns = {'req_id', 'class', 'offset', 'len', 't_arrival', 't_submit', 't_complete',
               'status', 'errno', 'verified', 'q_at_submit', 'bg_out_at_submit', 'fg_out_at_submit'}
    if not columns <= set(req.columns):
        return ['missing request columns']
    need(meta['direct_io'] is True, 'direct I/O not explicitly true')
    need(meta['accounting_ok'] is True, 'internal accounting failed')
    need(meta['stopped_by_signal'] is False, 'run interrupted by a signal')
    need(meta.get('run_status', 'completed') == 'completed', 'run did not complete normally')
    need(meta['mode'] in ('fg', 'bg', 'mixed'), 'unknown run mode')
    need(meta['q'] in QS, 'q outside allowed set')
    duration = meta['duration_ns']
    end = meta['warmup_ns'] + duration
    need(duration > 0, 'nonpositive measurement duration')
    if not {'t_start', 't_end', 'q_config', 'bg_out_max', 'bg_out_mean'} <= set(win.columns):
        return ['missing window columns']
    need(not win.empty and {'t_start', 't_end', 'q_config', 'bg_out_max', 'bg_out_mean'} <= set(win.columns), 'missing windows')
    if not win.empty:
        need(win['t_end'].max() >= end, 'run stopped before scheduled end')
        need((win['t_end'] > win['t_start']).all(), 'nonpositive window length')
        need((win['q_config'] == meta['q']).all(), 'configured q changed in a fixed run')
        need(((win['bg_out_max'] >= 0) & (win['bg_out_max'] <= meta['q'])).all(), 'window depth exceeds cap')
        need(((win['bg_out_mean'] >= 0) & (win['bg_out_mean'] <= meta['q'] + 1e-4)).all(), 'window mean depth invalid')
    need(req['req_id'].notna().all() and not req['req_id'].duplicated().any(), 'missing/duplicate request IDs')
    need(req['status'].isin(['OK', 'ERR', 'REJECTED', 'UNSUBMITTED']).all(), 'unknown request status')
    need(req['class'].isin(['FG', 'BG']).all(), 'unknown request class')
    need(((req['offset'] >= 0) & (req['offset'] % 4096 == 0)).all(), 'invalid offset')
    need((req.loc[req['class'] == 'FG', 'len'] == 4096).all(), 'foreground size differs from 4 KiB')
    submitted = req[req['status'].isin(['OK', 'ERR'])]
    ok = req[req['status'] == 'OK']
    need((ok['verified'] == 1).all(), 'successful reads are unverified')
    need((ok['errno'] == 0).all(), 'successful reads have errors')
    need(not (req['status'] == 'ERR').any(), 'unexpected read/verification errors')
    need(submitted[['t_submit', 't_complete']].notna().all().all(), 'submitted reads lack timestamps')
    need(((submitted['t_arrival'] <= submitted['t_submit']) &
          (submitted['t_submit'] <= submitted['t_complete'])).all(), 'request timestamps out of order')
    if not win.empty:
        need((submitted['t_complete'] <= win['t_end'].max()).all(), 'completion after last recorded window')
    need((submitted['q_at_submit'] == meta['q']).all(), 'request q differs from run configuration')
    bg_submitted = submitted[submitted['class'] == 'BG']
    fg_submitted = submitted[submitted['class'] == 'FG']
    need(((bg_submitted['bg_out_at_submit'] >= 0) &
          (bg_submitted['bg_out_at_submit'] < meta['q'])).all(), 'background cap exceeded')
    need(((fg_submitted['fg_out_at_submit'] >= 0) &
          (fg_submitted['fg_out_at_submit'] < meta['fg_quota'])).all(), 'foreground quota exceeded')
    pending = req[req['status'].isin(['UNSUBMITTED', 'REJECTED'])]
    need(pending[['t_submit', 't_complete']].isna().all().all(), 'unsubmitted rows have I/O timestamps')
    need(not ((req['class'] == 'BG') & (req['status'] == 'REJECTED')).any(), 'unexpected BG rejection')
    counts = meta['counts']
    observed = {'accepted': int(req['status'].ne('REJECTED').sum()),
                'rejected': int(req['status'].eq('REJECTED').sum()),
                'submitted': len(submitted), 'completed_ok': len(ok),
                'completed_err': int(req['status'].eq('ERR').sum()),
                'unsubmitted': int(req['status'].eq('UNSUBMITTED').sum()),
                'fg_ok': int((ok['class'] == 'FG').sum()), 'bg_ok': int((ok['class'] == 'BG').sum())}
    for name, value in observed.items():
        need(counts.get(name) == value, 'count mismatch: ' + name)
    need(counts.get('verify_fail') == 0, 'verification failures recorded')
    if 'bytes_read' in req:
        need(((ok['bytes_read'] > 0) & (ok['bytes_read'] <= ok['len']) &
              (ok['bytes_read'] % 4096 == 0)).all(), 'invalid successful byte count')
        need((ok.loc[ok['class'] == 'FG', 'bytes_read'] == 4096).all(), 'short foreground read marked successful')
        bg_bytes = int(ok.loc[ok['class'] == 'BG', 'bytes_read'].sum())
        need({'t_admit', 't_verify'} <= set(req.columns), 'missing lifecycle timestamps')
        if {'t_admit', 't_verify'} <= set(req.columns):
            need(((submitted['t_arrival'] <= submitted['t_admit']) &
                  (submitted['t_admit'] <= submitted['t_submit']) &
                  (submitted['t_complete'] <= submitted['t_verify'])).all(), 'admission/verification timestamps invalid')
    else:
        # Legacy v2 has no actual-byte column: accept only if all requested BG
        # bytes agree with the runtime's independently accumulated actual total.
        bg_bytes = int(ok.loc[ok['class'] == 'BG', 'len'].sum())
    need(counts.get('scan_bytes_total') == bg_bytes, 'scan-byte mismatch or ambiguous legacy short tail')
    fg = req[req['class'] == 'FG']
    need(not (fg['status'] == 'UNSUBMITTED').any(), 'accepted foreground requests were not drained')
    if meta['mode'] == 'bg':
        need(fg.empty, 'foreground requests in scanner-only run')
    else:
        if trace is None:
            problems.append('original foreground trace is missing')
        else:
            need(list(trace.columns) == ['t_ns', 'offset'], 'unexpected trace schema')
            if list(trace.columns) == ['t_ns', 'offset']:
                expected = trace[(trace['t_ns'] >= 0) & (trace['t_ns'] < end)]
                a = sorted(zip(expected['t_ns'].astype(int), expected['offset'].astype(int)))
                b = sorted(zip(fg['t_arrival'].astype(int), fg['offset'].astype(int)))
                need(a == b, 'offered requests differ from scheduled trace')
                if 'expected_foreground_requests' in meta:
                    need(meta['expected_foreground_requests'] == len(a), 'expected trace count mismatch')
                if meta.get('log_format', 2) >= 3:
                    need(meta.get('arrival_schedule_complete') is True, 'arrival schedule incomplete')
    if meta['mode'] == 'fg':
        need(not (req['class'] == 'BG').any(), 'background requests in foreground-only run')
    return sorted(set(problems))


def validate_dataset(metas, reps=3):
    expected = {('fg', 0)} | {(mode, q) for mode in ('bg', 'mixed') for q in QS}
    groups = {}
    errors = []
    for m in metas:
        key = (m['mode'], 0 if m['mode'] == 'fg' else m['q'])
        groups.setdefault(key, []).append(m['repetition'])
    if set(groups) != expected:
        errors.append('dataset must contain all nine Study A conditions')
    for key, values in groups.items():
        if sorted(values) != list(range(1, reps + 1)):
            errors.append(f'{key}: expected unique repetitions 1..{reps}')
    common = ['fg_path', 'bg_path', 'trace', 'fg_quota', 'fg_queue_cap', 'bg_queue_cap',
              'chunk_bytes', 'bg_start_offset', 'cpu', 'window_ms', 'warmup_ns', 'duration_ns', 'direct_io', 'device', 'target_ms']
    if metas:
        for key in common:
            if any(m.get(key) != metas[0].get(key) for m in metas):
                errors.append('inconsistent common setting: ' + key)
        if len({m['run_id'] for m in metas}) != len(metas):
            errors.append('duplicate run IDs')
    return errors


def read_trace(meta, trace_dir=None):
    name = meta.get('trace')
    if not name or meta['mode'] == 'bg':
        return None
    candidates = ([Path(trace_dir) / Path(name).name] if trace_dir else []) + [Path(name)]
    for path in candidates:
        if path.is_file():
            if meta.get('trace_sha256') and hashlib.sha256(path.read_bytes()).hexdigest() != meta['trace_sha256']:
                raise ValueError('trace checksum differs from run metadata')
            return pd.read_csv(path)
    return None
