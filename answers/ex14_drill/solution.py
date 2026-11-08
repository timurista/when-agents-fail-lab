"""Exercise 14, reference answer: one pass through the drill."""
from lab.drill import CAPABILITIES, miss_proves_failure
from lab.outcomes import Outcome


def classify(events: list[dict]) -> Outcome:
    """Chapter 1's rules, repeated so this file stands alone."""
    for e in events:
        if e["kind"] == "response" and e["ok"]:
            return Outcome.CONFIRMED
        if e["kind"] == "status" and e["found"]:
            return Outcome.CONFIRMED
    for e in reversed(events):
        if e["kind"] == "decision":
            if not e.get("reason"):
                raise ValueError("a decision needs a reason")
            return Outcome(e["outcome"])
        if e["kind"] == "response" and not e["ok"]:
            return Outcome.FAILED
        if (e["kind"] == "status" and not e["found"]
                and e.get("authoritative")):
            return Outcome.FAILED
        if e["kind"] == "cancel_ack":
            return Outcome.CANCELED
    if not any(e["kind"] == "sent" for e in events):
        return Outcome.NEVER_SENT
    return Outcome.UNKNOWN


def outcomes(log) -> dict:
    return {op: classify(log.for_op(op)) for op in log.ops()}


def intent_of(log, op) -> dict:
    return next(e for e in log.for_op(op) if e["kind"] == "intent")


# region: ex14_reconcile
def reconcile(incident) -> dict:
    """Ask each tool about its unknowns, record answers, reclassify."""
    log = incident.log
    for op, outcome in outcomes(log).items():
        if outcome is not Outcome.UNKNOWN:
            continue
        intent = intent_of(log, op)
        tool = incident.tools[intent["tool"]]
        cap = CAPABILITIES[tool.name]
        if cap["lookup"] is None:
            continue  # (1)
        if cap["lookup"] == "key":
            receipt = tool.lookup(intent["args"]["key"])
        else:
            receipt = tool.status(op)
        log.record("status", op, found=receipt is not None,
                   receipt=receipt,
                   authoritative=miss_proves_failure(cap))  # (2)
    return outcomes(log)
# endregion


# region: ex14_decide
def decide(incident, after: dict) -> dict:
    """One action per operation, from its outcome and its tool."""
    plan = {}
    for op, outcome in after.items():
        events = incident.log.for_op(op)
        cap = CAPABILITIES[intent_of(incident.log, op)["tool"]]
        rejected = any(e["kind"] == "response" and not e["ok"]
                       for e in events)
        if outcome is Outcome.CONFIRMED:
            plan[op] = "keep"
        elif outcome is Outcome.NEVER_SENT:
            plan[op] = "resume"  # (1)
        elif cap["key"] and not rejected:
            plan[op] = "resend"  # (2)
        else:
            plan[op] = "escalate"  # (3)
    return plan
# endregion


# region: ex14_messages
SAYS = {
    "keep": "Next: keep it; nothing to do.",
    "resend": "Next: resend with the same key.",
    "resume": "Next: resume after its refund is confirmed.",
    "escalate": "Next: escalate to a person. Do not resend.",
}


def write_messages(after: dict, plan: dict) -> dict:
    """One line per operation: what is known, then what happens next."""
    return {op: f"{op}: {outcome.value.replace('_', ' ')}. "
                f"{SAYS[plan[op]]}" for op, outcome in after.items()}


def headline(after: dict) -> str:
    counts = {}
    for outcome in after.values():
        name = outcome.value.replace("_", " ")
        counts[name] = counts.get(name, 0) + 1
    parts = ", ".join(f"{n} {name}" for name, n in counts.items())
    return f"Returns run stopped: {parts}."
# endregion


# region: ex14_handoff
def hand_off(incident, after: dict, plan: dict) -> dict:
    """The note the next owner reads first."""
    unknown = sorted(op for op, o in after.items()
                     if o is Outcome.UNKNOWN)
    stale = sorted(op for op in incident.claims
                   if after[op] is not Outcome.CONFIRMED)  # (1)
    order = ["resend", "resume", "escalate", "wait"]  # (2)
    first = min((op for op in plan if plan[op] in order),
                key=lambda op: order.index(plan[op]))
    return {
        "settled": sorted(op for op in after if op not in unknown),
        "unknown": unknown,
        "stale_claims": stale,
        "next_action": {"op": first, "action": plan[first]},
        "do_not": [f"do not resend {op}: nobody knows if it landed"
                   for op in unknown if plan[op] != "resend"],
    }
# endregion


# region: ex14_run
def run_drill(incident) -> dict:
    before = outcomes(incident.log)  # (1)
    after = reconcile(incident)
    plan = decide(incident, after)
    return {
        "before": {op: o.value for op, o in before.items()},
        "after": {op: o.value for op, o in after.items()},
        "plan": plan,
        "messages": write_messages(after, plan),
        "headline": headline(after),
        "handoff": hand_off(incident, after, plan),
    }
# endregion
