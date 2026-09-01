# Local verification record — 2 September 2026

Status: **PASS**
Environment: macOS localhost, Python 3.14.3
Command: `make verify`

## Quality gates

- 9 of 9 unit and localhost integration tests passed.
- Statement-line coverage was 184 of 226 lines, or 81.4%.
- The configured minimum coverage gate was 80.0%.

## Measured experiment

| Measurement | Observed | Acceptance objective |
|---|---:|---:|
| Baseline median latency | 1.50 ms | Recorded for comparison |
| Injected median latency | 127.45 ms | — |
| Added median latency | 125.95 ms | At least 100 ms |
| Deterministic request loss | 4 of 12 (33.33%) | Exactly every third request |
| Outage detection | 56.33 ms | Under 300 ms |
| Recovery detection | 56.51 ms | Under 300 ms |

All four experiment objectives passed. The machine-readable result is in
`latest.json`.

## Public CI verification

- GitHub Actions run
  [33557699028](https://github.com/jyotirawattech/linux-network-reliability-lab/actions/runs/33557699028)
  completed successfully for commit `7c07024`.
- Python 3.11 and Python 3.13 jobs both passed the tests, 80% coverage gate, and
  deterministic reliability experiment.
- Each job published a machine-readable reliability-results artifact.

## Evidence boundary

The measurements in this record come from the verified local run; public CI
independently verifies the same acceptance gates in GitHub-hosted Linux runners.
The timing data is synthetic localhost evidence, not a production SLO or customer
outcome. Request rejection occurs at the application gateway and must not be
described as kernel packet loss.
