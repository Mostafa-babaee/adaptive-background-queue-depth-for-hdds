# Revised dispatcher: Babbage validation

On October 30, 2026, the revised integration compiled and passed validation on Babbage using Linux 6.8.0-106-generic, Python 3.12.3 and the local liburing 2.5 installation. Compilation used -Wall -Wextra -Werror.

| Check | Passed | Skipped |
|---|---:|---:|
| C submission-batch scenarios | 8 | 0 |
| Python controller, analysis, validation and tool tests | 36 | 0 |
| Linux io_uring dispatcher tests | 15 | 0 |
| Total | 59 | 0 |

The downloaded validation.json contains hashes of 18 source files. All 18 match this source snapshot exactly. The retained test logs confirm the counts above. This validates the revised implementation's tested functionality; it is not a rerun of the original 27 performance experiments.

Evidence: evidence/linux_validation/validation_20261030T202213Z_S8ECSG/. Request CSVs, window CSVs, traces, metadata and the receipt are included. Generated .dat fixtures are omitted from the distributable copy; tests regenerate them. The full downloaded copy remains locally preserved under evidence/babbage_download/.

The test cases intentionally include corrupt files, read errors, queue overload and interrupted runs. Their logged error outcomes are expected test evidence, not performance measurements. Do not combine them into Study A summaries.

The source receipt covers C/Python files under src, analysis, tests and tools. It does not checksum the compiler, linked liburing binary, shell scripts or Makefile; the terminal transcript separately records the build command. Reproduction on another system may require its own dependency setup.
