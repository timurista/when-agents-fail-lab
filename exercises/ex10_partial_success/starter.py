"""Exercise 10: plan the way back from a partly finished workflow."""
from lab.agent import call, request_hash  # noqa: F401
from lab.compensation import (CAPABILITIES, receipt_of,  # noqa: F401
                              reference_classify)
from lab.outcomes import Outcome  # noqa: F401

classify = reference_classify()


def plan_step(step, outcome, receipt):
    """A plan item for one step: a dict with op, tool, outcome, do,
    why, receipt, request and needs_approval. `do` is one of
    "reverse", "compensate", "wait" or "leave"."""
    raise NotImplementedError("plan_step")


def plan_recovery(log, steps):
    """One plan item per step the log touched, newest first. Steps an
    earlier pass already reversed or compensated are not redone."""
    raise NotImplementedError("plan_recovery")


def apply_plan(plan, tools, log, approvals=None):
    """Carry out a plan; return {op: what happened}. `approvals` maps
    an op to the request_hash of the compensation someone approved."""
    raise NotImplementedError("apply_plan")
