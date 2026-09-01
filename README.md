# Linux Network Reliability Lab

An original, public-safe reliability experiment by Jyoti Rawat. It runs a small
localhost work service behind a programmable fault gateway, injects delay,
deterministic request loss, and a service outage, then measures detection and
recovery through a threshold-based monitor.

The project uses synthetic traffic and no employer code, logs, metrics, or
architecture.

## Why this exists

Reliability claims are stronger when another engineer can reproduce the failure,
inspect the detection policy, and see the measured recovery. This lab keeps that
proof small enough to review while making limitations explicit.

## Run it

Requires Python 3.11+ and `make`; the core path has no third-party dependencies.

```bash
make verify
```

The command runs unit and localhost integration tests, enforces an 80% statement-
line coverage floor, executes the fault scenarios, prints the measurements, and
writes `docs/results/latest.json`.

## Acceptance objectives

- inject at least 100 ms of observable latency;
- reject exactly every third request in the deterministic loss scenario;
- detect a sustained outage within 300 ms;
- detect recovery within 300 ms;
- pass the test and coverage gates on Python 3.11 and 3.13 in CI.

These thresholds are lab objectives, not production SLO recommendations.

## Design evidence

- [Architecture and failure flow](docs/architecture.md)
- [ADR 0001: portable deterministic faults](docs/adr/0001-portable-deterministic-faults.md)
- [Leadership and release memo](docs/leadership-memo.md)
- [Candidate execution plan](docs/candidate-execution-plan.md)
- [Local verification record](docs/results/verification-2026-09-02.md)
- [Public CI verification](https://github.com/jyotirawattech/linux-network-reliability-lab/actions/runs/33557699028)
- [Latest machine-readable result](docs/results/latest.json)

## Evidence labels

- **Demonstrated:** localhost service, gateway, monitoring state machine,
  deterministic fault scenarios, 9 passing tests, 81.4% statement-line
  coverage, locally measured results, and public CI verification on Python 3.11
  and 3.13.
- **Planned:** a separate Linux network-namespace experiment using `tc netem`.
- **Not claimed:** production reliability improvement, kernel packet-loss behavior,
  Kubernetes operations, customer adoption, or employer outcomes.

## Repository map

```text
src/reliability_lab/       service, fault gateway, monitor and experiment
tests/                     unit and localhost integration tests
scripts/                   experiment and dependency-free coverage runners
docs/                      architecture, decision, leadership and result evidence
.github/workflows/ci.yml   public CI matrix for Python 3.11 and 3.13
```

## Next technical experiment

Run the same monitor against a Linux network namespace with `tc netem`, compare
kernel-level loss and delay against the portable gateway model, and document where
the observations diverge. That work should be released as a separate result so it
does not blur the v0.1 evidence boundary.

## License

MIT.
