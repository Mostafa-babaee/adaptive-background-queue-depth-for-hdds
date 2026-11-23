# Adaptive Background Queue Depth for HDDs

CSC 720: Storage Systems — Project 03.

A read-only C/io_uring dispatcher studies the tradeoff between 4 KiB foreground reads and sequential background scanning. Policies include fixed background limits of 1, 2, 4 and 8, a feedback controller, and a learned queue-depth policy.

## Team

Mostafa Babaei, Muhammad Ahmad Tariq, and Sheryar Karim.

Mostafa handles dispatcher integration and correctness checks. Ahmad handles policy settings and analysis. Sheryar handles workloads, experiment execution, hardware records and report coordination. The integrated baseline was supplied as an AI-assisted reference implementation and revised by the team; it is distinct from Mostafa's earlier standalone prototype.

## Milestone 4

- [RL dispatcher, build instructions, and short demo](milestone4/README.md)
- [Frozen RL policy and settings](milestone4/config/rl_policy.json)
- [RL training and simulator code](milestone4/rl_training/)
- [Simulator and short VM read-test evidence](milestone4/evidence/)

The learned policy chooses the next background depth from a frozen 36-entry table. The analysis supports RL request logs, and the tests cover policy behavior and result validation.

## Milestone 3

- [Adaptive controller, dispatcher, and reproduction instructions](milestone3/README.md)
- [Milestone 3 results and limitations](milestone3/docs/RESULTS.md)
- [Study B and C tables, plots, traces, and checksums](milestone3/evidence/m3_20261112T171109Z_a98ce9/)
- [Babbage test logs](milestone3/evidence/_tests/)

The team tested adaptive control against fixed depths on constant and alternating traces, then tested higher demand and a second scan chunk size. The 56 runs describe Babbage's shared RAID storage. Study B has three repetitions per condition and Study C has two.

## Milestone 2

- [Source, build and reproduction instructions](milestone2/README.md)
- [Phase progress report](milestone2/submission/PROGRESS_UPDATE.md)
- [Linux validation](milestone2/docs/LINUX_VALIDATION.md): 8 C scenarios, 36 Python tests and 15 Linux dispatcher tests passed, no skips. All 18 source-file hashes match the Babbage receipt.
- [Original-data audit](milestone2/docs/HANDOFF_AUDIT.md): all 27 reference runs checked, 48,746,023 request records audited, and 459 per-run metric values reproduced.
- [Reference baseline results](milestone2/evidence/reference/results/studyA/): unchanged aggregate CSVs and figures from the original build.
- [Evidence packaging and provenance](milestone2/docs/PUBLIC_EVIDENCE.md)

The course performance measurements use the professor-approved Babbage shared Dell PERC RAID storage. Platform details are recorded alongside each dataset.

## Earlier work

[Milestone 1 documentation](docs/MILESTONE1_README.md), [smoke reader and evidence](milestone1/), and [Python foreground/background pilot](foreground_background_pilot/) remain available. The Milestone 1 submission commit is dfceada3bf4d78a8a400642ec97eb66f3d16737a.

## License

The team's original source and associated software documentation are under the [MIT License](LICENSE). Course materials and third-party content retain their own terms.
