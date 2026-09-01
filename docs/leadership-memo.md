# Leadership memo: release a credible reliability lab before expanding scope

To: Engineering reviewers and project contributors
From: Jyoti Rawat
Date: 2 September 2026
Decision requested: Approve the v0.1 evidence boundary and release gates

## Recommendation

Release a small, reproducible v0.1 that proves four things well: a service can be
observed, latency and failures can be injected, degradation and recovery can be
detected, and the result can be independently reproduced. Do not add a dashboard,
Kubernetes, eBPF, or cloud deployment until reviewers can run the core experiment
and challenge its assumptions.

## Priorities

1. **Truthful evidence:** distinguish application-layer request rejection from
   kernel packet loss and distinguish localhost measurements from production SLOs.
2. **Reproducibility:** keep the acceptance path dependency-free and deterministic.
3. **Operational reasoning:** record thresholds, detection delay, recovery delay,
   limitations, and failure modes—not only a green test result.
4. **Reviewability:** keep the implementation small enough for an interviewer or
   contributor to understand in one sitting.

## Trade-offs

Two-sample thresholds reduce alert flapping but add at least one polling interval
to detection and recovery. A 50 ms poll interval is intentionally aggressive for
the lab; a production value would need service cost, error budget, and alert-noise
analysis. Deterministic request rejection makes CI stable but cannot demonstrate
TCP retransmission, queueing, or packet reordering. Those are explicit follow-up
experiments, not implied capabilities.

## Release plan

| Gate | Evidence | Exit condition |
|---|---|---|
| v0.1 local candidate | Tests, coverage gate, JSON experiment | All objectives pass on a clean checkout |
| v0.1 public candidate | README review and secret/IP scan | No employer material, credentials, or unsupported claim |
| v0.2 Linux extension | Namespace plus `tc netem` experiment | Root requirement documented; portable path still passes |
| v0.3 resilience option | Retry/backoff or circuit breaker | Improvement measured against the same failure scenario |

## Risks and controls

- **Overclaiming:** use the exact phrase “application-layer request loss” for v0.1.
- **Timing flakiness:** enforce bounded objectives and publish raw values.
- **Scope expansion:** accept a feature only when it tests a named reliability
  hypothesis.
- **Unsafe public evidence:** use only synthetic traffic and independently review
  every file before publication.

The release owner may stop the release if any measurement cannot be reproduced or
any public claim exceeds the recorded evidence.
