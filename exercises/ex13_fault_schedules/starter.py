"""Exercise 13: enumerate fault schedules; turn an incident into a test.

Given, and not part of the exercise: the workflows (naive, v1, the
fixed process_return and the do-nothing control), run, classify and
main. Write schedules, check_invariants, explore, reaches_goal, assess,
consistent_faults and incident_schedules.
The README lists the rules.
"""
import itertools

from lab.agent import call, request_hash
from lab.clock import FakeClock
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Mailer, Payments, Storefront

ORDER, AMOUNT, SKU = "ORD-5531", 58.0, "SKU-7730"
TO = "customer-5531@example.test"
KEY = f"{ORDER}-refund"
TIMEOUT_S = 5.0      # how long a timed-out call costs on the clock
APPROVED_FOR = 8.0   # the refund approval expires at t = 8.0
SHAPE = {"payments": 3, "mailer": 1, "storefront": 1}


def classify(events: list[dict]) -> Outcome:
    """Chapter 1's classifier, repeated so this file stands alone."""
    for e in events:
        if e["kind"] == "response" and e["ok"]:
            return Outcome.CONFIRMED
        if e["kind"] == "status" and e["found"]:
            return Outcome.CONFIRMED
    for e in reversed(events):
        if e["kind"] == "decision":
            return Outcome(e["outcome"])
        if e["kind"] == "response" and not e["ok"]:
            return Outcome.FAILED
        if (e["kind"] == "status" and not e["found"]
                and e.get("authoritative")):
            return Outcome.FAILED
        if e["kind"] == "cancel_ack":
            return Outcome.CANCELED
    if not any(e["kind"] == "sent" for e in events):
        return Outcome.NEVER_SENT
    return Outcome.UNKNOWN


def send(log, clock, tool, op, action, **args):
    """lab.agent.call, plus the time a timeout costs."""
    receipt = call(log, tool, op, action, **args)
    if log.events[-1]["kind"] == "timeout":
        clock.advance(TIMEOUT_S)
    return receipt


def approval_holds(approval, args, now) -> bool:
    return (now < approval["expires_at"] and approval["request_hash"]
            == request_hash("payments", "refund", args))


def run(workflow, schedule: dict) -> dict:
    """Run `workflow` once under `schedule`, then let late work land."""
    clock = FakeClock()
    log = RunLog(clock)
    tools = {"payments": Payments(schedule.get("payments", ())),
             "mailer": Mailer(schedule.get("mailer", ())),
             "storefront": Storefront(
                 faults=schedule.get("storefront", ()))}
    args = {"order": ORDER, "amount": AMOUNT}
    bound = request_hash("payments", "refund", args)
    approval = {"request_hash": bound, "expires_at": APPROVED_FOR}
    report = workflow(log, clock, tools, approval)
    for tool in tools.values():
        tool.settle()
    return {"log": log, "tools": tools, "approval": approval,
            "report": report}


def refund_outcome(log) -> Outcome:
    """One refund, however many sends carried it."""
    outs = [classify(log.for_op(op)) for op in log.ops()
            if op.startswith("op-refund")]
    for o in (Outcome.CONFIRMED, Outcome.UNKNOWN):
        if o in outs:
            return o
    return outs[-1] if outs else Outcome.NEVER_SENT


def finish(log, clock, tools) -> dict:
    """Email only on a confirmed refund, then restock. No resends."""
    if refund_outcome(log) is Outcome.CONFIRMED:
        send(log, clock, tools["mailer"], "op-email", "send", to=TO,
             subject=f"Your refund for {ORDER}")
    shop = tools["storefront"]
    if send(log, clock, shop, "op-restock", "set_description", sku=SKU,
            text="Back in stock") is None:
        if log.events[-1]["kind"] == "timeout":
            found = shop.status("op-restock")
            log.record("status", "op-restock", found=found is not None,
                       receipt=found, authoritative=False)
    return {op: classify(log.for_op(op)) for op in log.ops()}


def process_return_v1(log, clock, tools, approval) -> dict:
    """Key and lookup, but one op id, and the approval checked once."""
    pay, args = tools["payments"], {"order": ORDER, "amount": AMOUNT}
    if approval_holds(approval, args, clock.now()):
        for _ in range(3):
            if send(log, clock, pay, "op-refund", "refund", key=KEY,
                    **args):
                break
            if log.events[-1]["kind"] == "response":
                break
            found = pay.lookup(KEY)
            log.record("status", "op-refund", found=found is not None,
                       receipt=found, authoritative=False)
            if found:
                break
    return finish(log, clock, tools)


def process_return(log, clock, tools, approval) -> dict:
    """One key for the refund, one op id per send, approval per send."""
    pay, args = tools["payments"], {"order": ORDER, "amount": AMOUNT}
    for n in range(1, 4):
        op = f"op-refund-{n}"
        if not approval_holds(approval, args, clock.now()):
            log.record("escalate", None, reason="approval expired")
            break
        if send(log, clock, pay, op, "refund", key=KEY, **args):
            break
        if log.events[-1]["kind"] == "response":
            break  # rejected: resending it unchanged won't help
        found = pay.lookup(KEY)
        log.record("status", op, found=found is not None,
                   receipt=found, authoritative=False)
        if found:
            break
    return finish(log, clock, tools)


def process_return_naive(log, clock, tools, approval) -> dict:
    """The version that shipped: a timeout is a failure, so retry."""
    report = {}
    for _ in range(3):
        if send(log, clock, tools["payments"], "op-refund", "refund",
                order=ORDER, amount=AMOUNT):
            report["op-refund"] = Outcome.CONFIRMED
            break
        report["op-refund"] = Outcome.FAILED
    if report["op-refund"] is Outcome.CONFIRMED:
        for _ in range(2):
            ok = send(log, clock, tools["mailer"], "op-email", "send",
                      to=TO, subject=f"Your refund for {ORDER}")
            report["op-email"] = (Outcome.CONFIRMED if ok
                                  else Outcome.FAILED)
            if ok:
                break
    ok = send(log, clock, tools["storefront"], "op-restock",
              "set_description", sku=SKU, text="Back in stock")
    report["op-restock"] = Outcome.CONFIRMED if ok else Outcome.FAILED
    return report


def process_return_empty(log, clock, tools, approval) -> dict:
    """The control: does nothing, so it can break no safety rule."""
    return {}


def schedules(shape: dict):
    """Every way to give each call in `shape` one fault."""
    raise NotImplementedError("schedules")


def check_invariants(result: dict) -> list[str]:
    """Names of the rules this run broke. Empty means it held."""
    raise NotImplementedError("check_invariants")


def explore(workflow, shape: dict = SHAPE) -> list:
    """(schedule, broken rules) for every schedule that breaks one."""
    raise NotImplementedError("explore")


def reaches_goal(result: dict) -> bool:
    """Progress, from ground truth: refunded, emailed, restocked."""
    raise NotImplementedError("reaches_goal")


def assess(workflow, shape: dict = SHAPE) -> dict:
    """{"unsafe": explore(...), "completes": goal reached with no
    faults}. Safety and completion, reported separately."""
    raise NotImplementedError("assess")


TIMEOUTS = (Fault.LOST_REPLY, Fault.NOT_DELIVERED, Fault.LATE_APPLY)


def consistent_faults(log) -> dict:
    """{tool: [faults that fit the log, one tuple per call]}."""
    raise NotImplementedError("consistent_faults")


def incident_schedules(log):
    """Every schedule the incident's log cannot rule out."""
    raise NotImplementedError("incident_schedules")


def describe(schedule: dict) -> str:
    """'payments=lost_reply,none mailer=reject', trailing NONEs cut."""
    parts = []
    for tool, faults in schedule.items():
        faults = list(faults)
        while faults and faults[-1] is Fault.NONE:
            faults.pop()
        if faults:
            parts.append(f"{tool}=" + ",".join(f.value for f in faults))
    return " ".join(parts) or "no faults"


def main():
    total = sum(1 for _ in schedules(SHAPE))
    for workflow in (process_return_naive, process_return_v1,
                     process_return, process_return_empty):
        result = assess(workflow)
        failures = result["unsafe"]
        goal = "reached" if result["completes"] else "NOT reached"
        print(f"{workflow.__name__}: {len(failures)} of {total} break;"
              f" goal without faults {goal}")
        for rule in sorted({r for _, rules in failures for r in rules}):
            hits = [describe(s) for s, rules in failures
                    if rule in rules]
            shortest = min(hits, key=len)
            print(f"  {rule:<22} {len(hits):>5}  {shortest}")


if __name__ == "__main__":
    main()
