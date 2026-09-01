from __future__ import annotations

import json
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from reliability_lab import FaultController, LabStack, MonitorConfig, ReliabilityMonitor, run_experiment


class FaultControllerTests(unittest.TestCase):
    def test_loss_is_deterministic(self) -> None:
        controller = FaultController()
        controller.configure("loss", drop_every=3)
        decisions = [controller.decision()[1] for _ in range(6)]
        self.assertEqual(decisions, [False, False, True, False, False, True])
        self.assertEqual(controller.snapshot()["request_count"], 6)

    def test_invalid_fault_configuration_is_rejected(self) -> None:
        controller = FaultController()
        with self.assertRaises(ValueError):
            controller.configure("unknown")
        with self.assertRaises(ValueError):
            controller.configure("latency", latency_ms=-1)
        with self.assertRaises(ValueError):
            controller.configure("loss", drop_every=1)


class MonitorTests(unittest.TestCase):
    def test_thresholds_prevent_single_sample_flapping(self) -> None:
        samples = iter([True, True, False, True, False, False, True, True])
        monitor = ReliabilityMonitor(
            "synthetic://health",
            MonitorConfig(failures_to_degrade=2, successes_to_recover=2),
            probe=lambda url, timeout: next(samples),
        )

        states = []
        for tick in range(8):
            monitor.sample_once(now=float(tick))
            states.append(monitor.state)

        self.assertEqual(
            states,
            ["UNKNOWN", "HEALTHY", "HEALTHY", "HEALTHY", "HEALTHY", "DEGRADED", "DEGRADED", "HEALTHY"],
        )
        self.assertEqual([event.current for event in monitor.transitions], ["HEALTHY", "DEGRADED", "HEALTHY"])

    def test_wait_for_times_out_when_state_never_changes(self) -> None:
        monitor = ReliabilityMonitor(
            "synthetic://health",
            MonitorConfig(poll_interval_ms=1),
            probe=lambda url, timeout: True,
        )
        with self.assertRaises(TimeoutError):
            monitor.wait_for("DEGRADED", timeout_seconds=0.01)


class NetworkIntegrationTests(unittest.TestCase):
    def test_gateway_forwards_and_injects_faults(self) -> None:
        with LabStack() as lab:
            with urlopen(f"{lab.endpoint}/work", timeout=1) as response:
                payload = json.loads(response.read())
            self.assertEqual(payload["result"], "synthetic-work-complete")

            lab.controller.configure("latency", latency_ms=30)
            started = time.perf_counter()
            with urlopen(f"{lab.endpoint}/health", timeout=1) as response:
                self.assertEqual(response.status, 200)
            self.assertGreaterEqual((time.perf_counter() - started) * 1000, 25)

            lab.controller.configure("outage")
            with self.assertRaises(HTTPError) as context:
                urlopen(f"{lab.endpoint}/health", timeout=1)
            self.assertEqual(context.exception.code, 503)
            context.exception.close()

    def test_unknown_path_is_forwarded_as_not_found(self) -> None:
        with LabStack() as lab:
            with self.assertRaises(HTTPError) as context:
                urlopen(f"{lab.endpoint}/missing", timeout=1)
            self.assertEqual(context.exception.code, 404)
            context.exception.close()

    def test_endpoint_requires_started_stack(self) -> None:
        with self.assertRaises(RuntimeError):
            _ = LabStack().endpoint

    def test_stack_rejects_double_start(self) -> None:
        with LabStack() as lab:
            with self.assertRaises(RuntimeError):
                lab.start()


class AcceptanceExperimentTests(unittest.TestCase):
    def test_experiment_meets_objectives(self) -> None:
        result = run_experiment()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(all(result["objectives"].values()))
        self.assertEqual(result["measurements"]["failed_requests"], 4)
        self.assertGreaterEqual(result["measurements"]["observed_latency_delta_ms"], 100)


if __name__ == "__main__":
    unittest.main()
