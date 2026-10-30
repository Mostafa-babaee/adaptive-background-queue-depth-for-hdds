# Study A results (fixed-depth baselines)

Logs: `logs/studyA`. Runs: 27. Warm-up dropped. Values are mean ± sd over repetitions.

Integrity: 27 of 27 runs clean (accounting OK, 0 errors, all bytes verified, O_DIRECT).

| Run type | q | reps | FG p50 ms | FG p99 ms | wait p99 ms | service p99 ms | miss % | scan MiB/s | actual depth | rejected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scanner alone | 1 | 3 | – | – ± – | – | – | – | 2931.9 ± 286.5 | 0.69 | 0 |
| scanner alone | 2 | 3 | – | – ± – | – | – | – | 4078.2 ± 298.3 | 1.34 | 0 |
| scanner alone | 4 | 3 | – | – ± – | – | – | – | 3584.4 ± 353.6 | 3.03 | 0 |
| scanner alone | 8 | 3 | – | – ± – | – | – | – | 4914.3 ± 646.8 | 5.97 | 0 |
| foreground alone | – | 3 | 0.22 | 0.58 ± 0.21 | 0.21 | 0.27 | 1.0 | 0.0 ± 0.0 | 0.00 | 0 |
| combined | 1 | 3 | 0.15 | 0.35 ± 0.02 | 0.15 | 0.21 | 0.2 | 2949.7 ± 112.6 | 0.72 | 0 |
| combined | 2 | 3 | 0.21 | 0.60 ± 0.05 | 0.21 | 0.42 | 2.2 | 3801.5 ± 256.7 | 1.30 | 0 |
| combined | 4 | 3 | 0.28 | 1.01 ± 0.05 | 0.40 | 0.66 | 7.1 | 3939.9 ± 57.9 | 3.20 | 0 |
| combined | 8 | 3 | 0.38 | 1.27 ± 0.16 | 0.67 | 0.68 | 22.9 | 5001.0 ± 718.9 | 5.98 | 0 |

## Frozen latency target and controller settings

- **target_ms = 0.5** (1.25 × mean p99 of the combined run at q = 1, rounded up to 0.5 ms)
- window_ms = 1000, min_samples = 25 (a window holds about twice min_samples at the trace rate, so quiet windows are not sparse)
- miss_high = 0.05, miss_low = 0.01, up_windows = 3

Figures: `studyA_tradeoff.png` (required), `studyA_scan_throughput.png`, `studyA_latency_cdf.png`, `studyA_actual_depth.png`.
