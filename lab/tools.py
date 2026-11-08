"""Fake external systems with faults you can schedule.

The point of every fault here is that two of them look identical from
the caller's side. LOST_REPLY applies the change and then loses the
answer. NOT_DELIVERED loses the request before anything happens. Both
raise ToolTimeout. The caller cannot tell them apart without asking
the other system, which is what most of this book is about.
"""
from enum import Enum


# region: faults
class Fault(str, Enum):
    NONE = "none"
    LOST_REPLY = "lost_reply"        # applied; the answer is lost
    NOT_DELIVERED = "not_delivered"  # lost on the way; not applied
    REJECT = "reject"                # the tool says no, explicitly
    LATE_APPLY = "late_apply"        # applies after we stop waiting


class ToolTimeout(Exception):
    """We stopped waiting. Says nothing about the other side."""


class ToolRejected(Exception):
    """The other side answered, and the answer was no."""
# endregion


class FakeTool:
    name = "tool"
    supports_status = True

    def __init__(self, faults=None):
        # One fault per call, in order. Calls past the end get NONE.
        self.faults = list(faults or [])
        self.applied = {}      # op -> receipt
        self.pending = []      # (op, apply) waiting for settle()
        self.calls = 0
        self._seq = 0

    def _receipt_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:04d}"

    # region: call
    def _call(self, op, apply):
        fault = self.faults.pop(0) if self.faults else Fault.NONE
        self.calls += 1
        if fault == Fault.REJECT:
            raise ToolRejected(f"{self.name} rejected {op}")
        if fault == Fault.NOT_DELIVERED:
            raise ToolTimeout(op)
        if fault == Fault.LATE_APPLY:
            self.pending.append((op, apply))
            raise ToolTimeout(op)
        receipt = apply()
        self.applied[op] = receipt
        if fault == Fault.LOST_REPLY:
            raise ToolTimeout(op)
        return receipt
    # endregion

    def settle(self):
        """Let queued work land, as it would after we gave up on it."""
        while self.pending:
            op, apply = self.pending.pop(0)
            self.applied[op] = apply()

    # region: status
    def status(self, op):
        """The receipt for `op` if it was applied, else None."""
        if not self.supports_status:
            raise NotImplementedError(f"{self.name} has no lookup")
        return self.applied.get(op)
    # endregion


class Storefront(FakeTool):
    """Product descriptions. Writes are reversible."""
    name = "storefront"

    def __init__(self, catalog=None, faults=None):
        super().__init__(faults)
        self.catalog = {k: dict(v) for k, v in (catalog or {}).items()}

    def set_description(self, op, sku, text):
        def apply():
            item = self.catalog.setdefault(sku, {"text": "",
                                                 "version": 0})
            before = item["text"]
            item["text"] = text
            item["version"] += 1
            return {"receipt": self._receipt_id("rcpt"), "sku": sku,
                    "version": item["version"], "before": before}
        return self._call(op, apply)

    def revert(self, receipt):
        item = self.catalog[receipt["sku"]]
        item["text"] = receipt["before"]
        item["version"] += 1
        return item["version"]


class Payments(FakeTool):
    """Refunds. An idempotency key makes a repeat return the first
    receipt instead of paying twice."""
    name = "payments"

    def __init__(self, faults=None):
        super().__init__(faults)
        self.refunds = []      # every refund actually paid
        self.by_key = {}

    def refund(self, op, order, amount, key=None):
        def apply():
            if key is not None and key in self.by_key:
                return self.by_key[key]
            receipt = {"refund": self._receipt_id("rf"),
                       "order": order, "amount": amount}
            self.refunds.append(receipt)
            if key is not None:
                self.by_key[key] = receipt
            return receipt
        return self._call(op, apply)

    def lookup(self, key):
        return self.by_key.get(key)


class Mailer(FakeTool):
    """Email. Sent is sent: no lookup, no undo."""
    name = "mailer"
    supports_status = False

    def __init__(self, faults=None):
        super().__init__(faults)
        self.outbox = []

    def send(self, op, to, subject):
        def apply():
            msg = {"message_id": self._receipt_id("msg"), "to": to,
                   "subject": subject}
            self.outbox.append(msg)
            return msg
        return self._call(op, apply)
