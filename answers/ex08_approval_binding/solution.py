"""Exercise 8, reference answer."""
import os
from collections import namedtuple

from lab.agent import call, request_hash

AGENT = "agent"


# region: ex08_grant
def grant(clock, tool, action, args, by, ttl):
    """Record that `by` approved this exact request, for `ttl` s."""
    if not by or by == AGENT:
        raise ValueError("only a person can approve")  # (1)
    now = clock.now()
    rh = request_hash(tool, action, args)  # (2)
    return {"id": f"apr-{rh[:6]}-{int(now)}", "request_hash": rh,
            "tool": tool, "action": action, "args": dict(args),
            "by": by, "granted_at": now, "expires_at": now + ttl}
# endregion


# region: ex08_check
Verdict = namedtuple("Verdict", "ok reasons changed")


def check(approval, tool, action, args, now, spent):
    """Does `approval` cover this request, at time `now`?"""
    reasons = []
    if approval["id"] in spent:
        reasons.append("spent")
    if now >= approval["expires_at"]:  # (1)
        reasons.append("expired")
    changed = {}
    if request_hash(tool, action, args) != approval["request_hash"]:
        reasons.append("changed")  # (2)
        was = {"tool": approval["tool"], "action": approval["action"],
               **approval["args"]}
        ask = {"tool": tool, "action": action, **args}
        for k in sorted(set(was) | set(ask)):
            if was.get(k) != ask.get(k):
                changed[k] = (was.get(k), ask.get(k))  # (3)
    return Verdict(not reasons, reasons, changed)
# endregion


# region: ex08_act
def act(log, tool, op, action, approval, clock, spent, **args):
    """Re-check the approval now, against what is about to be sent.

    Returns the receipt, or None. A refusal sends nothing.
    """
    v = check(approval, tool.name, action, args, clock.now(), spent)
    if not v.ok:
        log.record("approval_refused", op, approval=approval["id"],
                   reasons=v.reasons,
                   changed={k: list(p) for k, p in v.changed.items()},
                   request_hash=request_hash(tool.name, action, args))
        return None  # (1)
    spent.add(approval["id"])  # (2)
    log.record("approval_used", op, approval=approval["id"])
    return call(log, tool, op, action, **args)
# endregion


# region: ex08_consume
def consume(spent_dir, approval_id):
    """Spend an approval on disk in one step. False if already spent.

    Survives a restart, unlike the `spent` set that `act` keeps in
    memory.
    """
    path = os.path.join(spent_dir, approval_id)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(path, flags)  # (1)
    except FileExistsError:
        return False  # (2)
    try:
        os.fsync(fd)  # (3)
    finally:
        os.close(fd)
    return True
# endregion


# region: ex08_renew
def renew(old, args, clock, by, ttl):
    """A new approval for the changed request. Never automatic."""
    new = grant(clock, old["tool"], old["action"], args, by, ttl)
    new["renews"] = old["id"]
    return new
# endregion


# region: ex08_explain
def explain(approval, verdict):
    """Words for the person asked to approve again."""
    if verdict.ok:
        return [f"Approval {approval['id']} covers this request."]
    lines = [f"Approval {approval['id']} does not cover this request."]
    if "spent" in verdict.reasons:
        lines.append("It was already used once.")
    if "expired" in verdict.reasons:
        lines.append(f"It expired at t={approval['expires_at']:g}.")
    for k, (was, now) in verdict.changed.items():
        lines.append(f"{k} changed: {was} -> {now}")
    lines.append("Nothing was sent. Approve this request, or drop it.")
    return lines
# endregion
