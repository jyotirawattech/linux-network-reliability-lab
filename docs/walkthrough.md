# Run and understand the reliability experiment

This walkthrough follows the implemented experiment in
[`src/reliability_lab/lab.py`](../src/reliability_lab/lab.py). It uses a work service
and gateway on temporary localhost ports. The harness controls the faults and
the monitor decides when the observed health state changes.

## 1. Run the verification

From the repository root, with Python 3.11+ and `make` installed:

```bash
make verify
```

The command runs three stages in order:

| Stage | Command | Success condition |
|---|---|---|
| Unit and integration tests | `make test` | All nine tests pass |
| Statement-line coverage | `make coverage` | Tests pass and coverage is at least 80% |
| Measured scenarios | `make experiment` | All four experiment objectives are true |

No package installation is needed. Each stage can be rerun independently. The
coverage stage runs the test suite again, so seeing two test summaries is normal.
The final experiment prints JSON and rewrites `docs/results/latest.json` with that
run's measurements. A new run therefore creates a local Git diff in that file.
Review it as new evidence; a timing difference alone is not a regression.

The services bind to `127.0.0.1` and let the operating system assign free ports.
There is no fixed browser URL or long-running service after the command finishes.

## 2. Follow the scenarios

### Baseline and delay

The harness sends seven sequential `GET /work` requests through the gateway with
normal forwarding, then seven with an added 120 ms delay. Each request uses a
one-second timeout. The reported latency includes the request through the
gateway to the backend and the response.

The experiment subtracts the baseline median from the delayed median and checks
that the difference is at least 100 ms. Medians reduce the influence of one slow
sample; they do not make seven requests a production benchmark.

### Deterministic request rejection

The controller resets its request counter and rejects every third request. Of
12 sequential `GET /work` requests, requests 3, 6, 9, and 12 receive HTTP 503.
Exactly four failures are required to pass the check.

The code calls this mode `loss`, but it rejects requests at the HTTP gateway.
No packet is deliberately discarded by the kernel. This deterministic pattern
makes the count testable without a random seed or a probabilistic tolerance.

### Outage and return to health

The harness restores normal forwarding and waits for the monitor to become
`HEALTHY`. It then configures `outage`, causing the gateway to return HTTP 503 for
every request. The monitor probes `GET /health` and waits for `DEGRADED`.

Next, the harness configures `pass` again. After two successful health probes,
the monitor returns to `HEALTHY`. The experiment measures detection of that
restored forwarding. It does not restart the backend, repair a real failure, or
perform failover.

## 3. Inspect the health policy

`MonitorConfig` supplies these defaults:

| Setting | Value | Meaning |
|---|---:|---|
| `poll_interval_ms` | 50 | Pause after an unsuccessful wait-loop iteration |
| `timeout_ms` | 250 | Timeout passed to each health probe |
| `failures_to_degrade` | 2 | Consecutive failures needed to declare `DEGRADED` |
| `successes_to_recover` | 2 | Consecutive successes needed to declare `HEALTHY` |

The monitor begins in `UNKNOWN`. A successful probe increments the success count
and resets the failure count; a failing probe does the reverse. The default
experiment follows `UNKNOWN` → `HEALTHY` → `DEGRADED` → `HEALTHY`.

The anti-flapping test deliberately supplies the sequence
`success, success, failure, success, failure, failure, success, success`. It checks
that an isolated failure does not degrade a healthy monitor and an isolated
success does not recover a degraded one.

These thresholds trade faster detection for resistance to isolated samples. The
50 ms value is a sleep between probes, not a fixed-rate scheduler: probe work
and host scheduling add time. `wait_for` normally gives the state change two
seconds before raising `TimeoutError`; the experiment separately requires each
reported outage/restoration duration to remain under 300 ms.

## 4. Read the output

After successful tests, the output includes:

```text
Ran 9 tests
OK
Statement-line coverage: 184/226 (81.4%)
Coverage gate passed: 81.4% >= 80.0%
```

The JSON contains `monitor`, `measurements`, `objectives`, `limitations`, and a
final `result`. All four values in `objectives` must be `true` for `result` to be
`PASS`. The experiment command exits nonzero for a failed objective.

One observed run on **1 November 2026**, on **macOS 27.2 with Python 3.14.3**, had:

```json
{
  "baseline_median_latency_ms": 1.34,
  "injected_median_latency_ms": 126.99,
  "observed_latency_delta_ms": 125.65,
  "loss_requests": 12,
  "failed_requests": 4,
  "observed_loss_percent": 33.33,
  "outage_detection_ms": 56.01,
  "recovery_detection_ms": 56.23
}
```

Those are observed values, not constants to match exactly. The tracked
`latest.json` can contain a different earlier run until you run the experiment.
The [original dated record](results/verification-2026-09-02.md) preserves the
earlier verification separately.

### Interpret the timing carefully

The harness records `time.monotonic()` immediately after changing the fault mode.
`sample_once` also records its timestamp **before** executing the probe. A
transition receives that sample-start timestamp when the qualifying result
arrives. The reported difference therefore excludes the duration of the final
qualifying probe. It is not the elapsed time until the caller receives the
completed transition.

That distinction is small for the immediate localhost HTTP 503/200 responses in
this experiment. It matters much more for slow or timed-out probes. Do not use
these figures as proof of end-to-end repair time, production MTTR, or a guaranteed
detection deadline under arbitrary network conditions.

## 5. Troubleshoot a local run

| Symptom | Check and next step |
|---|---|
| `python3` missing or Python older than 3.11 | Install/select Python 3.11+ and confirm `python3 --version` before running again. |
| `make` unavailable | Run the three commands from `Makefile` in a terminal at the repository root: tests, coverage runner, then experiment runner, each with `PYTHONPATH=src`. |
| `ModuleNotFoundError: reliability_lab` | Run from the repository root through `make`, which supplies `PYTHONPATH=src`. |
| `PermissionError` while binding localhost | Check the terminal/sandbox policy for permission to open loopback sockets. The experiment needs local sockets, not root or internet exposure. |
| Timing objective fails or `wait_for` times out | Inspect the specific objective and host load; rerun once on an idle host and preserve both results. A failed run remains failed evidence. |
| Browser connection refused after completion | Expected: the experiment closes both temporary servers. Inspect the terminal output and JSON file. |
| Coverage differs from the recorded value | Check the source revision, Python version, and tests. This custom metric counts executed AST statement-start lines; it is not branch coverage. |

The [nine tests](../tests/test_lab.py) cover deterministic decisions, invalid fault
configuration, monitor state transitions/timeouts, actual HTTP forwarding and
injection, unknown paths, stack lifecycle guards, and experiment acceptance.
They do not claim exhaustive concurrency, security, performance, or failure-path
coverage.

## 6. Connect local evidence to CI

The [workflow](../.github/workflows/ci.yml) runs the same test, coverage, and
experiment commands on GitHub-hosted Linux with Python 3.11 and 3.13. Each matrix
job uploads its JSON result as a separate artifact.

Public run
[33557893891](https://github.com/jyotirawattech/linux-network-reliability-lab/actions/runs/33557893891)
passed for commit `10f369c`. That dated receipt applies to that revision; later
revisions need their own checks. The badge on the README links to current
workflow history.

## Boundaries and extension

The current model covers HTTP request rejection and delay with synthetic traffic.
It does not emulate kernel queueing, packet reordering/corruption, TCP
retransmission, distributed consensus, real service-process death, or automatic
repair. Production availability, customer adoption, and employer outcomes are
outside this evidence.

A planned Linux network-namespace experiment with `tc netem` can compare actual
kernel-level faults against this model. It needs its own implementation,
privilege review, and measurements before being described as demonstrated.
