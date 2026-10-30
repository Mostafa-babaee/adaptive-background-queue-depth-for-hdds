# Milestone 2 progress update

Mostafa Babaei, Muhammad Ahmad Tariq, Sheryar Karim — CSC 720, Project 03.

We adopted the integrated reference dispatcher provided in Ahmad and Sheryar's handoff. It uses separate foreground and background test files, a repeatable foreground trace, two queues and one C/io_uring path. Fixed background limits are 1, 2, 4 and 8. Every returned block is checked against a file-ID and block-ID pattern.

Mostafa's earlier standalone dispatcher passed 16 executed Linux correctness tests, 18 executed simulated-backend checks and six short foreground/background demo cases. That evidence belongs to the earlier program. The reference handoff separately reports 29 passing server tests. The current integration adds submission, shutdown, logging and validation corrections; it passed eight C submission scenarios, 36 Python tests and 15 Linux dispatcher tests on Babbage with no skips. The downloaded receipt matches all 18 source files.

The supplied Study A aggregate data contains 27 runs: foreground alone, scanner alone at four limits and combined work at four limits, with three repetitions each. The reported combined-run mean foreground p99 increases from about 0.35 ms at q=1 to 1.27 ms at q=8, while mean scan throughput increases from about 2,950 to 5,001 MiB/s. The published means and standard deviations match the per-run aggregate CSV. The complete handoff has now passed an independent audit of all 27 raw runs: 48,746,023 request records checked and 459 per-run metric values reproduced.

These measurements came from the original AI-assisted reference dispatcher on Babbage's shared Dell PERC RAID storage. They are preliminary results for that setup. They do not establish performance on the department's separate physical HDD, and they were not produced by the revised code in this folder.

The reference analysis selected a provisional 0.5 ms target, a 1000 ms window and 25 minimum samples. The configs now preserve that calibration consistently. The team must confirm the calibration and the acceptable hardware platform before treating those settings as final.

The revised runner preserves existing results and uses no global cache flush. The revised analysis requires complete, validated raw datasets before making final summaries or freezing settings. It uses actual returned bytes when a scan ends with a short aligned chunk.

The final Milestone 2 source and evidence are included in this snapshot. Each member will present their own contribution in the group recording. Adaptive-policy experiments remain the next milestone.
