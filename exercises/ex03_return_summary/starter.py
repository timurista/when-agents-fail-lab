"""Exercise 3: what the screen says after Stop."""
from collections import namedtuple
from enum import Enum

from lab import target
from lab.agent import request_hash
from lab.outcomes import Outcome
from lab.tools import ToolRejected, ToolTimeout

# return_summary() classifies with your answer to Exercise 1.
ex01 = target.load("ex01_three_outcomes")


class Stopped(Exception):
    """New work was offered after Stop."""


class Runner:
    """Drafts steps, then sends them one at a time until stopped."""

    def __init__(self, log, tools):
        self.log, self.tools = log, tools
        self.stopped = False
        self.queue = []

    def stop(self, by: str) -> None:
        """Record one stop event, however many times it is pressed."""
        raise NotImplementedError("stop")

    def submit(self, op, tool, action, **args) -> None:
        """Record an intent and queue it. Refuse once stopped."""
        raise NotImplementedError("submit")

    def run(self) -> None:
        """Send queued steps in order: sent, then the call, then the
        response or timeout. Check for Stop before each send."""
        raise NotImplementedError("run")


class Action(str, Enum):
    INSPECT = "inspect"        # read what the other side reports
    REVERSE = "reverse"        # undo a confirmed, reversible effect
    COMPENSATE = "compensate"  # a new action, with its own approval
    RECONCILE = "reconcile"    # wait for evidence, or go and get it
    RESUME = "resume"          # send it, as drafted
    DISCARD = "discard"        # drop it from the plan


CAPS = {  # what each lab tool can do after the fact
    "storefront": {"reversible": True, "lookup": True},
    "payments": {"reversible": False, "lookup": True},
    "mailer": {"reversible": False, "lookup": False},
}


def allowed(outcome: Outcome, reversible: bool) -> tuple:
    """The actions a card may offer. Nothing else is clickable."""
    raise NotImplementedError("allowed")


def evidence(events: list[dict], outcome: Outcome) -> str:
    """The event behind the outcome, in words."""
    raise NotImplementedError("evidence")


def next_step(tool: str, op: str, outcome: Outcome) -> str:
    """What would move this card, in words. Only UNKNOWN needs one."""
    raise NotImplementedError("next_step")


Card = namedtuple("Card",
                  "op tool target outcome evidence next_step actions")
Summary = namedtuple("Summary", "local cards")


def return_summary(log) -> Summary:
    """Local state once, then one card per operation."""
    raise NotImplementedError("return_summary")


class Refused(Exception):
    """An action that this card's outcome does not allow."""


def check(card: Card, action: Action) -> None:
    """Raise Refused, with a reason a person can act on."""
    raise NotImplementedError("check")
