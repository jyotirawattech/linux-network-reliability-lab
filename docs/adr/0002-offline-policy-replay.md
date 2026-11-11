# ADR 0002: Compare detection policies by replaying synthetic observations

Decision recorded: 11 November 2026. A public revision and its read-back receipt,
rather than this decision date, establish publication.

## Context

The lab already demonstrates service faults and checks its 2/2 threshold state
machine. One successful network experiment does not show why that threshold is
chosen or how a different threshold changes missed short outages and noise.

## Decision

Add a dependency-free offline replay that injects booleans and sample-start times
into the existing monitor. Use 1/1 as the named baseline and compare 2/2 and 3/3 on four
small, fully disclosed traces. Warm every policy to `HEALTHY` before the trace and
report startup separately. Keep source, tests, command and worked output together.

## Consequences and alternatives

- Deterministic input times make boundary/reset behavior repeatable without
  localhost scheduling variability. They cannot establish wall-clock speedup,
  TCP behavior, production health truth or a production SLO.
- Higher thresholds suppress these isolated noise events but delay sustained
  outage detection and can miss a short outage. No threshold is universally better.
- The helper bounds inputs and uses an injected probe; it never loads user files,
  executes commands, opens a network connection or changes the live monitor default.
- A second independently implemented monitor would risk comparing different
  semantics. A privileged network-emulation extension would answer another question
  and remains separate planned work.

Validation: unit tests exercise fixed traces, reset boundaries, missing restoration,
already-degraded episodes, irregular timestamps, invalid input and the no-network
boundary. The existing localhost tests remain required. Exact command results and
the publication decision belong to the task's actual validation/release receipts.
