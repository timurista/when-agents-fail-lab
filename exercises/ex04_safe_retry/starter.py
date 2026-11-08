"""Exercise 4: retry a tool call without doubling its effect."""
from lab.agent import call  # noqa: F401  (you will need it)
from lab.outcomes import Outcome  # noqa: F401

# What each lab tool lets a caller do after an unanswered call.
CAPABILITIES = {
    # key:         a repeat with the same key returns the first receipt
    # lookup:      we can ask afterwards whether it happened
    # repeat_safe: applying it twice leaves the same state as once
    "payments":   {"key": True,  "lookup": True,  "repeat_safe": False},
    "storefront": {"key": False, "lookup": True,  "repeat_safe": True},
    "mailer":     {"key": False, "lookup": False, "repeat_safe": False},
}


def backoff(attempt: int, base: float = 1.0, cap: float = 30.0):
    """Seconds to wait before retry number `attempt` (1, 2, ...)."""
    raise NotImplementedError("backoff")


def ask(log, tool, op, args):
    """Ask the tool whether `op` happened; record a status event.
    Returns the receipt, or None."""
    raise NotImplementedError("ask")


def retry_safely(log, tool, op, action, args, clock, attempts=3):
    """Returns (outcome, receipt). See README.md for the rules."""
    raise NotImplementedError("retry_safely")
