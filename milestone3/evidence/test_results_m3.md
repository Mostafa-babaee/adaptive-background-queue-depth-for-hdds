# Milestone 3 test results (2026-11-12 11:09 CST, babbage)

```
C submission scenarios:   PASS: 8 submission-batch scenarios
C controller unit tests:  controller tests: 63 checks, 0 failed (7 test groups)
py_analysis: Ran 39 tests in 0.743s OK: /home/sgf.edubear.net/mt6289s/milestone3/results/tmpqlwxx3ku/fixture.dat (256 blocks, file_id=1) matches the pattern
py_dispatcher: Ran 15 tests in 25.071s Retained dispatcher evidence: /home/sgf.edubear.net/mt6289s/milestone3/tests/_tmp_m2_1794503329
py_adaptive: Ran 10 tests in 15.287s OK
```

## Every test
```
test_adaptive_run_clean (test_adaptive.AdaptiveTests.test_adaptive_run_clean) ... ok
test_bad_options (test_adaptive.AdaptiveTests.test_bad_options) ... ok
test_ctrl_c_with_reads_in_flight (test_adaptive.AdaptiveTests.test_ctrl_c_with_reads_in_flight) ... ok
test_fixed_policy_unchanged (test_adaptive.AdaptiveTests.test_fixed_policy_unchanged) ... ok
test_no_new_bg_until_drained (test_adaptive.AdaptiveTests.test_no_new_bg_until_drained) ... ok
test_nodamp_up_every_window (test_adaptive.AdaptiveTests.test_nodamp_up_every_window) ... ok
test_safe_reduction_below_outstanding (test_adaptive.AdaptiveTests.test_safe_reduction_below_outstanding) ... ok
test_sparse_windows_hold (test_adaptive.AdaptiveTests.test_sparse_windows_hold) ... ok
test_up_after_three_good_windows (test_adaptive.AdaptiveTests.test_up_after_three_good_windows) ... ok
test_window_log_matches_requests (test_adaptive.AdaptiveTests.test_window_log_matches_requests) ... ok
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
test_adaptive_matches_python (test_ctrl_match.ControllerMatch.test_adaptive_matches_python) ... ok
test_frozen_config_values (test_ctrl_match.ControllerMatch.test_frozen_config_values) ... ok
test_nodamp_matches_python (test_ctrl_match.ControllerMatch.test_nodamp_matches_python) ... ok
test_choose_target_rule (test_study_a.StudyATests.test_choose_target_rule) ... ok
test_metrics (test_study_a.StudyATests.test_metrics) ... ok
test_no_target_gives_nan_miss (test_study_a.StudyATests.test_no_target_gives_nan_miss) ... ok
test_existing_fixture_not_replaced (test_tools.ToolTests.test_existing_fixture_not_replaced) ... ok
test_generator_handles_partial_writes (test_tools.ToolTests.test_generator_handles_partial_writes) ... ok
test_invalid_fixture_size (test_tools.ToolTests.test_invalid_fixture_size) ... ok
test_trace_repeatability_and_exclusive_output (test_tools.ToolTests.test_trace_repeatability_and_exclusive_output) ... ok
test_actual_tail_bytes_used_by_metrics (test_validation.ValidationTests.test_actual_tail_bytes_used_by_metrics) ... ok
test_duplicate_id_rejected (test_validation.ValidationTests.test_duplicate_id_rejected) ... ok
test_duplicate_repetition (test_validation.ValidationTests.test_duplicate_repetition) ... ok
test_early_end_rejected (test_validation.ValidationTests.test_early_end_rejected) ... ok
test_full_dataset_and_missing_repetition (test_validation.ValidationTests.test_full_dataset_and_missing_repetition) ... ok
test_inconsistent_counters_rejected (test_validation.ValidationTests.test_inconsistent_counters_rejected) ... ok
test_interrupt_rejected (test_validation.ValidationTests.test_interrupt_rejected) ... ok
test_invalid_run_excluded_before_summary (test_validation.ValidationTests.test_invalid_run_excluded_before_summary) ... ok
test_legacy_tail_ambiguity_rejected (test_validation.ValidationTests.test_legacy_tail_ambiguity_rejected) ... ok
test_missing_direct_flag_rejected (test_validation.ValidationTests.test_missing_direct_flag_rejected) ... ok
test_missing_trace_rejected (test_validation.ValidationTests.test_missing_trace_rejected) ... ok
test_valid_run (test_validation.ValidationTests.test_valid_run) ... ok
test_wrong_trace_rejected (test_validation.ValidationTests.test_wrong_trace_rejected) ... ok
test_bad_arguments (test_dispatcher.DispatcherTests.test_bad_arguments) ... ok
test_corrupted_data_detected (test_dispatcher.DispatcherTests.test_corrupted_data_detected) ... ok
test_end_of_file (test_dispatcher.DispatcherTests.test_end_of_file) ... ok
test_existing_results_preserved (test_dispatcher.DispatcherTests.test_existing_results_preserved) ... ok
test_full_queue_rejects (test_dispatcher.DispatcherTests.test_full_queue_rejects) ... ok
test_invalid_numeric_and_policy_arguments (test_dispatcher.DispatcherTests.test_invalid_numeric_and_policy_arguments) ... ok
test_malformed_trace_rejected (test_dispatcher.DispatcherTests.test_malformed_trace_rejected) ... ok
test_normal_end_drains_and_keeps_due_arrivals (test_dispatcher.DispatcherTests.test_normal_end_drains_and_keeps_due_arrivals) ... ok
test_q_and_quota_limits (test_dispatcher.DispatcherTests.test_q_and_quota_limits) ... ok
test_read_error_logged (test_dispatcher.DispatcherTests.test_read_error_logged) ... ok
test_same_trace_same_requests (test_dispatcher.DispatcherTests.test_same_trace_same_requests) ... ok
test_shutdown_ctrl_c (test_dispatcher.DispatcherTests.test_shutdown_ctrl_c) ... ok
test_shutdown_early_stop (test_dispatcher.DispatcherTests.test_shutdown_early_stop) ... ok
test_symlink_input_rejected (test_dispatcher.DispatcherTests.test_symlink_input_rejected) ... ok
test_verified_contents (test_dispatcher.DispatcherTests.test_verified_contents) ... ok
```
