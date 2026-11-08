"""Exercise 1, reference answer."""
from lab.outcomes import Outcome


# region: classify
def classify(events: list[dict]) -> Outcome:
    """The outcome of one operation, from its events in order."""
    for e in events:  # (1)
        if e["kind"] == "response" and e["ok"]:
            return Outcome.CONFIRMED
        if e["kind"] == "status" and e["found"]:
            return Outcome.CONFIRMED
    for e in reversed(events):  # (2)
        if e["kind"] == "decision":
            if not e.get("reason"):
                raise ValueError("a decision needs a reason")
            return Outcome(e["outcome"])
        if e["kind"] == "response" and not e["ok"]:
            return Outcome.FAILED
        if (e["kind"] == "status" and not e["found"]
                and e.get("authoritative")):  # (3)
            return Outcome.FAILED
        if e["kind"] == "cancel_ack":
            return Outcome.CANCELED
    if not any(e["kind"] == "sent" for e in events):
        return Outcome.NEVER_SENT  # (4)
    return Outcome.UNKNOWN  # (5)
# endregion


# region: summarize
def summarize(log) -> dict:
    """{op: Outcome} for every operation in the log."""
    return {op: classify(log.for_op(op)) for op in log.ops()}
# endregion
