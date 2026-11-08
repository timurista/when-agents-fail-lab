"""Exercise 14: run the recovery drill on the stopped returns run.

`incident` is what lab.drill.stage() returns: incident.log (a RunLog),
incident.tools ({"storefront": ..., "payments": ..., "mailer": ...})
and incident.claims ({op: what the agent's final message said}).
Read lab/drill.py for CAPABILITIES and ACTIONS before you start.
"""
from lab.drill import CAPABILITIES, miss_proves_failure  # noqa: F401
from lab.outcomes import Outcome  # noqa: F401


def classify(events: list[dict]) -> Outcome:
    """Chapter 1's rules. Paste your Exercise 1 answer or rewrite it."""
    raise NotImplementedError("classify")


def reconcile(incident) -> dict:
    """Ask each tool that can answer about its UNKNOWN operations.
    Record each answer as a `status` event with `found`, `receipt` and
    `authoritative` (True only when a miss proves the effect will never
    apply: see miss_proves_failure). Return {op: Outcome} for every
    operation."""
    raise NotImplementedError("reconcile")


def decide(incident, after: dict) -> dict:
    """{op: action}, one of the names in lab.drill.ACTIONS."""
    raise NotImplementedError("decide")


def write_messages(after: dict, plan: dict) -> dict:
    """{op: one line for the operator}: the outcome, then the next
    step, using the action's name."""
    raise NotImplementedError("write_messages")


def headline(after: dict) -> str:
    """One line for the whole run that doesn't hide the unknowns."""
    raise NotImplementedError("headline")


def hand_off(incident, after: dict, plan: dict) -> dict:
    """{"settled", "unknown", "stale_claims", "next_action", "do_not"}.
    next_action is {"op": ..., "action": ...}."""
    raise NotImplementedError("hand_off")


def run_drill(incident) -> dict:
    """The drill report: before, after, plan, messages, headline and
    handoff. Outcomes are written as their string values. A team drill
    adds "assists": the help the scribe recorded (empty if none)."""
    raise NotImplementedError("run_drill")
