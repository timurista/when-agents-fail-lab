"""Exercise 12: write a handoff note from a run log.

Given, and not part of the exercise: LOOKUP, evidence_for (Chapter 1's
classifier, keeping its proof) and render. Write check_claims, handoff,
next_action and do_not. The README lists the rules.
"""
import textwrap

from lab.outcomes import Outcome

# Which lab tools can answer "did you apply this op?" after the fact.
LOOKUP = {"storefront": True, "payments": True, "mailer": False}


def evidence_for(events: list[dict]):
    """(outcome, the event that decided it) for one operation.

    Chapter 1's classifier, changed to keep its proof. The event is
    None only for UNKNOWN, which has no proof by definition.
    """
    for e in events:
        if e["kind"] == "response" and e["ok"]:
            return Outcome.CONFIRMED, e
        if e["kind"] == "status" and e["found"]:
            return Outcome.CONFIRMED, e
    for e in reversed(events):
        if e["kind"] == "decision":
            if not e.get("reason"):
                raise ValueError("a decision needs a reason")
            return Outcome(e["outcome"]), e
        if e["kind"] == "response" and not e["ok"]:
            return Outcome.FAILED, e
        if (e["kind"] == "status" and not e["found"]
                and e.get("authoritative")):
            return Outcome.FAILED, e
        if e["kind"] == "cancel_ack":
            return Outcome.CANCELED, e
    if not any(e["kind"] == "sent" for e in events):
        return Outcome.NEVER_SENT, events[0]
    return Outcome.UNKNOWN, None


def check_claims(log) -> dict:
    """Sort every claim in the log into current, stale, unsupported."""
    raise NotImplementedError("check_claims")


def handoff(log) -> dict:
    """A handoff note built from the log, not from memory."""
    raise NotImplementedError("handoff")


def next_action(unknown, claims, unfinished) -> dict:
    """The one step that is in bounds now. Read-only steps first."""
    raise NotImplementedError("next_action")


def do_not(settled, unknown, claims, unfinished) -> list[dict]:
    """Steps that look helpful and aren't, each with its reason."""
    raise NotImplementedError("do_not")


WHY = {
    "unknown": "resend {target}: no answer yet, a resend may double it",
    "after_unknown": "resume {target} before {until} is settled",
    "confirmed": "redo {target}: it is already confirmed",
    "failed": "resend {target} unchanged: the other side said no",
    "stale": 'rely on "{target}": a change came after its evidence',
    "unsupported": 'rely on "{target}": it points at no evidence',
}


def _wrap(line: str, indent: str = "  ") -> list[str]:
    return textwrap.wrap(line, 72, initial_indent=indent,
                         subsequent_indent=indent + "  ")


def render(note: dict) -> str:
    """The note as text. Every line fits in 72 columns."""
    out = _wrap(f"GOAL: {note['goal']}", "")
    if note["paused"]:
        p = note["paused"]
        out += _wrap(f"PAUSED at seq {p['seq']}: "
                     f"{p.get('reason', p['kind'])}", "")
    out.append("VERIFIED (seq = the event that proves it)")
    for s in note["settled"]:
        out.append(f"  {s['op']:<20} {s['outcome'].value:<10}"
                   f" seq {s['evidence']}")
    out.append("UNKNOWN (sent, never answered)")
    for u in note["unknown"]:
        out.append(f"  {u['op']:<20} {u['tool']}.{u['action']}")
    out.append("UNFINISHED (never sent)")
    for u in note["unfinished"]:
        out.append(f"  {u['op']:<20} {u['tool']}.{u['action']}")
    out.append("CLAIMS NOT TO TRUST")
    for c in note["stale"]:
        out += _wrap(f"stale: {c['claim']} (evidence seq "
                     f"{c['evidence']}, changed seq {c['changed']})")
    for c in note["unsupported"]:
        out += _wrap(f"unsupported: {c['claim']}")
    out.append("NEXT ACTION (the only one in bounds)")
    out += _wrap(note["next_action"]["text"])
    out.append("DO NOT")
    for rule in note["do_not"]:
        out += _wrap("- " + WHY[rule["why"]].format(**rule))
    return "\n".join(out)


if __name__ == "__main__":
    from lab.runlog import RunLog
    from lab.target import fixture
    log = RunLog.load(fixture("ex12_handoff_note", "paused-return.jsonl"))
    print(render(handoff(log)))
