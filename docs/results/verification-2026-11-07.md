# Local worked result — 7 November 2026

Command: `make verify` from the repository root.
Source tested: `1b49a2e346afce02f354cc2bcaa0bd9b6a839a71`.
Recorded at: `2026-11-07T12:53:16.892322+00:00`.
Environment: macOS 27.2, Python 3.14.3, x86_64 process, localhost.
Status: **PASS** (command exit 0). No third-party package installation or
privileged network configuration was required.

## Reproduce and inspect

```sh
git clone https://github.com/jyotirawattech/linux-network-reliability-lab.git
cd linux-network-reliability-lab
make verify
```

The command runs the nine unit/localhost integration tests, reruns them under
the statement-line coverage runner, then runs the measured experiment. Both
test passes succeeded. Coverage was **184/226 statement-start lines (81.4%)**,
above the 80% gate. The experiment passed all four objectives.

The experiment prints JSON and rewrites `docs/results/latest.json` with the new
run. That generated file is expected to differ locally. This dated record keeps
the observed values below separate from earlier records; timing differences
alone are not regressions.

## Observed JSON output

```json
{
  "environment": "localhost; Python standard library; no privileged network access",
  "experiment": "portable-http-fault-lab",
  "fault_model": "application-layer request rejection and delay",
  "limitations": [
    "Portable mode does not emulate kernel queueing, reordering, corruption, or TCP retransmission.",
    "Localhost results demonstrate the method and state machine; they are not production SLO evidence.",
    "Timing varies by host load, so objectives use bounded thresholds rather than exact values."
  ],
  "measurements": {
    "baseline_median_latency_ms": 1.67,
    "failed_requests": 4,
    "injected_median_latency_ms": 126.2,
    "loss_requests": 12,
    "observed_latency_delta_ms": 124.53,
    "observed_loss_percent": 33.33,
    "outage_detection_ms": 54.13,
    "recovery_detection_ms": 54.59
  },
  "monitor": {
    "failures_to_degrade": 2,
    "poll_interval_ms": 50,
    "successes_to_recover": 2,
    "timeout_ms": 250
  },
  "objectives": {
    "detect_outage_under_300_ms": true,
    "deterministic_loss_is_exact": true,
    "inject_at_least_100_ms_latency": true,
    "recover_under_300_ms": true
  },
  "result": "PASS"
}
```

## Read the engineering result

The fault gateway rejects requests 3, 6, 9 and 12 with HTTP 503, giving the
expected four failures. In the outage scenario it rejects every health probe.
The monitor changes state only after two consecutive qualifying probes:
`UNKNOWN` → `HEALTHY` → `DEGRADED` → `HEALTHY`. The harness, not the monitor,
clears the outage by restoring normal forwarding.

The delay scenario added 124.53 ms to the median of seven sequential requests
compared with seven baseline requests. This measures the injected delay in this
small experiment; it is not a throughput or comparative optimization benchmark.

The reported outage/restoration durations use the **start** of the qualifying
probe. They exclude that final probe's completion time, so they are not elapsed
repair time, production MTTR, or guaranteed end-to-end detection deadlines.
See [the measurement boundary](../walkthrough.md#interpret-the-timing-carefully).

The `loss` names in the JSON/code refer to application-layer request rejection.
No kernel packet loss, TCP retransmission, distributed failover or automatic
repair is exercised. This local run is not a new public CI result, device test,
production SLO or customer outcome.
