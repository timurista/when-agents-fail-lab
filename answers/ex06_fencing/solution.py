"""Exercise 6, reference answer."""
from lab.agent import call
from lab.leases import StaleToken


def no_pause(where: str) -> None:
    """The default: the worker runs straight through."""


# region: ex06_naive
def naive_update(leases, catalog, lease, sku, text, pause=no_pause):
    """The control. The worker checks its own lease, then writes."""
    if not leases.is_current(lease):
        return "lost_lease"
    pause("before_write")  # (1)
    catalog[sku] = text  # (2)
    return "written"
# endregion


# region: ex06_fenced_update
def fenced_update(store, lease, sku, text, pause=no_pause):
    """Write with the lease's token. The store decides, not us."""
    pause("before_write")
    try:
        store.write(sku, text, lease.token)
    except StaleToken:
        return "fenced"
    return "written"
# endregion


# region: ex06_send_once
def send_once(log, leases, claims, lease, mailer, op, to, subject,
              pause=no_pause):
    """Send one email for `op` through a tool that can't check tokens.

    Returns "sent", "no_receipt", "lost_lease" or "escalate".
    """
    if not leases.is_current(lease):  # (1)
        log.record("fenced", op, holder=lease.holder,
                   token=lease.token, reason="lease not current")
        return "lost_lease"
    pause("after_check")
    earlier = claims.read(op)
    if earlier is not None and earlier["token"] < lease.token:
        log.record("escalate", op, holder=lease.holder,  # (2)
                   reason=f"claimed by token {earlier['token']}")
        return "escalate"
    try:
        claims.write(op, {"holder": lease.holder,
                          "token": lease.token}, lease.token)  # (3)
    except StaleToken:
        log.record("fenced", op, holder=lease.holder,
                   token=lease.token, reason="claim refused")
        return "lost_lease"
    log.record("claim", op, holder=lease.holder,  # (4)
               token=lease.token, expires=lease.expires)
    pause("before_send")  # (5)
    receipt = call(log, mailer, op, "send", to=to, subject=subject)
    return "sent" if receipt is not None else "no_receipt"
# endregion


# region: ex06_late_sends
def late_sends(log) -> list[str]:
    """Ops whose request left after the claiming lease had expired."""
    late = []
    for op in log.ops():
        expires = None
        for e in log.for_op(op):
            if e["kind"] == "claim":
                expires = e["expires"]
            elif (e["kind"] == "sent" and expires is not None
                  and e["t"] >= expires):
                late.append(op)
                break
    return late
# endregion
