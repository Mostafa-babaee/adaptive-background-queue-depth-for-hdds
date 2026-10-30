# Log format 3

One run directory contains run_meta.json, requests.csv and windows.csv. Raw source-linked validation reports are separate from performance runs.

## Requests

| Column | Meaning |
|---|---|
| req_id | Unique request ID within the run |
| class | FG or BG |
| offset / len | Requested offset and length, bytes |
| t_arrival | Intended FG trace time, or BG queue-generation time |
| t_admit | Time admitted into the pending queue; zero for rejection |
| t_submit | Time prepared for submission, immediately before the batch flush |
| t_complete | Time the application reaped the completion |
| t_verify | Time byte verification finished |
| status | OK, ERR, REJECTED or UNSUBMITTED |
| errno | Zero for OK; explicit error code otherwise |
| verified | 1 only after returned bytes passed the known-pattern check |
| bytes_read | Actual nonnegative bytes returned, including a short tail |
| q_at_submit | Configured background limit at submission |
| bg_out_at_submit / fg_out_at_submit | Application quota reservations before this request; firmware depth is not observed |

Times are CLOCK_MONOTONIC nanoseconds relative to run start. Admission, scheduling, verification and logging consume time; completion timestamps are application observations. Batch timestamps also include batch preparation. REJECTED and UNSUBMITTED rows have blank submission/completion fields. An aligned short BG tail may be verified; its actual bytes_read, not len, contributes to scan bytes. FG reads require a full 4 KiB block.

## Windows

Windows record configured q, maximum and time-weighted mean application BG count, pending queue lengths, successful FG samples/misses, cumulative verified BG bytes, rejection count and controller CPU time. Boundaries are advanced before depth changes/completion samples. Application depth includes prepared quota reservations before kernel submission and ends at completion observation; it is not firmware queue depth.

## Metadata and validation

Metadata records implementation, status, scheduled warm-up/duration, actual elapsed time, file sizes, configured limits, foreground expected/offered counts and final accounting. The experiment runner adds the trace SHA-256 and the read-only preparation outcome. A completed run may include drain time beyond the scheduled measurement interval. Analysis measures BG throughput from completions in the specified warm-up-excluded interval and latency for FG arrivals in that interval.

For a valid measurement, all scheduled FG arrivals inside the horizon must appear exactly once, including rejections. The metadata counters must match terminal rows; unexpected errors, interrupted/early stops, incomplete duration, unverified bytes and ambiguous byte counts are rejected. Legacy reference format 2 lacks admission/verification/actual-byte fields; its BG lengths can be used only when the sum exactly matches the runtime's actual scan-byte counter. The reference raw files remain unchanged.
