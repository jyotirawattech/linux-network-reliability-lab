# How many failed probes should trigger an alert?

A single-sample monitor reacts quickly, but an isolated failed probe can switch it
to `DEGRADED`. Requiring a streak filters that noise and delays detection. This
offline experiment makes both consequences visible using the lab's **actual
`ReliabilityMonitor.sample_once` state machine**, rather than a second implementation.

```bash
make compare-policies
```

This prints deterministic JSON, opens no sockets, starts no services and requires
no additional packages. The [worked output](../results/detection-policy-example.json)
contains the complete labelled inputs and results. `make verify` also runs this
command after the existing tests, coverage and localhost acceptance experiment.
A degradation event is a monitor state change, not a sent notification.

## Worked result

The named baseline is **1/1**: one failed probe declares degradation and one
successful probe restores health. Compare it with **2/2** and **3/3** on exactly the
same observations. Every policy is first warmed to `HEALTHY`; startup transitions
are excluded from the counts. The worked traces use supplied sample-start times
0 ms, 50 ms, 100 ms, … . These are **model inputs**, not elapsed execution measurements.

- Two isolated failed probes while synthetic truth says the service is available
  produce **2 degradation events and 4 state transitions** under 1/1. Both 2/2 and 3/3
  produce **0** on this trace. That is two fewer noise-induced degradation events
  in this example, not a general false-alert reduction guarantee.
- A four-sample outage is detected after **0 ms, 50 ms, 100 ms** under 1/1,2/2,3/3
  respectively, measured from its first labelled failed sample. Restoration is
  first reported healthy after the same respective delays when subsequent probes
  all succeed. The policy that filters noise is not faster here.
- A one-sample outage is detected by 1/1 and **not detected** by 2/2 or 3/3. Filtering a
  real short outage is a cost, not a correctness improvement.
- After an outage, a successful probe followed by another failed probe resets the
  recovery streak. First-healthy restoration delays become **0 ms, 150 ms, 200 ms**.
  The baseline also produces an extra noise-induced degradation after that first
  restoration. A first-healthy event does not guarantee health remains stable.

## Read the metrics operationally

`noise_degradations` counts transitions to `DEGRADED` **on a sample labelled
available**. It does not classify the cause of the entire failure streak. A streak
can start in a labelled outage and reach the threshold after labelled restoration.
`detection_status` attributes detection only within that outage's labelled samples.
`recovery_status: not_needed` means no detection was attributed to that window;
it does **not** mean the monitor never degrades after restoration. Inspect the
complete transition list alongside these window-local summaries.

For example, replay 2/2 with these `(time_ms, probe_ok, service_unavailable)` inputs:

```text
(0, false, true), (50, false, false), (100, true, false), (150, true, false)
```

The actual monitor degrades at 50 ms and returns healthy at 150 ms. The failed probe
at 50 ms continues the streak started during the outage, but its sample is labelled
available, so `noise_degradations` is 1. The one-sample labelled outage remains
`not_detected`, with `recovery_status: not_needed` and null attributed delays.
Those summaries do not erase the later monitor transitions. A regression test
asserts both the full transition sequence and the attribution fields.

## Why the difference?

For consecutive failures on a uniform input grid with spacing Δ, a threshold F
needs F failed samples and changes state at the Fth sample. Relative to the first
failed sample, this is `(F−1)Δ` if the outage lasts long enough. A success resets the
failure streak. Recovery uses the analogous success threshold and resets on any
failed probe. For Δ = 50 ms, increasing the threshold from 1 to 2 adds 50 ms of model delay;
increasing it to 3 adds 100 ms. No timed speedup or memory-saving benchmark was run.

For N observations and recovery warmup threshold R, one replay does O(N+R) work and
stores O(N+R) data, including observations, state/event history and warmup outcomes.
Comparing P policies costs O(PN+ΣR) work; all three threshold choices have the same
growth order. Their useful difference is the state-change decision, not an
established computational performance advantage. Output storage can be O(PN).

## Measurement and input boundaries

The replay calls `sample_once(now=...)` with supplied timestamps and an injected
boolean probe. It does not call `wait_for`, sleep, perform HTTP requests, model
probe duration/timeout, or measure a live network. The live monitor's pause occurs
after each completed probe, so real start-to-start times need not be 50 ms. This
output is separate from the existing dated localhost experiment results.

`service_unavailable` is caller-supplied synthetic truth. Available service may
have a failed probe, representing health-check noise. A labelled outage must have
a failed probe; false-healthy probes are outside this version's model. Do not
infer true service state from arbitrary production probe logs using this helper.
For an outage beginning while already degraded, output says `already_degraded`
and does not manufacture a fresh detection delay. An outage or recovery that
extends beyond the trace keeps the relevant outcome unknown/not observed.

The function accepts 1–10,000 observations with strictly increasing integer
millisecond times within one day. Thresholds must be integers 1–1,000; interval and
timeout settings must be integers 1–60,000 ms. Booleans are rejected as numeric input.
Bounds constrain accidental allocation/work. No input is interpreted as code,
filename, URL, command or credential.

## Decision

Keep 2/2 as the live lab default. The isolated-noise trace explains its purpose while
the short-outage trace exposes the cost. This experiment supplies a reproducible
decision aid, not a production tuning recommendation or universal winner. For a
real system, choose an acceptable outage duration and false-alert cost, establish
actual probe timing and failure modes, then validate candidate policies on
representative evidence. See [ADR 0002](../adr/0002-offline-policy-replay.md).
