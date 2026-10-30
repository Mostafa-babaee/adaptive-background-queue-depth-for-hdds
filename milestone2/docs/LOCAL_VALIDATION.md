# Local validation — October 30, 2026

- Full revised Python suite: 36 tests passed, including the 16 controller tests, three metric/target tests, 13 raw-data/dataset validation tests and four generator/trace tests.
- Portable C submission helper: eight scenarios passed (full/partial submission, interruptions, no progress, failures, invalid return counts and empty batch).
- Revised dispatcher passed GCC -Wall -Wextra -Werror syntax checking using temporary Linux API declarations on Windows. This is not compilation against real liburing or a Linux execution test.
- Production Linux compile and 15 dispatcher integration tests: pending Babbage execution. The validation script will preserve their output and source hashes.
- Reference aggregate data: 27 rows, nine conditions with three repetitions; 162 summary values matched the per-run aggregate CSV. No original raw request logs were available for independent measurement validation.
- Original reference source/evidence copies remain byte-for-byte unchanged.
- No long experiments, global cache operations, or new HDD performance measurements were performed during packaging.


Subsequent Linux validation is now complete; see LINUX_VALIDATION.md for the matching source receipt and 59 passed checks. This document retains the earlier local-check history.
