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

## Evidence boundary

This is a verified local run. The GitHub Actions workflow is prepared but has not
run in a public repository. The timing data is localhost evidence, not a
production SLO or customer outcome. Request rejection occurs at the application
gateway and must not be described as kernel packet loss.
