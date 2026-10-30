# Test results (2026-10-30 10:25 CDT, babbage)

```
test_ablation_steps_up_every_good_window (test_controller.TestAdaptive.test_ablation_steps_up_every_good_window) ... ok
test_bad_config_rejected (test_controller.TestAdaptive.test_bad_config_rejected) ... ok
test_config_file_loads (test_controller.TestAdaptive.test_config_file_loads) ... ok
test_exact_threshold_boundaries (test_controller.TestAdaptive.test_exact_threshold_boundaries) ... ok
test_middle_window_resets_streak (test_controller.TestAdaptive.test_middle_window_resets_streak) ... ok
test_needs_three_good_windows_to_step_up (test_controller.TestAdaptive.test_needs_three_good_windows_to_step_up) ... ok
test_never_above_max (test_controller.TestAdaptive.test_never_above_max) ... ok
test_never_below_one (test_controller.TestAdaptive.test_never_below_one) ... ok
test_not_scanning_holds (test_controller.TestAdaptive.test_not_scanning_holds) ... ok
test_q_always_allowed_value (test_controller.TestAdaptive.test_q_always_allowed_value) ... ok
test_sparse_window_holds (test_controller.TestAdaptive.test_sparse_window_holds) ... ok
test_sparse_window_keeps_streak (test_controller.TestAdaptive.test_sparse_window_keeps_streak) ... ok
test_starts_at_q_start (test_controller.TestAdaptive.test_starts_at_q_start) ... ok
test_step_down_on_misses (test_controller.TestAdaptive.test_step_down_on_misses) ... ok
test_never_changes (test_controller.TestFixed.test_never_changes) ... ok
test_rejects_bad_q (test_controller.TestFixed.test_rejects_bad_q) ... ok
test_choose_target_rule (test_study_a.StudyATests.test_choose_target_rule) ... ok
test_metrics (test_study_a.StudyATests.test_metrics) ... ok
test_no_target_gives_nan_miss (test_study_a.StudyATests.test_no_target_gives_nan_miss) ... ok
Ran 19 tests in 0.022s
OK
test_bad_arguments (tests.test_dispatcher.DispatcherTests.test_bad_arguments) ... ok
test_corrupted_data_detected (tests.test_dispatcher.DispatcherTests.test_corrupted_data_detected) ... ok
test_end_of_file (tests.test_dispatcher.DispatcherTests.test_end_of_file) ... ok
test_full_queue_rejects (tests.test_dispatcher.DispatcherTests.test_full_queue_rejects) ... ok
test_q_and_quota_limits (tests.test_dispatcher.DispatcherTests.test_q_and_quota_limits) ... ok
test_read_error_logged (tests.test_dispatcher.DispatcherTests.test_read_error_logged) ... ok
test_same_trace_same_requests (tests.test_dispatcher.DispatcherTests.test_same_trace_same_requests) ... ok
test_shutdown_ctrl_c (tests.test_dispatcher.DispatcherTests.test_shutdown_ctrl_c) ... ok
test_shutdown_early_stop (tests.test_dispatcher.DispatcherTests.test_shutdown_early_stop) ... ok
test_verified_contents (tests.test_dispatcher.DispatcherTests.test_verified_contents) ... ok
Ran 10 tests in 23.215s
OK
```
