"""Exercise 5: find the missing row, and repair only from evidence."""
from lab.stores import StoreUnavailable, apply_projection  # noqa: F401


def audit(legacy, projection):
    """Classify every expected order. Returns a dict with keys
    expected, matched, mismatched, missing, orphans and ok."""
    raise NotImplementedError("audit")


def reconcile(legacy, projection):
    """Finish projection writes that an unprojected intent says are
    owed. Returns a dict with keys repaired, already, conflicts,
    writes and unavailable."""
    raise NotImplementedError("reconcile")
