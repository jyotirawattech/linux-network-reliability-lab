"""Offline replay of the real monitor against explicitly labelled synthetic input.

Times are input sample-start times, not measurements of elapsed execution time.
The injected probe never opens a socket, and no real service truth is inferred.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .lab import MonitorConfig, ReliabilityMonitor


MAX_SAMPLES = 10_000
MAX_THRESHOLD = 1_000
MAX_TIME_MS = 86_400_000


@dataclass(frozen=True)
class Observation:
    at_ms: int
    probe_ok: bool
    service_unavailable: bool = False


def _positive_integer(value: int, name: str, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum}")


def replay_policy(
    samples: list[Observation] | tuple[Observation, ...], config: MonitorConfig
) -> dict[str, object]:
    """Replay one bounded trace; warm up to HEALTHY before its first observation.

    Outage labels are synthetic truth supplied by the caller. This model permits
    failed probes while the service is labelled available, but not successful
    probes while it is labelled unavailable. It does not model false-healthy probes.

    ``noise_degradations`` counts DEGRADED transitions on available-labelled
    samples, including a failure streak that began during a preceding outage.
    Outage detection is attributed only inside that labelled outage window.
    Its recovery status ``not_needed`` means no detection was attributed there,
    not that the monitor cannot degrade after the labelled restoration.
    """
    if not isinstance(config, MonitorConfig):
        raise ValueError("config must be a MonitorConfig")
    for name in ("failures_to_degrade", "successes_to_recover"):
        _positive_integer(getattr(config, name), name, MAX_THRESHOLD)
    for name in ("poll_interval_ms", "timeout_ms"):
        _positive_integer(getattr(config, name), name, 60_000)
    if not isinstance(samples, (list, tuple)) or not 1 <= len(samples) <= MAX_SAMPLES:
        raise ValueError(f"samples must be a nonempty list or tuple of at most {MAX_SAMPLES}")
    previous_time = -1
    for sample in samples:
        if not isinstance(sample, Observation):
            raise ValueError("each sample must be an Observation")
        if type(sample.at_ms) is not int or not previous_time < sample.at_ms <= MAX_TIME_MS:
            raise ValueError("sample times must be strictly increasing integer milliseconds within one day")
        if type(sample.probe_ok) is not bool or type(sample.service_unavailable) is not bool:
            raise ValueError("probe_ok and service_unavailable must be bool values")
        if sample.service_unavailable and sample.probe_ok:
            raise ValueError("this model requires a failed probe during a labelled outage")
        previous_time = sample.at_ms

    warmup_count = config.successes_to_recover
    outcomes = iter([True] * warmup_count + [sample.probe_ok for sample in samples])
    monitor = ReliabilityMonitor(
        "synthetic://policy-replay", config, probe=lambda _url, _timeout: next(outcomes)
    )
    for tick in range(warmup_count):
        monitor.sample_once(now=-(warmup_count - tick) * config.poll_interval_ms / 1000)

    states: list[str] = []
    events: list[dict[str, object]] = []
    noise_degradations = 0
    for sample in samples:
        event = monitor.sample_once(now=sample.at_ms / 1000)
        states.append(monitor.state)
        if event is not None:
            events.append({"previous": event.previous, "current": event.current, "at_ms": sample.at_ms})
            if event.current == "DEGRADED" and not sample.service_unavailable:
                # Classification by the transition's sample label, not a claim
                # about the origin of the whole consecutive-failure streak.
                noise_degradations += 1

    # Every outage and recovery window is disjoint: all searches together are O(N).
    intervals: list[tuple[int, int]] = []
    index = 0
    while index < len(samples):
        if not samples[index].service_unavailable:
            index += 1
            continue
        start = index
        while index < len(samples) and samples[index].service_unavailable:
            index += 1
        intervals.append((start, index))

    outages: list[dict[str, object]] = []
    for number, (start, end) in enumerate(intervals):
        prior_state = states[start - 1] if start else "HEALTHY"
        detected = next((i for i in range(start, end) if states[i] == "DEGRADED"), None)
        already_degraded = prior_state == "DEGRADED"
        detection_status = "already_degraded" if already_degraded else "detected" if detected is not None else "not_detected"
        detection_delay = samples[detected].at_ms - samples[start].at_ms if detected is not None and not already_degraded else None
        window_end = intervals[number + 1][0] if number + 1 < len(intervals) else len(samples)
        recovered = next((i for i in range(end, window_end) if states[i] == "HEALTHY"), None)
        recovery_delay = None
        if end == len(samples):
            recovery_status = "restoration_not_observed"
        elif detected is None:
            # Attribution is local to the outage window. A late degradation can
            # still appear in the complete transition list and noise count.
            recovery_status = "not_needed"
        elif recovered is None:
            recovery_status = "not_recovered_in_window"
        else:
            recovery_status = "recovered"
            recovery_delay = samples[recovered].at_ms - samples[end].at_ms
        outages.append({
            "start_ms": samples[start].at_ms,
            "restoration_ms": samples[end].at_ms if end < len(samples) else None,
            "outage_samples": end - start,
            "detection_status": detection_status,
            "detection_delay_ms": detection_delay,
            "recovery_status": recovery_status,
            "recovery_delay_ms": recovery_delay,
        })

    return {
        "failures_to_degrade": config.failures_to_degrade,
        "successes_to_recover": config.successes_to_recover,
        "sample_count": len(samples),
        "noise_degradations": noise_degradations,
        "transition_count": len(events),
        "transitions": events,
        "outages": outages,
    }


def run_policy_comparison() -> dict[str, object]:
    """Return a deterministic worked example; the only probe data are below."""
    interval_ms = 50
    traces = {
        "isolated_probe_glitches": [(True, False), (False, False), (True, False), (True, False), (False, False), (True, False)],
        "sustained_outage": [(True, False)] * 2 + [(False, True)] * 4 + [(True, False)] * 4,
        "one_sample_outage": [(True, False)] * 2 + [(False, True)] + [(True, False)] * 4,
        "noisy_restoration": [(True, False)] * 2 + [(False, True)] * 4 + [(True, False), (False, False)] + [(True, False)] * 3,
    }
    cases = []
    for name, trace in traces.items():
        samples = [Observation(i * interval_ms, ok, unavailable) for i, (ok, unavailable) in enumerate(trace)]
        cases.append({
            "name": name,
            "samples": [asdict(sample) for sample in samples],
            "policies": [replay_policy(samples, MonitorConfig(failures_to_degrade=n, successes_to_recover=n)) for n in (1, 2, 3)],
        })
    return {
        "evidence_type": "deterministic_synthetic_sample_time_model",
        "baseline": "one failure to degrade / one success to recover (1/1)",
        "sample_interval_ms": interval_ms,
        "warmup": "each policy starts HEALTHY; warmup is excluded from reported transitions",
        "benchmark": {"paired_wall_clock": "not_run", "measured_speedup": None},
        "cases": cases,
    }
