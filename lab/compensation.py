"""Chapter 10's workflow: one support ticket, five steps, three tools.

Everything here is synthetic. Ticket T-2207 asked the agent to make
things right for order ORD-7713. The ticket said ORD-7731, so every
step below acts on the wrong order. Exercise 10 plans the way back.
"""
import importlib.util

from .agent import call, request_hash
from .target import ROOT


# region: ex10_capabilities
# What each tool can do after the fact. "reverse" names a method that
# restores the state before a confirmed write, if the tool has one.
CAPABILITIES = {
    "storefront": {"reverse": "revert", "status": True},
    "payments": {"reverse": None, "status": True},
    "mailer": {"reverse": None, "status": False},
}
# endregion


# region: ex10_workflow
STEPS = [
    {"op": "op-4471-hold", "tool": "storefront",
     "action": "set_description",
     "args": {"sku": "SKU-4471", "text": "On hold: quality check"},
     "compensation": None},
    {"op": "op-7731-refund", "tool": "payments", "action": "refund",
     "args": {"order": "ORD-7731", "amount": 64.00,
              "key": "T-2207-refund"},
     "compensation": None},  # (1)
    {"op": "op-7731-email", "tool": "mailer", "action": "send",
     "args": {"to": "buyer-7731@example.com",
              "subject": "Sorry about your order ORD-7731"},
     "compensation": {"tool": "mailer", "action": "send",  # (2)
                      "args": {"to": "buyer-7731@example.com",
                               "subject": "Correction: our earlier "
                                          "email about ORD-7731"}}},
    {"op": "op-4472-hold", "tool": "storefront",
     "action": "set_description",
     "args": {"sku": "SKU-4472", "text": "On hold: quality check"},
     "compensation": None},
    {"op": "op-qa-note", "tool": "mailer", "action": "send",
     "args": {"to": "qa@fernhill.example",
              "subject": "Check SKU-4471 and SKU-4472"},
     "compensation": None},
]
# endregion


# region: ex10_run
def run_workflow(log, tools, steps):
    """Run steps in order. Halt at the first step with no receipt."""
    halted = False
    for step in steps:
        if halted:  # (1)
            log.record("intent", step["op"], tool=step["tool"],
                       action=step["action"], args=step["args"],
                       request_hash=request_hash(
                           step["tool"], step["action"], step["args"]))
            continue
        receipt = call(log, tools[step["tool"]], step["op"],
                       step["action"], **step["args"])
        if receipt is None:
            halted = True  # (2)
    return log
# endregion


def receipt_of(events):
    """The receipt that confirms an operation, or None."""
    for e in events:
        if e["kind"] == "response" and e.get("ok"):
            return e.get("receipt")
        if e["kind"] == "status" and e.get("found"):
            return e.get("receipt")
    return None


def reference_classify():
    """Chapter 1's reference `classify`, so this module stands alone."""
    path = ROOT / "answers" / "ex01_three_outcomes" / "solution.py"
    spec = importlib.util.spec_from_file_location("ex01_ref", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify
