"""Replay a single synthetic message under three acknowledgement policies."""

import json
from enum import Enum
from typing import TypedDict


class Fault(str, Enum):
    CLEAN = "clean"
    BEFORE_EFFECT = "before_effect"
    AFTER_EFFECT = "after_effect"
    ACK_LOST = "ack_lost"


class Policy(str, Enum):
    ACK_FIRST = "ack_first"
    ACK_LAST = "ack_last"
    ATOMIC_MARKER = "atomic_marker"


class Attempt(TypedDict):
    fault: str
    events: list[str]


class Replay(TypedDict):
    attempts: int
    effects: int
    duplicate_effects: int
    suppressed_effects: int
    settled: bool
    trace: list[Attempt]


def simulate(policy: Policy, faults: tuple[Fault, ...]) -> Replay:
    """A fault applies to one attempted delivery of the same logical message."""
    if not isinstance(policy, Policy) or not isinstance(faults, tuple) or any(
        not isinstance(fault, Fault) for fault in faults
    ):
        raise ValueError("expected a policy and a finite tuple of modeled faults")

    trace: list[Attempt] = []
    effects = 0
    suppressed = 0
    settled = False
    for fault in faults:
        events: list[str] = []
        trace.append({"fault": fault.value, "events": events})
        if policy is Policy.ACK_FIRST:
            # This policy requires broker settlement before it can run the effect.
            if fault is Fault.ACK_LOST:
                events.append("ack_lost")
                continue
            settled = True
            events.append("ack_settled")

        if fault is Fault.BEFORE_EFFECT:
            events.append("crash_before_effect")
        else:
            # In the atomic model, a prior committed effect implies a retained marker.
            if policy is Policy.ATOMIC_MARKER and effects:
                suppressed += 1
                events.append("effect_suppressed")
            else:
                effects += 1
                events.append("effect_applied")

            if fault is Fault.AFTER_EFFECT:
                events.append("crash_after_effect")
            elif policy is not Policy.ACK_FIRST:
                if fault is Fault.ACK_LOST:
                    events.append("ack_lost")
                else:
                    settled = True
                    events.append("ack_settled")

        if settled:
            break

    return {
        "attempts": len(trace),
        "effects": effects,
        "duplicate_effects": max(0, effects - 1),
        "suppressed_effects": suppressed,
        "settled": settled,
        "trace": trace,
    }


SCENARIOS = {
    "clean": (Fault.CLEAN,),
    "crash_before_effect": (Fault.BEFORE_EFFECT, Fault.CLEAN),
    "crash_after_effect": (Fault.AFTER_EFFECT, Fault.CLEAN),
    "lost_ack": (Fault.ACK_LOST, Fault.CLEAN),
    "budget_exhausted": (Fault.ACK_LOST, Fault.ACK_LOST),
}


def worked_results() -> dict[str, dict[str, Replay]]:
    """Return the same ordered scenario and policy traces on every run."""
    return {
        scenario: {policy.value: simulate(policy, faults) for policy in Policy}
        for scenario, faults in SCENARIOS.items()
    }


if __name__ == "__main__":
    print(json.dumps(worked_results(), indent=2))
