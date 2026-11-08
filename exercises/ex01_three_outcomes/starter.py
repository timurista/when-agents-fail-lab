"""Exercise 1: classify each operation in a run log."""
from lab.outcomes import Outcome


def classify(events: list[dict]) -> Outcome:
    """The outcome of one operation, from its events in order."""
    raise NotImplementedError("classify")


def summarize(log) -> dict:
    """{op: Outcome} for every operation in the log."""
    raise NotImplementedError("summarize")
