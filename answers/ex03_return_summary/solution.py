"""Exercise 3, reference answer."""
from collections import namedtuple
from enum import Enum

from lab import target
from lab.agent import request_hash
from lab.outcomes import Outcome
from lab.tools import ToolRejected, ToolTimeout

# Classification is Exercise 1's job. With LAB_TARGET=solution this
# loads the reference answer; otherwise it loads your own.
ex01 = target.load("ex01_three_outcomes")


# region: ex03_runner
class Stopped(Exception):
    """New work was offered after Stop."""


class Runner:
    """Drafts steps, then sends them one at a time until stopped."""

    def __init__(self, log, tools):
        self.log, self.tools = log, tools
        self.stopped = False
        self.queue = []

    def stop(self, by: str) -> None:
        if not self.stopped:
            self.stopped = True
            self.log.record("stop", None, by=by)

    def submit(self, op, tool, action, **args) -> None:
        if self.stopped:  # (1)
            raise Stopped(f"stopped: {op} was not accepted")
        self.log.record("intent", op, tool=tool, action=action,
                        args=args,
                        request_hash=request_hash(tool, action, args))
        self.queue.append((op, tool, action, args))

    def run(self) -> None:
        while self.queue and not self.stopped:  # (2)
            op, tool, action, args = self.queue.pop(0)
            self.log.record("sent", op)
            try:
                receipt = getattr(self.tools[tool], action)(op, **args)
            except ToolTimeout:
                self.log.record("timeout", op)
            except ToolRejected as err:
                self.log.record("response", op, ok=False,
                                error=str(err))
            else:
                self.log.record("response", op, ok=True,
                                receipt=receipt)
# endregion


# region: ex03_actions
class Action(str, Enum):
    INSPECT = "inspect"        # read what the other side reports
    REVERSE = "reverse"        # undo a confirmed, reversible effect
    COMPENSATE = "compensate"  # a new action, with its own approval
    RECONCILE = "reconcile"    # wait for evidence, or go and get it
    RESUME = "resume"          # send it, as drafted
    DISCARD = "discard"        # drop it from the plan


A = Action
OPEN = {
    Outcome.FAILED: (A.INSPECT, A.DISCARD),
    Outcome.UNKNOWN: (A.RECONCILE,),
    Outcome.CANCELED: (A.INSPECT, A.RESUME),
    Outcome.NEVER_SENT: (A.DISCARD, A.RESUME),
}


def allowed(outcome: Outcome, reversible: bool) -> tuple:
    """The actions a card may offer. Nothing else is clickable."""
    if outcome == Outcome.CONFIRMED:
        return (A.INSPECT, A.REVERSE if reversible else A.COMPENSATE)
    return OPEN[outcome]
# endregion


# region: ex03_caps
CAPS = {  # what each lab tool can do after the fact
    "storefront": {"reversible": True, "lookup": True},
    "payments": {"reversible": False, "lookup": True},
    "mailer": {"reversible": False, "lookup": False},
}
# endregion

RECEIPT_KEYS = ("receipt", "refund", "message_id")
TARGET_KEYS = ("sku", "order", "to")


def _receipt_id(receipt: dict) -> str:
    return next((receipt[k] for k in RECEIPT_KEYS if k in receipt), "?")


# region: ex03_evidence
def evidence(events: list[dict], outcome: Outcome) -> str:
    """The event behind the outcome, in words."""
    if outcome == Outcome.UNKNOWN:
        return "sent; no receipt, rejection or cancel ack"
    if outcome == Outcome.NEVER_SENT:
        return "drafted; never sent"
    for e in events:  # positive evidence first, as classify does
        if e["kind"] == "response" and e["ok"]:
            return f"receipt {_receipt_id(e['receipt'])}"
        if e["kind"] == "status" and e["found"]:
            return f"lookup found {_receipt_id(e['receipt'])}"
    for e in reversed(events):
        if e["kind"] == "decision":
            return f"decided by {e.get('by', '?')}: {e['reason']}"
        if e["kind"] == "response":
            return f"rejected: {e['error']}"
        if e["kind"] == "status":
            return "authoritative lookup: not applied"
        if e["kind"] == "cancel_ack":
            return "cancel acknowledged before applying"
    return "?"


def next_step(tool: str, op: str, outcome: Outcome) -> str:
    """What would move this card, in words. Only UNKNOWN needs one."""
    if outcome != Outcome.UNKNOWN:
        return "none needed"
    if CAPS[tool]["lookup"]:
        return f"ask {tool} for the status of {op}; do not resend"
    return f"{tool} has no lookup: a person must check; do not resend"
# endregion


# region: ex03_summary
Card = namedtuple("Card",
                  "op tool target outcome evidence next_step actions")
Summary = namedtuple("Summary", "local cards")


def card(op: str, events: list[dict], outcome: Outcome) -> Card:
    intent = next(e for e in events if e["kind"] == "intent")
    tool, args = intent["tool"], intent.get("args", {})
    what = next((args[k] for k in TARGET_KEYS if k in args), op)
    return Card(op, tool, what, outcome, evidence(events, outcome),
                next_step(tool, op, outcome),
                allowed(outcome, CAPS[tool]["reversible"]))


def return_summary(log) -> Summary:
    """Local state once, then one card per operation."""
    outcomes = ex01.summarize(log)
    stopped = any(e["kind"] == "stop" for e in log.events)
    cards = [card(op, log.for_op(op), outcomes[op])
             for op in log.ops()]
    return Summary("stopped" if stopped else "running", cards)
# endregion


# region: ex03_check
class Refused(Exception):
    """An action that this card's outcome does not allow."""


def check(c: Card, action: Action) -> None:
    """Raise Refused, with a reason a person can act on."""
    if action in c.actions:
        return
    if c.outcome == Outcome.UNKNOWN:  # (1)
        raise Refused(f"nothing settled to {action.value} yet. "
                      f"Next: {c.next_step}")
    if action == A.REVERSE and c.outcome == Outcome.CONFIRMED:
        raise Refused(f"{c.tool} can't reverse this. Removing it is "
                      "compensation: a new action, own approval")
    raise Refused(f"{action.value} is not open when the outcome is "
                  f"{c.outcome.value}")
# endregion
