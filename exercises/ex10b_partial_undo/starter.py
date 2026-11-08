"""Exercise 10b: undo a run, but keep what surviving work needs."""
from lab.undo_workspace import (delete, fingerprint,  # noqa: F401
                                object_by_object, resolve)


def plan(ws, run):
    """A plan dict: against (the workspace fingerprint), remove and keep
    (lists of (id, why)), unresolved (list of (holder, name, [ids])) and
    error (None, or why nothing can be planned). See README.md."""
    raise NotImplementedError("plan")


def execute(p, ws):
    """Carry out a plan; return {"removed": [ids], "refused": None or
    why}."""
    raise NotImplementedError("execute")


def report(p):
    """The plan as lines a person reads: one per remove, keep and
    unresolved reference."""
    raise NotImplementedError("report")
