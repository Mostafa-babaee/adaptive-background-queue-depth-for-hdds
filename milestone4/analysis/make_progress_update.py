"""Generate a provenance-aware progress note without overwriting existing evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    checked = False
    if args.validation:
        receipt = json.loads(args.validation.read_text())
        checked = receipt.get('status') == 'passed' and receipt.get('platform') == 'Linux'
        for name, expected in receipt.get('source_sha256', {}).items():
            source = ROOT / name
            checked = checked and source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == expected
        checked = checked and bool(receipt.get('source_sha256'))
    reference = ROOT / 'evidence/reference/results/studyA'
    runs = pd.read_csv(reference / 'runs.csv')
    summary = pd.read_csv(reference / 'summary.csv')
    q1 = summary[(summary['mode'] == 'mixed') & (summary['q'] == 1)].iloc[0]
    q8 = summary[(summary['mode'] == 'mixed') & (summary['q'] == 8)].iloc[0]
    lines = [
        '# Milestone 2 progress update', '',
        'Team: Mostafa Babaei, Muhammad Ahmad Tariq, Sheryar Karim.', '',
        'We adopted and revised the integrated AI-assisted reference dispatcher supplied by Ahmad and Sheryar.',
        'Revised Linux validation: ' + ('passed for the current source snapshot.' if checked else 'pending a matching Linux validation receipt.'), '',
        f'The supplied reference aggregate data contains {len(runs)} runs, three repetitions for each of nine conditions.',
        f"Reported combined p99: {q1['fg_p99_ms_mean']:.2f} ms at q=1 and {q8['fg_p99_ms_mean']:.2f} ms at q=8.",
        f"Reported combined scan throughput: {q1['scan_mib_s_mean']:.1f} and {q8['scan_mib_s_mean']:.1f} MiB/s respectively.",
        'These measurements belong to the original reference build on Babbage shared RAID, not to this revised build.',
        'They do not establish isolated physical-HDD performance. Original raw-log revalidation remains pending the handoff archive.', '',
        'The 0.5 ms target, 1000 ms window and 25 minimum samples are provisional for the reference platform.',
        'The revised code preserves results, handles partial submissions, records actual bytes and rejects invalid datasets before freezing targets.', '',
        'Remaining submission work: review the Linux validation receipt and original raw handoff, update GitHub, and record each member’s presentation/demo segment.'
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
    print(args.out)


if __name__ == '__main__':
    main()
