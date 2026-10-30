# Evidence status

## Available and checked

The supplied original reference snapshot, server test summary, hardware record, per-run aggregate CSV, summary CSV, provisional target and four figures are retained. There are 27 aggregate rows with three repetitions per condition; 162 means/standard deviations were independently checked against those rows. This earlier aggregate check is now supplemented by the request-level audit described below.

Mostafa's earlier standalone-dispatcher evidence is retained separately. Its 16 executed Linux tests, 18 executed simulated-backend checks and six demonstration cases passed, but they do not validate the newly adopted reference implementation.

Local revised-code checks are documented in LOCAL_VALIDATION.md. The downloaded Babbage Linux receipt has now been reviewed: all 18 source hashes match, and all 59 checks passed without skips. See LINUX_VALIDATION.md.

## Original handoff received and audited

M2_handoff_for_Mostafa.zip is available locally and verified. The nested archive checksum matches, as do all 26 available original source-manifest entries. All 27 raw runs passed the independent audit: 48,746,023 request records checked and 459 per-run metric values reproduced. The original traces, terminal output and both adaptive configuration versions are retained. See HANDOFF_AUDIT.md for scope, provenance and shutdown accounting.

## Configuration history

The original reference ZIP contains the pre-freeze adaptive config. The supplied manifest expects its post-analysis frozen counterpart. Reconstructing that counterpart with the documented 0.5/1000/25 settings and the original writer's note reproduces the recorded hash exactly. The original metadata confirms all 27 experiments used fixed policies with no target. The handoff documents adaptive.json as a post-analysis output, and its frozen copy matches the manifest. The revised config retains these settings as provisional, with a note identifying their RAID provenance.

## Phase closure

The revised Linux validation and original-data audit are complete. Publish the Milestone 2 source and labelled evidence; finalize slides and recordings. The Linux correctness run is not a new performance experiment. Keep the distinction between the original measured source and revised source in the report, slides and demo.
