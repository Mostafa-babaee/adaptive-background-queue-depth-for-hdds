# Dispatcher design - Milestone 1

Status: architecture reviewed on October 19, 2026. See `DISPATCHER_DESIGN_REVIEW.md` for the completed written review and proposed implementation decisions. The full C/io_uring dispatcher is still Milestone 2 work; team interface agreement remains pending.

For a worked example and the decisions still to agree with the team, see `DESIGN_REVIEW.md`.

## Purpose

Serve 4 KiB random foreground reads alongside a fixed-chunk sequential background scan on the same HDD. The program controls how many reads it submits; it does not control firmware scheduling or know physical head position.

## Components

```text
Foreground arrival schedule -> foreground pending queue --+
                                                         +-> dispatcher -> io_uring -> completions
Sequential scan generator  -> background pending queue --+                          |
                              ^                                                    |
                              +---- counters, verification, logs <-----------------+
```

- Workload generator: Sheryar's component. Retains intended foreground arrival times even if the dispatcher falls behind.
- Dispatcher and correctness: Mostafa's component. Maintains separate pending queues and in-flight requests, and records completions.
- Depth policy: Muhammad's component. Returns a background cap q in {1, 2, 4, 8}; the dispatcher enforces it. Muhammad defines the final common log format with team input.
- Experiment scripts and plots: use the same dispatcher and logs for all policies.

## Request record

| Field | Meaning |
|---|---|
| request_id | Unique integer for the run; copied into the SQE's user_data |
| workload | foreground or background |
| file/descriptor | Open test-file identity |
| offset_bytes, length_bytes | Aligned file range |
| intended_arrival_ns | Original workload arrival using the agreed monotonic time basis |
| admitted_ns | Time accepted into the pending queue |
| submitted_ns | Time immediately before issuing the I/O |
| completed_ns | Time the application observes completion |
| buffer | Aligned memory kept alive until completion |
| state | pending, prepared, in_flight, verifying, success, error, or rejected |
| result_bytes, error_code | Actual result; short reads are explicit |

Milestone 1's smoke-test timestamps are local request timestamps, not a replayed arrival trace. Agree the final field names, units, rejection behavior, and measurement denominator with Muhammad before implementing the dispatcher.

## Main loop

1. Process available completions: match IDs, timestamp observations, verify results, log outcomes, and decrement the correct outstanding counter exactly once.
2. Enqueue newly due foreground requests with original arrival times. If a finite pending queue is full, record the admission failure instead of dropping it silently.
3. Submit foreground requests when their fixed quota permits. Use the same quota and admission rules for every policy.
4. Submit background requests only while scanning remains active and background_outstanding < q.
5. Collect the measurements needed by the depth policy. The required controller holds q when samples are sparse, reduces it after excessive misses, and raises it only after several comfortable windows.
6. Wait for arrivals/completions without busy-spinning when there is no useful work.

The completed review proposes foreground quota 1, foreground pending capacity 64, and background pending capacity 8 as configurable starting settings, not measured optimal values. Team agreement and controller-window calibration remain pending.

## Invariants and shutdown

- accepted = pending + prepared + in_flight + verifying + successful + completed_with_error at stable accounting checkpoints; rejected requests are tracked separately.
- A buffer cannot be reused or released while its read is in flight.
- After completion, keep the returned buffer intact until data verification has finished. If verification is queued separately, account for requests in a distinct verifying state.
- When q decreases, submitted reads continue. Only new background submissions stop until the outstanding count is below q.
- Each accepted request reaches one terminal outcome and produces one completion/error record.
- Shutdown stops new workload arrivals, drains accepted work (or explicitly records unsubmitted queued requests as shutdown errors), and keeps buffers/descriptors alive until outstanding reads complete.
- EOF, short reads, errors, and growth of pending queues are reported.

## Measurements

Report arrival-to-completion latency and preserve submission-to-completion timing separately. Submission-to-completion contains queueing and software delay; it is not pure seek time. Background throughput counts completed, verified useful bytes, not merely submitted bytes. Log both q and the actual outstanding count.

The later evaluation includes p50/p99 latency, target misses, scan progress, CPU cost, and errors. The smoke test provides functional evidence only. O_DIRECT reduces page-cache effects when supported; it does not remove the HDD's own cache.

## Later tests

Milestone 2 adds full pending-queue, in-flight shutdown, quota enforcement, and exactly-once accounting tests. Milestone 3 tests limit reduction under load, the controller, and workload comparisons. Optional RL follows the required work and is not a Milestone 1 deliverable.
