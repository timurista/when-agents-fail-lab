"""Exercise 13, reference answer."""
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


# region: ex13_run
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
        tool.settle()  # (1)
    return {"log": log, "tools": tools, "approval": approval,
            "report": report}
# endregion


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


# region: ex13_v1
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
# endregion


# region: ex13_safe
def process_return(log, clock, tools, approval) -> dict:
    """One key for the refund, one op id per send, approval per send."""
    pay, args = tools["payments"], {"order": ORDER, "amount": AMOUNT}
    for n in range(1, 4):
        op = f"op-refund-{n}"  # (1)
        if not approval_holds(approval, args, clock.now()):  # (2)
            log.record("escalate", None, reason="approval expired")
            break
        if send(log, clock, pay, op, "refund", key=KEY, **args):
            break
        if log.events[-1]["kind"] == "response":
            break  # rejected: resending it unchanged won't help
        found = pay.lookup(KEY)  # (3)
        log.record("status", op, found=found is not None,
                   receipt=found, authoritative=False)
        if found:
            break
    return finish(log, clock, tools)
# endregion


# region: ex13_naive
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
# endregion


# region: ex13_empty
def process_return_empty(log, clock, tools, approval) -> dict:
    """The control: does nothing, so it can break no safety rule."""
    return {}
# endregion


# region: ex13_schedules
def schedules(shape: dict):
    """Every way to give each call in `shape` one fault."""
    slots = [tool for tool, calls in shape.items()
             for _ in range(calls)]
    for combo in itertools.product(list(Fault), repeat=len(slots)):
        schedule = {tool: () for tool in shape}
        for tool, fault in zip(slots, combo):
            schedule[tool] += (fault,)
        yield schedule
# endregion


# region: ex13_invariants
def check_invariants(result: dict) -> list[str]:
    """Names of the rules this run broke. Empty means it held."""
    log, tools = result["log"], result["tools"]
    broken = set()
    if len(tools["payments"].refunds) > 1:
        broken.add("doubled_refund")
    if len(tools["mailer"].outbox) > 1:
        broken.add("doubled_email")
    for op, outcome in result["report"].items():
        if outcome is not Outcome.FAILED:
            continue
        if classify(log.for_op(op)) is not Outcome.FAILED:
            broken.add("unknown_marked_failed")  # (1)
        if any(op in tool.applied for tool in tools.values()):
            broken.add("applied_marked_failed")  # (2)
    expires = result["approval"]["expires_at"]
    if any(e["kind"] == "sent" and e["op"].startswith("op-refund")
           and e["t"] >= expires for e in log.events):
        broken.add("expired_approval")
    return sorted(broken)
# endregion


# region: ex13_explore
def explore(workflow, shape: dict = SHAPE) -> list:
    """(schedule, broken rules) for every schedule that breaks one."""
    failures = []
    for schedule in schedules(shape):
        broken = check_invariants(run(workflow, schedule))
        if broken:
            failures.append((schedule, broken))
    return failures
# endregion


# region: ex13_goal
def reaches_goal(result: dict) -> bool:
    """Progress, from ground truth: refunded, emailed, restocked."""
    tools = result["tools"]
    return (len(tools["payments"].refunds) == 1
            and len(tools["mailer"].outbox) == 1
            and tools["storefront"].catalog.get(SKU, {}).get("text")
            == "Back in stock")


def assess(workflow, shape: dict = SHAPE) -> dict:
    """Safety and completion, reported separately."""
    fault_free = {tool: (Fault.NONE,) * n for tool, n in shape.items()}
    return {"unsafe": explore(workflow, shape),  # (1)
            "completes": reaches_goal(run(workflow, fault_free))}  # (2)
# endregion


# region: ex13_consistent
TIMEOUTS = (Fault.LOST_REPLY, Fault.NOT_DELIVERED, Fault.LATE_APPLY)


def consistent_faults(log) -> dict:
    """{tool: [faults that fit the log, one tuple per call]}."""
    tool_of, out = {}, {}
    for i, e in enumerate(log.events):
        if e["kind"] == "intent":
            tool_of[e["op"]] = e["tool"]
        if e["kind"] != "sent":
            continue
        answer = next((a for a in log.events[i + 1:]
                       if a.get("op") == e["op"]
                       and a["kind"] in ("response", "timeout")), None)
        if answer is None:
            fits = tuple(Fault)  # (1)
        elif answer["kind"] == "timeout":
            fits = TIMEOUTS  # (2)
        elif answer["ok"]:
            fits = (Fault.NONE,)
        else:
            fits = (Fault.REJECT,)
        out.setdefault(tool_of[e["op"]], []).append(fits)
    return out


def incident_schedules(log):
    """Every schedule the incident's log cannot rule out."""
    per_call = [(tool, fits) for tool, calls in
                consistent_faults(log).items() for fits in calls]
    for combo in itertools.product(*(f for _, f in per_call)):
        schedule = {}
        for (tool, _), fault in zip(per_call, combo):
            schedule[tool] = schedule.get(tool, ()) + (fault,)
        yield schedule
# endregion


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


# region: ex13_main
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
# endregion


if __name__ == "__main__":
    main()
