"""Exercise 6: two workers, one effect."""
from lab.agent import call
from lab.leases import StaleToken


def no_pause(where: str) -> None:
    """The default: the worker runs straight through."""


def naive_update(leases, catalog, lease, sku, text, pause=no_pause):
    """The control. The worker checks its own lease, then writes.

    This one is finished and deliberately wrong. Leave it as it is:
    the checks use it to prove the race can happen at all.
    """
    if not leases.is_current(lease):
        return "lost_lease"
    pause("before_write")
    catalog[sku] = text
    return "written"


def fenced_update(store, lease, sku, text, pause=no_pause):
    """Write `text` for `sku` to a FencedStore with the lease's token.

    Call pause("before_write") first. Return "written", or "fenced"
    when the store refuses the token.
    """
    raise NotImplementedError("fenced_update")


def send_once(log, leases, claims, lease, mailer, op, to, subject,
              pause=no_pause):
    """Send one email for `op` through a tool that can't check tokens.

    Return "sent", "no_receipt", "lost_lease" or "escalate". Call
    pause("after_check") after the lease check and pause("before_send")
    just before the send. See the README for the rules.
    """
    raise NotImplementedError("send_once")


def late_sends(log) -> list[str]:
    """Ops whose `sent` came at or after the claiming lease expired."""
    raise NotImplementedError("late_sends")
