# ADR 0001: Start with portable deterministic faults

- Status: Accepted
- Date: 2026-09-02

## Context

The flagship artifact needs repeatable evidence in pull requests and on ordinary
developer laptops. Linux `tc netem` is more faithful to packet behavior, but it
usually needs root or network-administration capabilities and produces variable
random-loss results.

## Decision

Version 0.1 uses a localhost HTTP gateway that deterministically delays or rejects
requests. The lab labels this as application-layer fault injection. A later,
separate Linux namespace experiment may use `tc netem` without changing the
portable acceptance gate.

## Consequences

- Anyone with Python 3.11+ can reproduce the core experiment.
- CI can enforce exact loss counts and bounded timing objectives.
- Results demonstrate monitoring and recovery design, not TCP retransmission or
  kernel queue behavior.
- The limitation is visible in the README, architecture, and JSON output.
