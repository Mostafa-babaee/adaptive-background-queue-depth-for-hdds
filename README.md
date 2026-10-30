# Adaptive Background Queue Depth for HDDs

CSC 720: Storage Systems — Project 03.

A read-only C/io_uring dispatcher studies the tradeoff between 4 KiB foreground reads and sequential background scanning. Fixed background limits are 1, 2, 4 and 8. Adaptive evaluation is the next phase.

## Team

Mostafa Babaei, Muhammad Ahmad Tariq, and Sheryar Karim.

Mostafa handles dispatcher integration and correctness checks. Ahmad handles policy settings and analysis. Sheryar handles workloads, experiment execution, hardware records and report coordination. The integrated baseline was supplied as an AI-assisted reference implementation and revised by the team; it is distinct from Mostafa's earlier standalone prototype.

## Milestone 2

- [Source, build and reproduction instructions](milestone2/README.md)
- [Phase progress report](milestone2/submission/PROGRESS_UPDATE.md)
- [Linux validation](milestone2/docs/LINUX_VALIDATION.md): 8 C scenarios, 36 Python tests and 15 Linux dispatcher tests passed, no skips. All 18 source-file hashes match the Babbage receipt.
- [Original-data audit](milestone2/docs/HANDOFF_AUDIT.md): all 27 reference runs checked, 48,746,023 request records audited, and 459 per-run metric values reproduced.
- [Reference baseline results](milestone2/evidence/reference/results/studyA/): unchanged aggregate CSVs and figures from the original build.
- [Evidence packaging and provenance](milestone2/docs/PUBLIC_EVIDENCE.md)

The performance dataset describes Babbage's shared PERC RAID storage. It is preliminary evidence for that platform, separate from the revised program's correctness tests. It does not establish single physical-HDD performance or completion of the full project's adaptive evaluation. The 0.5 ms target remains provisional.

## Earlier work

[Milestone 1 documentation](docs/MILESTONE1_README.md), [smoke reader and evidence](milestone1/), and [Python foreground/background pilot](foreground_background_pilot/) remain available. The Milestone 1 submission commit is dfceada3bf4d78a8a400642ec97eb66f3d16737a.

## License

The team's original source and associated software documentation are under the [MIT License](LICENSE). Course materials and third-party content retain their own terms.
