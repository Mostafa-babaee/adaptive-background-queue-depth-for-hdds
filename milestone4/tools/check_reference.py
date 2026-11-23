"""Check supplied aggregate arithmetic; this does not validate missing raw logs."""
import csv
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
reference = ROOT / 'evidence/reference/results/studyA'
with (reference / 'runs.csv').open(newline='') as f:
    runs = list(csv.DictReader(f))
with (reference / 'summary.csv').open(newline='') as f:
    summary = list(csv.DictReader(f))
assert len(runs) == 27 and len(summary) == 9
assert len({r['run_id'] for r in runs}) == 27
count = 0
for row in summary:
    group = [r for r in runs if r['mode'] == row['mode'] and r['q'] == row['q']]
    assert sorted(int(r['rep']) for r in group) == [1, 2, 3]
    assert int(row['reps']) == 3
    for field in ['fg_p50_ms', 'fg_p99_ms', 'wait_p99_ms', 'service_p99_ms', 'miss_frac',
                  'scan_mib_s', 'bg_out_mean', 'rejected', 'errors']:
        values = [float(r[field]) for r in group if r[field] and math.isfinite(float(r[field]))]
        for suffix in ['mean', 'sd']:
            actual = float(row[field + '_' + suffix]) if row[field + '_' + suffix] else math.nan
            expected = (statistics.mean(values) if suffix == 'mean' else statistics.stdev(values)) if len(values) >= 2 else math.nan
            assert (math.isnan(actual) and math.isnan(expected)) or math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10)
            count += 1
target = json.loads((reference / 'target.json').read_text())
q1 = next(row for row in summary if row['mode'] == 'mixed' and row['q'] == '1')
assert target['target_ms'] == math.ceil(1.25 * float(q1['fg_p99_ms_mean']) * 2) / 2
receipt = dict(aggregate_arithmetic='consistent', runs=27, groups=9, checked_values=count,
               raw_request_measurements_verified=False, platform='Babbage shared RAID',
               implementation='original supplied reference snapshot', provisional_target=target)
print(json.dumps(receipt, indent=2))
