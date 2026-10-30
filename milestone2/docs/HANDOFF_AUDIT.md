# Original Study A handoff audit

Checked October 30, 2026. The complete handoff closes the missing original-data gap. The original measurements and source were preserved without changes.

## Findings

- All 27 original runs include request logs, window logs and run metadata. The full terminal log and both workload traces are included.
- The nested archive matches its supplied SHA-256 checksum. All 26 available entries in the original source manifest match; the compiled binary is intentionally absent and must be rebuilt.
- Independently checked 48,746,023 request records, including IDs, timestamps, verification flags, errors, byte accounting, foreground schedules and queue limits. All 27 runs passed these checks.
- Recomputed 459 per-run metric values from the raw logs; they match the published per-run results. The earlier aggregate check also verified 162 means and standard deviations.
- Every foreground run follows the same 130-second trace with 6,576 arrivals. Reconstructed background concurrency reaches the configured limits of 1, 2, 4 and 8 without exceeding them.
- No read errors or rejected requests were recorded. At normal shutdown, the original dispatcher explicitly marked 294 queued background requests UNSUBMITTED across the study. These requests are fully accounted for and excluded from successful reads; no foreground requests were left unsubmitted. The revised implementation instead drains accepted pending work at normal shutdown.
- The largest difference between logged and independently reconstructed average window depth is approximately 0.000862 requests. The original window-observation convention has a small precision difference; the concurrency limits still hold.

## Configuration and provenance

All 27 runs used fixed policies and recorded target_ms as null. The server's frozen adaptive configuration matches the supplied checksum exactly. The different configuration in the earlier small ZIP is the pre-freeze version: the analysis wrote the frozen file after the experiments. It did not change their policy inputs.

The 0.5 ms target, 1000 ms window and 25 minimum samples remain provisional reference-platform settings. The handoff does not establish team approval of a final physical-HDD calibration.

These experiments used the AI-assisted reference dispatcher supplied by Ahmad and Sheryar on Babbage's shared PERC RAID storage. They were not measurements of Mostafa's earlier standalone dispatcher or of the revised integration. They do not establish isolated physical-HDD performance. No separate per-run stdout/stderr files were saved; the full driver terminal output is available.

## Retained evidence

The checked archive remains at the workspace root as M2_handoff_for_Mostafa.zip. Its SHA-256 is:

`51e4e0a79e521f7e1977849e1bae16c02bf3931616caa01c16c974a5f99523b2`

The nested studyA_bundle_2026-10-30.tar.gz SHA-256 is:

`29c3f1f5d12446e420713a8f131656949c5ec5df075dc01334716ba0851943af`

The smaller release retains audit receipts, checked handoff documents, original run metadata and window logs under evidence/handoff_validation. Large request CSVs remain in the original archive, which was streamed directly during the audit. audit_script_as_run.py is an archival record of the workspace-specific audit, rather than the normal portable analysis entry point. No raw logs were invented or rewritten.

## Remaining milestone work

The revised integration has now passed its separate Babbage Linux validation, with all 18 source hashes matching the receipt; see LINUX_VALIDATION.md. Historical reference measurements remain separate. Finalize the Milestone 2 report, slides and recordings, publish the source and labelled evidence, and record the new Git commit ID.
