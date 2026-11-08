"""Exercise 10, reference answer."""
from lab.agent import call, request_hash
from lab.compensation import (CAPABILITIES, receipt_of,
                              reference_classify)
from lab.outcomes import Outcome

classify = reference_classify()


# region: ex10_plan_step
def plan_step(step, outcome, receipt):
    """What to do about one step of a run we are backing out of."""
    item = {"op": step["op"], "tool": step["tool"], "outcome": outcome,
            "receipt": None, "request": None, "needs_approval": False}
    if outcome == Outcome.UNKNOWN:  # (1)
        return {**item, "do": "wait",
                "why": "no answer yet; find out first"}
    if outcome != Outcome.CONFIRMED:  # (2)
        return {**item, "do": "leave",
                "why": f"{outcome.value}: nothing to undo"}
    if CAPABILITIES[step["tool"]]["reverse"]:  # (3)
        return {**item, "do": "reverse", "receipt": receipt,
                "why": "confirmed, reversible"}
    if step["compensation"]:  # (4)
        return {**item, "do": "compensate", "needs_approval": True,
                "request": step["compensation"],
                "why": "irreversible; a new action"}
    return {**item, "do": "leave",  # (5)
            "why": "irreversible; no compensation"}
# endregion


# region: ex10_plan_recovery
def plan_recovery(log, steps):
    """One plan item per step the run touched, newest first."""
    by_op = {s["op"]: s for s in steps}
    plan = []
    for op in reversed(log.ops()):  # (1)
        if op not in by_op:
            continue  # a compensation's own op; planned with its step
        events = log.for_op(op)
        done = already_handled(log, op)
        if done:  # (2)
            plan.append({"op": op, "tool": by_op[op]["tool"],
                         "outcome": classify(events), "do": done[0],
                         "why": done[1], "receipt": None,
                         "request": None, "needs_approval": False})
            continue
        plan.append(plan_step(by_op[op], classify(events),
                              receipt_of(events)))
    return plan


def already_handled(log, op):
    """(do, why) if an earlier recovery pass already acted on op."""
    if any(e["kind"] == "reverse" for e in log.for_op(op)):
        return ("leave", "already reversed")
    comp = log.for_op("comp-" + op)
    if comp:
        outcome = classify(comp)
        do = "wait" if outcome == Outcome.UNKNOWN else "leave"
        return (do, f"compensation {outcome.value}")
    return None
# endregion


# region: ex10_apply
def apply_plan(plan, tools, log, approvals=None):
    """Carry out a plan. Returns {op: what happened}."""
    approvals = approvals or {}
    results = {}
    for item in plan:
        op, do = item["op"], item["do"]
        if do == "reverse":
            results[op] = reverse_write(tools[item["tool"]], log, item)
        elif do == "compensate":
            req = item["request"]
            wanted = request_hash(req["tool"], req["action"],
                                  req["args"])
            if approvals.get(op) != wanted:  # (1)
                results[op] = "awaiting approval"
                continue
            call(log, tools[req["tool"]], "comp-" + op,  # (2)
                 req["action"], **req["args"])
            outcome = classify(log.for_op("comp-" + op))
            results[op] = f"compensation {outcome.value}"
        else:
            results[op] = do  # (3)
    return results
# endregion


# region: ex10_reverse
def reverse_write(shop, log, item):
    """Put back the text a confirmed storefront write replaced."""
    receipt = item["receipt"]
    current = shop.catalog[receipt["sku"]]["version"]  # (1)
    if current != receipt["version"]:
        return "refused: changed since our write"
    method = getattr(shop, CAPABILITIES[shop.name]["reverse"])
    version = method(receipt)
    log.record("reverse", item["op"], receipt=receipt["receipt"],
               version=version)  # (2)
    return "reversed"
# endregion


def demo():
    """The chapter's run: plan, then apply with no approvals."""
    from lab.compensation import STEPS, run_workflow
    from lab.runlog import RunLog
    from lab.tools import Fault, Mailer, Payments, Storefront
    shop = Storefront({"SKU-4471": {"text": "Wool camp blanket",
                                    "version": 2},
                       "SKU-4472": {"text": "Enamel camp mug",
                                    "version": 5}},
                      faults=[Fault.NONE, Fault.LOST_REPLY])
    tools = {"storefront": shop, "payments": Payments(),
             "mailer": Mailer()}
    log = run_workflow(RunLog(), tools, STEPS)
    plan = plan_recovery(log, STEPS)
    for item in plan:
        print(f"{item['op']:<15} {item['outcome'].value:<11} "
              f"{item['do']:<11} {item['why']}")
    print()
    for op, result in apply_plan(plan, tools, log).items():
        print(f"{op:<15} {result}")


if __name__ == "__main__":
    demo()
