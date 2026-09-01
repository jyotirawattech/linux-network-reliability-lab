"""Portable network fault lab built only with the Python standard library.

The default CI-safe mode injects deterministic failures at an HTTP gateway. It
does not claim to reproduce kernel packet scheduling. A Linux ``tc netem``
extension is described separately for privileged, kernel-level experiments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from statistics import median
from threading import Lock, Thread
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class MonitorConfig:
    poll_interval_ms: int = 50
    timeout_ms: int = 250
    failures_to_degrade: int = 2
    successes_to_recover: int = 2


@dataclass(frozen=True)
class Transition:
    previous: str
    current: str
    timestamp: float
    reason: str


class FaultController:
    """Thread-safe deterministic fault policy for the gateway."""

    MODES = {"pass", "latency", "loss", "outage"}

    def __init__(self) -> None:
        self._lock = Lock()
        self._mode = "pass"
        self._latency_ms = 0
        self._drop_every = 0
        self._request_count = 0

    def configure(self, mode: str, *, latency_ms: int = 0, drop_every: int = 0) -> None:
        if mode not in self.MODES:
            raise ValueError(f"unsupported fault mode: {mode}")
        if latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if mode == "loss" and drop_every < 2:
            raise ValueError("loss mode requires drop_every >= 2")
        with self._lock:
            self._mode = mode
            self._latency_ms = latency_ms
            self._drop_every = drop_every
            self._request_count = 0

    def decision(self) -> tuple[float, bool, str]:
        with self._lock:
            self._request_count += 1
            mode = self._mode
            latency_seconds = self._latency_ms / 1000
            if mode == "outage":
                return latency_seconds, True, "synthetic service outage"
            if mode == "loss" and self._request_count % self._drop_every == 0:
                return latency_seconds, True, "deterministic request loss"
            return latency_seconds, False, "pass"

    def snapshot(self) -> dict[str, int | str]:
        with self._lock:
            return {
                "mode": self._mode,
                "latency_ms": self._latency_ms,
                "drop_every": self._drop_every,
                "request_count": self._request_count,
            }


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _backend_handler() -> type[_QuietHandler]:
    class BackendHandler(_QuietHandler):
        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if self.path == "/health":
                self.send_json(200, {"component": "work-service", "status": "ok"})
                return
            if self.path == "/work":
                self.send_json(200, {"result": "synthetic-work-complete"})
                return
            self.send_json(404, {"error": "not found"})

    return BackendHandler


def _gateway_handler(controller: FaultController, backend_url: str) -> type[_QuietHandler]:
    class GatewayHandler(_QuietHandler):
        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            latency_seconds, reject, reason = controller.decision()
            if latency_seconds:
                time.sleep(latency_seconds)
            if reject:
                self.send_json(503, {"component": "fault-gateway", "error": reason})
                return

            request = Request(f"{backend_url}{self.path}", method="GET")
            try:
                with urlopen(request, timeout=0.5) as response:
                    body = response.read()
                    status = response.status
                    content_type = response.headers.get("Content-Type", "application/json")
            except HTTPError as error:
                try:
                    body = error.read()
                    status = error.code
                    content_type = error.headers.get("Content-Type", "application/json")
                finally:
                    error.close()
            except (URLError, TimeoutError):
                self.send_json(502, {"component": "fault-gateway", "error": "backend unavailable"})
                return

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return GatewayHandler


class _RunningServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


class LabStack:
    """Backend plus a programmable localhost gateway."""

    def __init__(self) -> None:
        self.controller = FaultController()
        self._backend: _RunningServer | None = None
        self._gateway: _RunningServer | None = None

    @property
    def endpoint(self) -> str:
        if self._gateway is None:
            raise RuntimeError("lab stack has not been started")
        return self._gateway.url

    def start(self) -> "LabStack":
        if self._backend is not None or self._gateway is not None:
            raise RuntimeError("lab stack is already running")
        self._backend = _RunningServer(_backend_handler())
        self._backend.start()
        self._gateway = _RunningServer(_gateway_handler(self.controller, self._backend.url))
        self._gateway.start()
        return self

    def stop(self) -> None:
        if self._gateway is not None:
            self._gateway.stop()
            self._gateway = None
        if self._backend is not None:
            self._backend.stop()
            self._backend = None

    def __enter__(self) -> "LabStack":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.stop()


def probe_ok(url: str, timeout_seconds: float) -> bool:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            response.read()
            return response.status == 200
    except HTTPError as error:
        error.close()
        return False
    except (URLError, TimeoutError):
        return False


class ReliabilityMonitor:
    """Small state machine with anti-flap success and failure thresholds."""

    def __init__(
        self,
        health_url: str,
        config: MonitorConfig | None = None,
        probe: Callable[[str, float], bool] = probe_ok,
    ) -> None:
        self.health_url = health_url
        self.config = config or MonitorConfig()
        self._probe = probe
        self.state = "UNKNOWN"
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.transitions: list[Transition] = []

    def sample_once(self, *, now: float | None = None) -> Transition | None:
        sampled_at = time.monotonic() if now is None else now
        ok = self._probe(self.health_url, self.config.timeout_ms / 1000)
        if ok:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            if self.state != "HEALTHY" and self.consecutive_successes >= self.config.successes_to_recover:
                return self._transition("HEALTHY", sampled_at, "success threshold reached")
            return None

        self.consecutive_failures += 1
        self.consecutive_successes = 0
        if self.state != "DEGRADED" and self.consecutive_failures >= self.config.failures_to_degrade:
            return self._transition("DEGRADED", sampled_at, "failure threshold reached")
        return None

    def wait_for(self, expected_state: str, timeout_seconds: float = 2.0) -> Transition:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            transition = self.sample_once()
            if self.state == expected_state:
                if transition is not None:
                    return transition
                return self.transitions[-1]
            time.sleep(self.config.poll_interval_ms / 1000)
        raise TimeoutError(f"monitor did not reach {expected_state} within {timeout_seconds}s")

    def _transition(self, current: str, timestamp: float, reason: str) -> Transition:
        transition = Transition(self.state, current, timestamp, reason)
        self.state = current
        self.transitions.append(transition)
        return transition


def _request_latency_ms(url: str, timeout_seconds: float = 1.0) -> tuple[bool, float]:
    started = time.perf_counter()
    ok = probe_ok(url, timeout_seconds)
    return ok, (time.perf_counter() - started) * 1000


def run_experiment() -> dict[str, object]:
    """Run the repeatable acceptance experiment and return measured evidence."""

    monitor_config = MonitorConfig()
    with LabStack() as lab:
        baseline_samples = [_request_latency_ms(f"{lab.endpoint}/work")[1] for _ in range(7)]

        lab.controller.configure("latency", latency_ms=120)
        latency_samples = [_request_latency_ms(f"{lab.endpoint}/work")[1] for _ in range(7)]

        lab.controller.configure("loss", drop_every=3)
        loss_samples = [_request_latency_ms(f"{lab.endpoint}/work")[0] for _ in range(12)]

        lab.controller.configure("pass")
        monitor = ReliabilityMonitor(f"{lab.endpoint}/health", monitor_config)
        monitor.wait_for("HEALTHY")

        lab.controller.configure("outage")
        outage_started = time.monotonic()
        degraded = monitor.wait_for("DEGRADED")
        detection_ms = (degraded.timestamp - outage_started) * 1000

        lab.controller.configure("pass")
        recovery_started = time.monotonic()
        healthy = monitor.wait_for("HEALTHY")
        recovery_ms = (healthy.timestamp - recovery_started) * 1000

    failed_requests = loss_samples.count(False)
    baseline_median = median(baseline_samples)
    latency_median = median(latency_samples)
    objectives = {
        "detect_outage_under_300_ms": detection_ms < 300,
        "recover_under_300_ms": recovery_ms < 300,
        "inject_at_least_100_ms_latency": latency_median - baseline_median >= 100,
        "deterministic_loss_is_exact": failed_requests == 4,
    }
    return {
        "experiment": "portable-http-fault-lab",
        "environment": "localhost; Python standard library; no privileged network access",
        "fault_model": "application-layer request rejection and delay",
        "monitor": asdict(monitor_config),
        "measurements": {
            "baseline_median_latency_ms": round(baseline_median, 2),
            "injected_median_latency_ms": round(latency_median, 2),
            "observed_latency_delta_ms": round(latency_median - baseline_median, 2),
            "loss_requests": len(loss_samples),
            "failed_requests": failed_requests,
            "observed_loss_percent": round(failed_requests / len(loss_samples) * 100, 2),
            "outage_detection_ms": round(detection_ms, 2),
            "recovery_detection_ms": round(recovery_ms, 2),
        },
        "objectives": objectives,
        "result": "PASS" if all(objectives.values()) else "FAIL",
        "limitations": [
            "Portable mode does not emulate kernel queueing, reordering, corruption, or TCP retransmission.",
            "Localhost results demonstrate the method and state machine; they are not production SLO evidence.",
            "Timing varies by host load, so objectives use bounded thresholds rather than exact values.",
        ],
    }
