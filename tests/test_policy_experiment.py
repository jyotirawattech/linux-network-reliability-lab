from dataclasses import replace
import unittest
from unittest.mock import patch

from reliability_lab import MonitorConfig
from reliability_lab.policy_experiment import Observation, replay_policy, run_policy_comparison


class PolicyReplayTests(unittest.TestCase):
    def test_isolated_failure_changes_baseline_but_not_two_sample_policy(self):
        samples = [Observation(0, True), Observation(50, False), Observation(100, True)]
        baseline = replay_policy(samples, MonitorConfig(failures_to_degrade=1, successes_to_recover=1))
        filtered = replay_policy(samples, MonitorConfig())
        self.assertEqual(baseline["noise_degradations"], 1)
        self.assertEqual(baseline["transition_count"], 2)
        self.assertEqual(filtered["transition_count"], 0)

    def test_sustained_outage_exposes_sample_delay_tradeoff(self):
        case = next(c for c in run_policy_comparison()["cases"] if c["name"] == "sustained_outage")
        outages = [p["outages"][0] for p in case["policies"]]
        self.assertEqual([o["detection_delay_ms"] for o in outages], [0, 50, 100])
        self.assertEqual([o["recovery_delay_ms"] for o in outages], [0, 50, 100])
        self.assertTrue(all(o["detection_status"] == "detected" for o in outages))

    def test_short_outage_is_not_detected_by_higher_thresholds(self):
        case = next(c for c in run_policy_comparison()["cases"] if c["name"] == "one_sample_outage")
        self.assertEqual([p["outages"][0]["detection_status"] for p in case["policies"]], ["detected", "not_detected", "not_detected"])
        self.assertIsNone(case["policies"][1]["outages"][0]["detection_delay_ms"])
        self.assertEqual(case["policies"][1]["outages"][0]["recovery_status"], "not_needed")

    def test_failed_recovery_probe_resets_success_counter(self):
        case = next(c for c in run_policy_comparison()["cases"] if c["name"] == "noisy_restoration")
        self.assertEqual([p["outages"][0]["recovery_delay_ms"] for p in case["policies"]], [0, 150, 200])
        self.assertEqual([p["noise_degradations"] for p in case["policies"]], [1, 0, 0])

    def test_warmup_is_not_a_recovery_event(self):
        result = replay_policy([Observation(0, True)], MonitorConfig())
        self.assertEqual(result["transitions"], [])
        self.assertEqual(result["outages"], [])

    def test_failure_streak_is_reset_by_success(self):
        samples = [Observation(0, False), Observation(50, True), Observation(100, False)]
        self.assertEqual(replay_policy(samples, MonitorConfig())["transition_count"], 0)

    def test_outage_at_end_has_no_observed_restoration(self):
        result = replay_policy([Observation(0, False, True), Observation(50, False, True)], MonitorConfig())
        self.assertEqual(result["outages"][0]["detection_delay_ms"], 50)
        self.assertEqual(result["outages"][0]["recovery_status"], "restoration_not_observed")

    def test_multiple_outages_preserve_already_degraded_state(self):
        samples = [Observation(0, False, True), Observation(50, False, True), Observation(100, True), Observation(150, False, True), Observation(200, False, True), Observation(250, True), Observation(300, True)]
        result = replay_policy(samples, MonitorConfig())
        first, second = result["outages"]
        self.assertEqual(first["recovery_status"], "not_recovered_in_window")
        self.assertEqual(second["detection_status"], "already_degraded")
        self.assertIsNone(second["detection_delay_ms"])
        self.assertEqual(second["recovery_delay_ms"], 50)

    def test_late_degradation_after_restoration_keeps_window_attribution_explicit(self):
        samples = [Observation(0, False, True), Observation(50, False), Observation(100, True), Observation(150, True)]
        result = replay_policy(samples, MonitorConfig())
        self.assertEqual(result["transitions"], [
            {"previous": "HEALTHY", "current": "DEGRADED", "at_ms": 50},
            {"previous": "DEGRADED", "current": "HEALTHY", "at_ms": 150},
        ])
        self.assertEqual(result["noise_degradations"], 1)
        outage = result["outages"][0]
        self.assertEqual(outage["detection_status"], "not_detected")
        self.assertIsNone(outage["detection_delay_ms"])
        self.assertEqual(outage["recovery_status"], "not_needed")
        self.assertIsNone(outage["recovery_delay_ms"])

    def test_irregular_input_timestamps_are_used_instead_of_poll_interval(self):
        samples = [Observation(7, False, True), Observation(90, False, True), Observation(110, True), Observation(350, True)]
        result = replay_policy(samples, MonitorConfig())
        self.assertEqual(result["outages"][0]["detection_delay_ms"], 83)
        self.assertEqual(result["outages"][0]["recovery_delay_ms"], 240)

    def test_invalid_config_is_rejected_before_replay(self):
        for name in ["poll_interval_ms", "timeout_ms", "failures_to_degrade", "successes_to_recover"]:
            for value in [0, -1, True, 1.5]:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replay_policy([Observation(0, True)], replace(MonitorConfig(), **{name: value}))
        with self.assertRaises(ValueError):
            replay_policy([Observation(0, True)], MonitorConfig(failures_to_degrade=1001))
        with self.assertRaises(ValueError):
            replay_policy([Observation(0, True)], MonitorConfig(successes_to_recover=1001))
        with self.assertRaises(ValueError):
            replay_policy([Observation(0, True)], MonitorConfig(timeout_ms=60_001))
        with self.assertRaises(ValueError):
            replay_policy([Observation(0, True)], None)

    def test_invalid_trace_is_rejected(self):
        bad = [[], [Observation(-1, True)], [Observation(0, True), Observation(0, False)], [Observation(50, True), Observation(0, False)], [Observation(True, True)], [Observation(0, 1)], [Observation(0, False, 1)], [Observation(0, True, True)], [Observation(86_400_001, True)], [None], [Observation(0, True)] * 10_001]
        for samples in bad:
            with self.subTest(samples=samples[:2]), self.assertRaises(ValueError):
                replay_policy(samples, MonitorConfig())
        with self.assertRaises(ValueError):
            replay_policy(iter([Observation(0, True)]), MonitorConfig())

    def test_worked_result_is_deterministic_and_not_a_timing_benchmark(self):
        result = run_policy_comparison()
        self.assertEqual(result, run_policy_comparison())
        self.assertEqual(result["benchmark"], {"paired_wall_clock": "not_run", "measured_speedup": None})

    def test_worked_comparison_never_calls_the_network_probe(self):
        with patch("reliability_lab.lab.urlopen", side_effect=AssertionError("network probe called")), patch("socket.socket", side_effect=AssertionError("socket opened")):
            self.assertEqual(len(run_policy_comparison()["cases"]), 4)


if __name__ == "__main__":
    unittest.main()
