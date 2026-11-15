# Milestone 3 results

The revised dispatcher ran on Babbage's shared Dell PERC H755 RAID storage. Study B contains 36 runs with three repetitions per condition. It compares all four fixed limits, adaptive control, and the no-damping variant on constant and alternating traces. Study C contains 20 runs with two repetitions per condition. It covers a high-demand trace and a second scan chunk size of 1 MiB. The high-demand runs recorded no rejections and zero foreground pending requests at the sampled windows. Dedicated physical-HDD evaluation remains open.

On the alternating 256 KiB trace, adaptive averaged 2.3% foreground target misses and 5,024 MiB/s of background scan throughput. Fixed q=8 averaged 3.7% misses and 5,965 MiB/s. The 0.5 ms threshold was set from the earlier Study A runs on Babbage. See the [full results](../evidence/m3_20261112T171109Z_a98ce9/summary.md) for all comparisons and their variation.

The [Babbage test logs](../evidence/_tests/) report eight C submission scenarios, 63 C controller checks, and 64 Python tests passing. The full experiment folder includes per-run tables, window summaries, plots, original traces, and the experiment settings. The quick-check results have their own folder.

The raw per-request logs remain on Babbage under `logs/m3_20261112T171109Z_a98ce9/` in the original account. The [raw-log checksum list](../evidence/m3_20261112T171109Z_a98ce9/raw_logs.sha256) covers 168 files. There is currently no public download link. The terminal log records the original execution. The experiment metadata records the original binary SHA-256 and an unknown Git commit, so the GitHub submission commit identifies the published package.

The published source uses the newer review archive. Both supplied code manifests verified. The review package adds an option and configuration for a third Study C repetition. Its dispatcher and controller are byte-identical to the original handoff source. The [source records](../evidence/source_provenance/) preserve both original manifests and the earlier runner. The top-level `MANIFEST.sha256` covers this GitHub package. No third-repetition results were supplied.
