"""Exercise 4, reference answer."""
from lab.agent import call
from lab.outcomes import Outcome


# region: ex04_capabilities
# What each lab tool lets a caller do after an unanswered call.
CAPABILITIES = {
    # key:         a repeat with the same key returns the first receipt
    # lookup:      we can ask afterwards whether it happened
    # repeat_safe: applying it twice leaves the same state as once
    "payments":   {"key": True,  "lookup": True,  "repeat_safe": False},
    "storefront": {"key": False, "lookup": True,  "repeat_safe": True},
    "mailer":     {"key": False, "lookup": False, "repeat_safe": False},
}


def may_resend(tool) -> bool:
    """True when sending again cannot double the effect."""
    cap = CAPABILITIES[tool.name]
    return cap["key"] or cap["repeat_safe"]
# endregion


# region: ex04_backoff
def backoff(attempt: int, base: float = 1.0, cap: float = 30.0):
    """Seconds to wait before attempt `attempt` (1 is the first
    retry). Doubles each time, never above `cap`. No randomness, so
    a test can predict every delay."""
    return min(cap, base * 2 ** (attempt - 1))
# endregion


# region: ex04_ask
def ask(log, tool, op, args):
    """Ask the tool whether `op` happened. Returns the receipt, or
    None for "not found" and for "this tool can't be asked"."""
    cap = CAPABILITIES[tool.name]
    if not cap["lookup"]:
        return None
    if cap["key"]:
        receipt = tool.lookup(args["key"])
    else:
        receipt = tool.status(op)
    log.record("status", op, found=receipt is not None,
               receipt=receipt, authoritative=False)
    return receipt
# endregion


# region: ex04_retry
def retry_safely(log, tool, op, action, args, clock, attempts=3):
    """Send, and resolve an unanswered send by asking, not guessing.

    Returns (outcome, receipt). Resends only when the tool would
    dedupe the repeat or the repeat is harmless. Otherwise it
    records an escalation and returns UNKNOWN.
    """
    if CAPABILITIES[tool.name]["key"] and not args.get("key"):
        raise ValueError("a keyed tool needs a key that outlives "
                         "the attempt")  # (1)
    for attempt in range(attempts):
        if attempt:
            clock.advance(backoff(attempt))  # (2)
            receipt = ask(log, tool, op, args)
            if receipt is not None:
                return Outcome.CONFIRMED, receipt  # (3)
            if not may_resend(tool):
                return escalate(log, op, "no key, no lookup, "
                                "and a repeat is not harmless")
        receipt = call(log, tool, op, action, **args)
        if receipt is not None:
            return Outcome.CONFIRMED, receipt
        if log.for_op(op)[-1]["kind"] == "response":  # (4)
            if attempt == 0:
                return Outcome.FAILED, None
            return escalate(log, op, "a retry was rejected; an "
                            "earlier attempt may still apply")
    return escalate(log, op, f"no answer after {attempts} attempts")


def escalate(log, op, reason):
    log.record("escalate", op, reason=reason)
    return Outcome.UNKNOWN, None
# endregion
