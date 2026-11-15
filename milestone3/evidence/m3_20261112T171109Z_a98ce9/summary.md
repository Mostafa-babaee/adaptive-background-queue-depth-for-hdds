# Milestone 3 results: Study B and Study C

Logs: `logs/m3_20261112T171109Z_a98ce9`. Runs: 56. Warm-up dropped. Mean ± sd over repetitions. Latency target 0.5 ms, window 1000 ms, a miss = FG read slower than the target.

**Integrity: 56 of 56 runs clean** (accounting OK, 0 errors, every byte verified, O_DIRECT, offered requests equal to the trace, no BG read sent while bg_out ≥ q).

## Study B

### alternating trace

| Policy | reps | FG p50 ms | FG p99 ms | miss % | scan MiB/s | scan GiB | mean q | q changes | reversals/min | rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 3 | 0.14 | 0.20 ± 0.00 | 0.0 ± 0.0 | 3285 ± 21 | 385 | 1.00 | 0.0 | 0.00 | 0 |
| fixed q=2 | 3 | 0.19 | 0.28 ± 0.02 | 0.0 ± 0.0 | 4814 ± 66 | 564 | 2.00 | 0.0 | 0.00 | 0 |
| fixed q=4 | 3 | 0.25 | 0.43 ± 0.01 | 0.4 ± 0.1 | 4275 ± 19 | 501 | 4.00 | 0.0 | 0.00 | 0 |
| fixed q=8 | 3 | 0.31 | 0.56 ± 0.02 | 3.7 ± 1.2 | 5965 ± 29 | 699 | 8.00 | 0.0 | 0.00 | 0 |
| adaptive | 3 | 0.29 | 0.54 ± 0.00 | 2.3 ± 0.1 | 5024 ± 190 | 589 | 5.74 | 38.7 | 17.83 | 0 |
| no-damping ablation | 3 | 0.31 | 0.54 ± 0.02 | 2.9 ± 1.0 | 5669 ± 165 | 664 | 7.28 | 30.0 | 13.17 | 0 |

Per phase (alternating trace):

| Policy | quiet miss % | busy miss % | quiet mean q | busy mean q | reaction s | recovery s |
| --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 0.0 | 0.0 | 1.00 | 1.00 | – | – |
| fixed q=2 | 0.0 | 0.0 | 2.00 | 2.00 | – | – |
| fixed q=4 | 0.5 | 0.4 | 4.00 | 4.00 | – | – |
| fixed q=8 | 4.4 | 3.5 | 8.00 | 8.00 | – | – |
| adaptive | 2.3 | 2.3 | 5.64 | 5.84 | 4.4 | 0.1 |
| no-damping ablation | 3.0 | 2.9 | 7.12 | 7.44 | 8.0 | 0.3 |

Reaction = busy phase starts → first step down. Recovery = busy phase ends → q back at its level from before the busy phase. – = never happened in the phase.

**Comparison:** the best fixed depth that keeps misses ≤ 5 % is fixed q=8 (3.7 % misses, 5965 MiB/s). Adaptive: 2.3 % misses, 5024 MiB/s (-16 % scan rate vs that fixed depth).

### constant trace

| Policy | reps | FG p50 ms | FG p99 ms | miss % | scan MiB/s | scan GiB | mean q | q changes | reversals/min | rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 3 | 0.15 | 0.20 ± 0.00 | 0.0 ± 0.0 | 3276 ± 28 | 384 | 1.00 | 0.0 | 0.00 | 0 |
| fixed q=2 | 3 | 0.19 | 0.28 ± 0.02 | 0.0 ± 0.0 | 4799 ± 27 | 562 | 2.00 | 0.0 | 0.00 | 0 |
| fixed q=4 | 3 | 0.26 | 0.41 ± 0.04 | 0.3 ± 0.2 | 4277 ± 9 | 501 | 4.00 | 0.0 | 0.00 | 0 |
| fixed q=8 | 3 | 0.33 | 0.57 ± 0.01 | 5.9 ± 0.8 | 5896 ± 46 | 691 | 8.00 | 0.0 | 0.00 | 0 |
| adaptive | 3 | 0.29 | 0.54 ± 0.00 | 2.5 ± 0.0 | 5016 ± 50 | 588 | 5.67 | 40.3 | 18.67 | 0 |
| no-damping ablation | 3 | 0.31 | 0.55 ± 0.01 | 3.3 ± 0.6 | 5548 ± 195 | 650 | 7.00 | 44.0 | 20.17 | 0 |

**Comparison:** the best fixed depth that keeps misses ≤ 5 % is fixed q=2 (0.0 % misses, 4799 MiB/s). Adaptive: 2.5 % misses, 5016 MiB/s (5 % scan rate vs that fixed depth).

## Study C: overload

### overload trace

| Policy | reps | FG p50 ms | FG p99 ms | miss % | scan MiB/s | scan GiB | mean q | q changes | reversals/min | rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 2 | 0.14 | 0.20 ± 0.00 | 0.0 ± 0.0 | 3229 ± 36 | 378 | 1.00 | 0.0 | 0.00 | 0 |
| fixed q=2 | 2 | 0.18 | 0.28 ± 0.00 | 0.0 ± 0.0 | 4600 ± 38 | 539 | 2.00 | 0.0 | 0.00 | 0 |
| fixed q=4 | 2 | 0.23 | 0.39 ± 0.00 | 0.2 ± 0.1 | 4257 ± 5 | 499 | 4.00 | 0.0 | 0.00 | 0 |
| fixed q=8 | 2 | 0.32 | 0.60 ± 0.04 | 5.1 ± 0.3 | 5695 ± 46 | 667 | 8.00 | 0.0 | 0.00 | 0 |
| adaptive | 2 | 0.30 | 0.56 ± 0.00 | 3.3 ± 0.4 | 5256 ± 181 | 616 | 6.76 | 19.0 | 8.50 | 0 |

**Comparison:** the best fixed depth that keeps misses ≤ 5 % is fixed q=2 (0.0 % misses, 4600 MiB/s). Adaptive: 3.3 % misses, 5256 MiB/s (14 % scan rate vs that fixed depth).

## Study C: 1 MiB chunks

### alternating trace

| Policy | reps | FG p50 ms | FG p99 ms | miss % | scan MiB/s | scan GiB | mean q | q changes | reversals/min | rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 2 | 0.20 | 0.32 ± 0.00 | 0.0 ± 0.0 | 4422 ± 43 | 518 | 1.00 | 0.0 | 0.00 | 0 |
| fixed q=2 | 2 | 0.30 | 0.58 ± 0.02 | 3.5 ± 0.3 | 6292 ± 8 | 737 | 2.00 | 0.0 | 0.00 | 0 |
| fixed q=4 | 2 | 0.49 | 1.02 ± 0.22 | 47.1 ± 0.8 | 7106 ± 43 | 833 | 4.00 | 0.0 | 0.00 | 0 |
| fixed q=8 | 2 | 1.24 | 1.93 ± 0.05 | 100.0 ± 0.0 | 7050 ± 41 | 826 | 8.00 | 0.0 | 0.00 | 0 |
| adaptive | 2 | 0.27 | 0.54 ± 0.01 | 2.3 ± 0.3 | 5811 ± 24 | 681 | 1.75 | 21.5 | 9.50 | 0 |

Per phase (alternating trace):

| Policy | quiet miss % | busy miss % | quiet mean q | busy mean q | reaction s | recovery s |
| --- | --- | --- | --- | --- | --- | --- |
| fixed q=1 | 0.1 | 0.0 | 1.00 | 1.00 | – | – |
| fixed q=2 | 3.8 | 3.5 | 2.00 | 2.00 | – | – |
| fixed q=4 | 47.8 | 46.9 | 4.00 | 4.00 | – | – |
| fixed q=8 | 100.0 | 100.0 | 8.00 | 8.00 | – | – |
| adaptive | 2.5 | 2.2 | 1.68 | 1.82 | 9.0 | 0.0 |

Reaction = busy phase starts → first step down. Recovery = busy phase ends → q back at its level from before the busy phase. – = never happened in the phase.

**Comparison:** the best fixed depth that keeps misses ≤ 5 % is fixed q=2 (3.5 % misses, 6292 MiB/s). Adaptive: 2.3 % misses, 5811 MiB/s (-8 % scan rate vs that fixed depth).

## Actual depth and pending queues (Study B)

| Trace | Policy | configured q (mean) | actual BG in flight (mean) | FG pending (mean / max) |
| --- | --- | --- | --- | --- |
| alternating | adaptive | 5.74 | 4.55 | 0.00 / 0 |
| alternating | no-damping ablation | 7.28 | 5.71 | 0.00 / 0 |
| alternating | fixed q=1 | 1.00 | 0.74 | 0.00 / 0 |
| alternating | fixed q=2 | 2.00 | 1.45 | 0.00 / 0 |
| alternating | fixed q=4 | 4.00 | 3.24 | 0.00 / 0 |
| alternating | fixed q=8 | 8.00 | 6.25 | 0.00 / 0 |
| constant | adaptive | 5.67 | 4.50 | 0.00 / 0 |
| constant | no-damping ablation | 7.00 | 5.50 | 0.00 / 0 |
| constant | fixed q=1 | 1.00 | 0.75 | 0.00 / 0 |
| constant | fixed q=2 | 2.00 | 1.45 | 0.00 / 0 |
| constant | fixed q=4 | 4.00 | 3.24 | 0.00 / 0 |
| constant | fixed q=8 | 8.00 | 6.27 | 0.00 / 0 |

## Controller CPU cost and safe reductions

- Controller decision: mean 1.18 µs per window, max 3.18 µs (one decision per 1000 ms window).
- Whole dispatcher process CPU per run: adaptive 94.8 s, fixed 89.9 s.
- Cuts of q below the reads already in flight: 215 in total; longest drain 0.311 ms; in every run no BG read was sent while bg_out ≥ q.

## Diagnosis: oscillation and recovery (adaptive vs no-damping ablation)

| Trace | Policy | q changes | reversals/min | time at q=1/2/4/8 (%) | miss % | scan MiB/s |
| --- | --- | --- | --- | --- | --- | --- |
| alternating | adaptive | 38.7 | 17.83 | 0/3/52/45 | 2.3 | 5024 |
| alternating | no-damping ablation | 30.0 | 13.17 | 0/1/16/83 | 2.9 | 5669 |
| constant | adaptive | 40.3 | 18.67 | 0/3/54/43 | 2.5 | 5016 |
| constant | no-damping ablation | 44.0 | 20.17 | 0/2/22/76 | 3.3 | 5548 |

A reversal is q going up then down (or down then up). Many reversals = oscillation.

Figures: `B_constant_timeseries.png`, `B_alternating_timeseries.png`, `B_tradeoff_miss.png`, `B_tradeoff_p99.png`, `ablation_oscillation.png`, `C_overload.png`, `C_chunk1m.png`, `C_chunk1m_timeseries.png`, `C_overload_timeseries.png`.

Platform note: all runs use only the course server (babbage). Its disk is a shared Dell PERC H755 RAID virtual disk. The 0.5 ms target was frozen from Study A (Milestone 2) on the same server, before these evaluation runs.
