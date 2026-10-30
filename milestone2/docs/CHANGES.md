# Integration changes

Base: AI-assisted reference package supplied by Ahmad and Sheryar on October 30, 2026. Original source/results are retained under evidence/reference and were not re-labelled as measurements from the revised program.

- Adopted the two-file integrated dispatcher and its workload/log interfaces.
- Fixed partial submission bookkeeping using a tested batch-flush helper; fatal/no-progress submission leaves the run incomplete instead of waiting on unsent reads.
- Added actual byte counts, admission/verification timestamps, implementation/run status, source-linked validation receipts and complete foreground-schedule accounting.
- Normal end drains accepted queued work. Signals and explicit early stops record unsubmitted work and return 130. Unexpected read/verification failures return nonzero even when bookkeeping balances.
- Added bounded numeric parsing, the discrete q set, regular-file/symlink checks, strict trace parsing and output protection.
- Fixed window-depth integration at nominal boundaries and checked log write/flush errors.
- Replaced the automatic long-run workflow with a fail-fast validation script. Future study runs use unique paths and read-only documented preparation; no global cache flushing or deletion of old results.
- Added raw-log/dataset validation before summaries or target freezing, including the original foreground trace, duration, direct-I/O flag, repetitions, counters and actual bytes.
- Restored the supplied provisional target in both adaptive configs; no-damping differs only in its intended up_windows setting. Original stale/frozen-history evidence remains separate.
- Added focused tests for batch submissions, validation gates, actual short-tail bytes, invalid arguments, result preservation, symlinks, malformed traces and normal draining.

The baseline numbers in the reference CSVs and PNGs were not changed. The complete original handoff has now passed request-level auditing; see HANDOFF_AUDIT.md. This revision has not acquired any new hardware-performance measurements merely by changing the software.
