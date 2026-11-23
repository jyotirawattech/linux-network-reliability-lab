"""Independent checks of the finite, single-message acknowledgement model."""

import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from reliability_lab.delivery_experiment import Fault, Policy, simulate, worked_results


class DeliveryExperimentTests(unittest.TestCase):
    def check_replay(self, policy, faults, effects, duplicates, suppressed, settled, events):
        result = simulate(policy, faults)
        self.assertEqual(
            result,
            {
                "attempts": len(events),
                "effects": effects,
                "duplicate_effects": duplicates,
                "suppressed_effects": suppressed,
                "settled": settled,
                "trace": [
                    {"fault": fault.value, "events": row}
                    for fault, row in zip(faults, events)
                ],
            },
        )
        return result

    def test_empty_budget_is_valid_and_unsettled(self):
        for policy in Policy:
            with self.subTest(policy=policy):
                self.check_replay(policy, (), 0, 0, 0, False, [])

    def test_early_ack_orders_effect_and_can_settle_without_effect(self):
        for fault, effects, events in (
            (Fault.CLEAN, 1, ["ack_settled", "effect_applied"]),
            (Fault.BEFORE_EFFECT, 0, ["ack_settled", "crash_before_effect"]),
            (
                Fault.AFTER_EFFECT,
                1,
                ["ack_settled", "effect_applied", "crash_after_effect"],
            ),
        ):
            with self.subTest(fault=fault):
                self.check_replay(
                    Policy.ACK_FIRST, (fault, Fault.CLEAN), effects, 0, 0, True, [events]
                )
        self.check_replay(
            Policy.ACK_FIRST,
            (Fault.ACK_LOST, Fault.ACK_LOST, Fault.CLEAN),
            1, 0, 0, True,
            [["ack_lost"], ["ack_lost"], ["ack_settled", "effect_applied"]],
        )

    def test_pre_effect_crash_has_no_effect_or_marker(self):
        for policy in (Policy.ACK_LAST, Policy.ATOMIC_MARKER):
            with self.subTest(policy=policy):
                self.check_replay(
                    policy, (Fault.BEFORE_EFFECT, Fault.CLEAN, Fault.ACK_LOST),
                    1, 0, 0, True,
                    [["crash_before_effect"], ["effect_applied", "ack_settled"]],
                )

    def test_late_ack_repeats_effect_after_crash_and_lost_ack(self):
        self.check_replay(
            Policy.ACK_LAST,
            (Fault.AFTER_EFFECT, Fault.ACK_LOST, Fault.CLEAN, Fault.CLEAN),
            3, 2, 0, True,
            [
                ["effect_applied", "crash_after_effect"],
                ["effect_applied", "ack_lost"],
                ["effect_applied", "ack_settled"],
            ],
        )

    def test_atomic_marker_suppresses_replay_without_settling_lost_ack(self):
        self.check_replay(
            Policy.ATOMIC_MARKER,
            (Fault.AFTER_EFFECT, Fault.ACK_LOST, Fault.CLEAN),
            1, 0, 2, True,
            [
                ["effect_applied", "crash_after_effect"],
                ["effect_suppressed", "ack_lost"],
                ["effect_suppressed", "ack_settled"],
            ],
        )
        for policy, effects, duplicates, suppressed, events in (
            (Policy.ACK_FIRST, 0, 0, 0, [["ack_lost"], ["ack_lost"]]),
            (
                Policy.ACK_LAST, 2, 1, 0,
                [["effect_applied", "ack_lost"], ["effect_applied", "ack_lost"]],
            ),
            (
                Policy.ATOMIC_MARKER, 1, 0, 1,
                [["effect_applied", "ack_lost"], ["effect_suppressed", "ack_lost"]],
            ),
        ):
            with self.subTest(exhausted_policy=policy):
                self.check_replay(
                    policy, (Fault.ACK_LOST, Fault.ACK_LOST),
                    effects, duplicates, suppressed, False, events,
                )

    def test_all_short_budgets_obey_accounting_and_stop_at_settlement(self):
        # 341 distinct tuples, each replayed under all three policies: 1,023 cases.
        allowed_events = {
            "ack_settled", "ack_lost", "effect_applied", "effect_suppressed",
            "crash_before_effect", "crash_after_effect",
        }
        for length in range(5):
            for faults in itertools.product(tuple(Fault), repeat=length):
                for policy in Policy:
                    with self.subTest(policy=policy, faults=faults):
                        result = simulate(policy, faults)
                        rows = result["trace"]
                        self.assertEqual(result["attempts"], len(rows))
                        self.assertLessEqual(len(rows), length)
                        self.assertEqual(
                            [row["fault"] for row in rows],
                            [fault.value for fault in faults[:len(rows)]],
                        )
                        flat = [event for row in rows for event in row["events"]]
                        self.assertTrue(set(flat) <= allowed_events)
                        self.assertEqual(result["effects"], flat.count("effect_applied"))
                        self.assertEqual(
                            result["suppressed_effects"], flat.count("effect_suppressed")
                        )
                        self.assertEqual(
                            result["duplicate_effects"], max(0, result["effects"] - 1)
                        )
                        self.assertEqual(result["settled"], "ack_settled" in flat)
                        self.assertNotIn("ack_settled", [
                            event for row in rows[:-1] for event in row["events"]
                        ])
                        if not result["settled"]:
                            self.assertEqual(len(rows), length)
                        if policy is Policy.ATOMIC_MARKER:
                            self.assertLessEqual(result["effects"], 1)
                        else:
                            self.assertEqual(result["suppressed_effects"], 0)

    def test_rejects_non_enum_and_non_tuple_inputs(self):
        for policy, faults in (
            ("ack_first", (Fault.CLEAN,)),
            (None, (Fault.CLEAN,)),
            (Policy.ACK_LAST, [Fault.CLEAN]),
            (Policy.ACK_LAST, None),
            (Policy.ACK_LAST, ("clean",)),
            (Policy.ACK_LAST, (None,)),
            (Policy.ACK_LAST, (Fault.CLEAN, "bad")),
        ):
            with self.subTest(policy=policy, faults=faults):
                with self.assertRaises(ValueError):
                    simulate(policy, faults)

    def test_worked_results_match_saved_json_and_fresh_cli_bytes(self):
        root = Path(__file__).resolve().parents[1]
        expected_bytes = (root / "docs/results/delivery-replay.json").read_bytes()
        expected = json.loads(expected_bytes)
        self.assertEqual(worked_results(), expected)
        first = worked_results()
        # Callers must not be able to corrupt a later independently produced result.
        first["clean"]["ack_first"]["trace"][0]["events"].clear()
        self.assertEqual(worked_results(), expected)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root / "src")
        result = subprocess.run(
            [sys.executable, "-m", "reliability_lab.delivery_experiment"],
            cwd=root, env=environment, capture_output=True, check=True, timeout=10,
        )
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, expected_bytes)
        self.assertEqual(json.loads(result.stdout), expected)


if __name__ == "__main__":
    unittest.main()
