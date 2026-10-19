# Foreground/background pilot

Threaded direct-read prototype; exploratory functional/interference results only.

| Case | FG successes | FG p50 ms | FG p99 ms* | BG MiB/s | Rejected | Errors | Peak BG jobs |
|---|---:|---:|---:|---:|---:|---:|---:|
| repeat1_foreground_only_q1 | 100 | 0.397 | 0.780 | 0.000 | 0 | 0 | 0 |
| repeat1_mixed_q4 | 100 | 0.383 | 1.449 | 8.175 | 0 | 0 | 4 |
| repeat1_mixed_q1 | 100 | 0.395 | 0.497 | 8.175 | 0 | 0 | 1 |
| repeat1_mixed_q8 | 100 | 0.375 | 0.988 | 8.175 | 0 | 0 | 8 |
| repeat1_mixed_q2 | 100 | 0.365 | 0.446 | 8.175 | 0 | 0 | 2 |
| repeat1_background_only_q1 | 0 | - | - | 8.175 | 0 | 0 | 1 |
| repeat2_foreground_only_q1 | 100 | 0.393 | 0.534 | 0.000 | 0 | 0 | 0 |
| repeat2_mixed_q1 | 100 | 0.506 | 0.785 | 8.175 | 0 | 0 | 1 |
| repeat2_mixed_q2 | 100 | 0.390 | 0.800 | 8.175 | 0 | 0 | 2 |
| repeat2_mixed_q8 | 100 | 0.408 | 0.492 | 8.175 | 0 | 0 | 8 |
| repeat2_background_only_q1 | 0 | - | - | 8.175 | 0 | 0 | 1 |
| repeat2_mixed_q4 | 100 | 0.376 | 0.545 | 8.175 | 0 | 0 | 4 |
| repeat3_mixed_q1 | 100 | 0.393 | 0.674 | 8.175 | 0 | 0 | 1 |
| repeat3_foreground_only_q1 | 100 | 0.391 | 0.802 | 0.000 | 0 | 0 | 0 |
| repeat3_mixed_q2 | 100 | 0.391 | 1.017 | 8.175 | 0 | 0 | 2 |
| repeat3_mixed_q8 | 100 | 0.390 | 1.237 | 8.175 | 0 | 0 | 8 |
| repeat3_background_only_q1 | 0 | - | - | 8.175 | 0 | 0 | 1 |
| repeat3_mixed_q4 | 100 | 0.376 | 0.504 | 8.175 | 0 | 0 | 4 |

*Short-run p99 is unstable. Rejections/errors are separate from successful-read percentiles.
BG rate is capped; a common rate ceiling or small cached fixture can hide queue-depth effects.
Each run drains submitted work; throughput includes drain time. Each case starts its scan at offset zero.
No final HDD-performance, adaptive-policy, or optimal-q conclusion is supported.
