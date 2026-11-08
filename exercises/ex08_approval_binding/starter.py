"""Exercise 8: bind an approval to one exact request."""
from collections import namedtuple

from lab.agent import call, request_hash

AGENT = "agent"
Verdict = namedtuple("Verdict", "ok reasons changed")


def grant(clock, tool, action, args, by, ttl):
    """Record that `by` approved this exact request, for `ttl` s.

    Returns a dict with at least: id, request_hash, tool, action,
    args, by, granted_at, expires_at. Raises ValueError when `by` is
    empty or is AGENT.
    """
    raise NotImplementedError("grant")


def check(approval, tool, action, args, now, spent):
    """Does `approval` cover this request, at time `now`?

    Returns Verdict(ok, reasons, changed). reasons is a list drawn
    from "spent", "expired", "changed". changed maps each field that
    differs (tool, action, or an arg name) to (approved, asked).
    """
    raise NotImplementedError("check")


def act(log, tool, op, action, approval, clock, spent, **args):
    """Re-check the approval now, against what is about to be sent.

    On a refusal, record an "approval_refused" event and send nothing.
    Otherwise mark the approval spent, record "approval_used", and
    send through lab.agent.call. Returns the receipt, or None.
    """
    raise NotImplementedError("act")


def consume(spent_dir, approval_id):
    """Spend an approval on disk, in one step that checks and records.

    Create a marker file named `approval_id` in `spent_dir` only if
    it doesn't exist yet, and flush it to disk. Returns True for the
    call that created it and False for every call after, including
    calls made after a restart.
    """
    raise NotImplementedError("consume")


def renew(old, args, clock, by, ttl):
    """A new approval for the changed request, with "renews": old id."""
    raise NotImplementedError("renew")


def explain(approval, verdict):
    """Lines of text for the person asked to approve again."""
    raise NotImplementedError("explain")
