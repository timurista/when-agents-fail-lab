"""The recovery drill for Chapter 14: a scripted incident and a rubric.

Everything here is synthetic. `stage()` replays one stopped run at
Fernhill Supply with faults on all three tools at once. `score()` grades
a drill report against the facilitator's answer key and against what
the fake tools actually hold after the team's plan is carried out.

    python3 -m lab.drill              score your ex14 starter.py
    python3 -m lab.drill --solution   score the reference answer
    python3 -m lab.drill --blind      score a responder who retries
    add --report to print the messages and the handoff note

The rubric is public on purpose. The key is the facilitator's.
"""
import json
import os
import sys
from collections import Counter, namedtuple

from .agent import call, request_hash
from .runlog import RunLog
from .tools import Fault, Mailer, Payments, Storefront

EX = "ex14_drill"
Incident = namedtuple("Incident", "log tools claims")


# region: drill_capabilities
# What the drill sheet tells responders about each tool. Synthetic.
# "closes" names what rules out a late apply after a lookup miss: a
# cancel acknowledgment or a deadline the provider guarantees.
CAPABILITIES = {
    # Writes go through a queue, so "not found" may mean "not yet".
    "storefront": {"lookup": "status", "authoritative": False,
                   "closes": None, "key": False, "reversible": True},
    # Keyed, but a refund still in the provider's queue is invisible
    # to the lookup and can apply after a miss (Chapter 4).
    "payments": {"lookup": "key", "authoritative": False,
                 "closes": None, "key": True, "reversible": False},
    # Sent is sent: no lookup, no undo.
    "mailer": {"lookup": None, "authoritative": False,
               "closes": None, "key": False, "reversible": False},
}

ACTIONS = {
    "keep": "leave the confirmed effect in place",
    "reverse": "undo a confirmed, reversible effect",
    "resend": "send again with the same idempotency key",
    "resume": "send a request that never left",
    "discard": "drop a request that never left",
    "wait": "ask the tool again later; touch nothing",
    "escalate": "a named person finds out or decides",
}
# endregion


# region: drill_miss
def miss_proves_failure(cap: dict) -> bool:
    """A miss means "not applied, and never will be" only when the
    lookup is authoritative AND the protocol rules out a late apply."""
    return cap["authoritative"] and cap["closes"] is not None
# endregion


def unsafe_on_unknown(incident, op, action) -> bool:
    """Resume and discard guess. A resend is safe only with a key."""
    if action == "resend":
        intent = next(e for e in incident.log.for_op(op)
                      if e["kind"] == "intent")
        return not CAPABILITIES[intent["tool"]]["key"]
    return action in ("resume", "discard")


# region: drill_incident
def stage(late=False) -> Incident:
    """Replay the stopped returns run. Same result every time."""
    shop = Storefront(faults=[Fault.LATE_APPLY, Fault.NOT_DELIVERED])
    last = Fault.LATE_APPLY if late else Fault.NOT_DELIVERED
    pay = Payments(faults=[Fault.LOST_REPLY, Fault.REJECT, last])
    pay.refunds.append({"refund": "rf-0000", "order": "ORD-5104",
                        "amount": 18.50})  # refunded by hand, earlier
    mail = Mailer(faults=[Fault.LOST_REPLY])
    log = RunLog()
    call(log, pay, "op-r5103", "refund", order="ORD-5103",
         amount=42.00, key="k-r5103")
    call(log, mail, "op-m5103", "send", to="c5103@example.com",
         subject="Refund issued for ORD-5103")
    call(log, shop, "op-s4471", "set_description", sku="SKU-4471",
         text="Back in stock")
    call(log, pay, "op-r5104", "refund", order="ORD-5104",
         amount=18.50, key="k-r5104")
    call(log, shop, "op-s9102", "set_description", sku="SKU-9102",
         text="Back in stock")
    call(log, pay, "op-r5105", "refund", order="ORD-5105",
         amount=63.00, key="k-r5105")
    args = {"to": "c5105@example.com",
            "subject": "Refund issued for ORD-5105"}
    log.record("intent", "op-m5105", tool="mailer", action="send",
               args=args, request_hash=request_hash("mailer", "send",
                                                    args))
    log.record("stop", None, by="operator")
    shop.settle()  # the queued storefront write lands after Stop
    claims = {"op-r5103": "refunded", "op-r5104": "refunded",
              "op-r5105": "refunded", "op-m5103": "emailed",
              "op-m5105": "emailed"}  # the agent's final message
    tools = {t.name: t for t in (shop, pay, mail)}
    return Incident(log, tools, claims)
# endregion


def load_key(path=None) -> dict:
    from . import target
    path = path or target.fixture(EX, "answer-key.json")
    with open(path) as f:
        return json.load(f)


# region: drill_invariants
def invariants(incident) -> list[str]:
    """What must be true in the world after the plan is carried out."""
    pay, mail = incident.tools["payments"], incident.tools["mailer"]
    broken = []
    paid = Counter(r["order"] for r in pay.refunds)
    for order, n in paid.items():
        if n > 1:
            broken.append(f"{order} refunded {n} times")
    sent = Counter((m["to"], m["subject"]) for m in mail.outbox)
    for (to, _), n in sent.items():
        if n > 1:
            broken.append(f"{to} got the same email {n} times")
    for m in mail.outbox:
        order = m["subject"].rsplit(" ", 1)[-1]
        if order not in paid:
            broken.append(f"{m['to']} told {order} was refunded")
    return broken
# endregion


def apply_plan(incident, plan: dict) -> None:
    """Carry out resend and resume, in log order, as the team would."""
    for op in incident.log.ops():
        if plan.get(op) not in ("resend", "resume"):
            continue
        intent = next(e for e in incident.log.for_op(op)
                      if e["kind"] == "intent")
        tool = incident.tools[intent["tool"]]
        call(incident.log, tool, op, intent["action"], **intent["args"])


# region: drill_rubric
def score(report: dict, incident, key: dict) -> dict:
    """Grade a drill report. Stages are checked in order; the first one
    that fails is where the drill stalled."""
    after, plan = key["after"], report.get("plan", {})
    unknown = sorted(op for op, o in after.items() if o == "unknown")
    checks = {
        "classify": report.get("before") == key["before"],
        "reconcile": report.get("after") == after,
        "decide": all(plan.get(op) in ok
                      for op, ok in key["allowed"].items()),
        "message": not lint(report, after),
        "handoff": handoff_ok(report, key, unknown),
    }
    critical = [f"{op}: {plan[op]} on an unknown outcome"
                for op in unknown
                if unsafe_on_unknown(incident, op, plan.get(op))]  # (1)
    critical += [f"{op}: unknown reported as failed" for op in unknown
                 if report.get("after", {}).get(op) == "failed"]
    apply_plan(incident, plan)
    for tool in incident.tools.values():
        tool.settle()  # late work lands before the world is checked
    critical += invariants(incident)  # (2)
    stalled = next((s for s, ok in checks.items() if not ok), None)
    passed = stalled is None and not critical  # (3)
    return {"checks": checks, "stalled_at": stalled,
            "critical": critical, "passed": passed,
            "recovery": recovery(passed, report)}


def recovery(passed: bool, report: dict) -> str:
    """Kept apart from the pass: who needed help is a finding."""
    if not passed:
        return "not recovered"
    if report.get("assists"):
        return "recovered with assistance"
    return "recovered independently"  # (4)
# endregion


# region: drill_lint
def lint(report, after) -> list[str]:
    """Wording rules for operator messages, published with the drill."""
    problems = []
    plan, msgs = report.get("plan", {}), report.get("messages", {})
    for op, outcome in after.items():
        text = msgs.get(op, "").lower()
        if outcome.replace("_", " ") not in text:
            problems.append(f"{op}: outcome not named")
        if plan.get(op, "?") not in text:
            problems.append(f"{op}: next step not named")
        if outcome != "failed" and "fail" in text:
            problems.append(f"{op}: says failed")
    n = sum(o == "unknown" for o in after.values())
    if f"{n} unknown" not in report.get("headline", ""):
        problems.append("headline hides the unknowns")
    return problems
# endregion


def handoff_ok(report, key, unknown) -> bool:
    note = report.get("handoff", {})
    plan = report.get("plan", {})
    nxt = note.get("next_action", {})
    dont = " ".join(note.get("do_not", []))
    return (sorted(note.get("unknown", [])) == unknown
            and sorted(note.get("stale_claims", [])) ==
            sorted(key["stale_claims"])
            and plan.get(nxt.get("op")) not in (None, "keep")
            and nxt.get("action") == plan.get(nxt.get("op"))
            and all(op in dont for op in unknown
                    if plan.get(op) != "resend"))


def blind_report(incident) -> dict:
    """The responder this drill exists to catch: every timeout is a
    failure, and every failure gets another try."""
    before = {}
    for op in incident.log.ops():
        events = incident.log.for_op(op)
        kinds = [e["kind"] for e in events]
        ok = any(e.get("ok") for e in events)
        before[op] = ("confirmed" if ok else "never_sent"
                      if "sent" not in kinds else "failed")
    plan = {op: "resend" if o == "failed" else "resume"
            if o == "never_sent" else "keep"
            for op, o in before.items()}
    msgs = {op: f"{o}" for op, o in before.items()}
    return {"before": before, "after": before, "plan": plan,
            "messages": msgs, "headline": "Run failed. Retrying.",
            "handoff": {}}


# region: drill_scorecard
def scorecard(result) -> str:
    lines = []
    for stage_name, ok in result["checks"].items():
        lines.append(f"  {stage_name:<10} {'pass' if ok else 'STALL'}")
    for c in result["critical"]:
        lines.append(f"  critical   {c}")
    stalled = result["stalled_at"] or "nowhere"
    verdict = "PASS" if result["passed"] else "NOT PASSED"
    lines.append(f"  stalled at {stalled}; drill {verdict}")
    lines.append(f"  {result['recovery']}")
    return "\n".join(lines)
# endregion


def report_text(report) -> str:
    """The parts of a report a person reads, for the terminal."""
    lines = [report.get("headline", "")]
    lines += [f"  {m}" for m in report.get("messages", {}).values()]
    note = report.get("handoff", {})
    nxt = note.get("next_action", {})
    lines.append(f"next action: {nxt.get('action')} {nxt.get('op')}")
    lines.append("stale claims: " + ", ".join(note.get("stale_claims",
                                                       [])))
    lines += [f"  {d}" for d in note.get("do_not", [])]
    return "\n".join(lines)


def main(argv):
    from . import target
    if "--solution" in argv:
        os.environ["LAB_TARGET"] = "solution"
    incident = stage()
    if "--blind" in argv:
        who, report = "blind retry", blind_report(incident)
    else:
        who = os.environ.get("LAB_TARGET", "starter")
        try:
            report = target.load(EX).run_drill(incident)
        except NotImplementedError as err:
            print(f"{EX}: {err} is not written yet")
            return 1
    print(f"== drill: Fernhill returns run ({who})")
    if "--report" in argv:
        print(report_text(report))
    result = score(report, incident, load_key())
    print(scorecard(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
