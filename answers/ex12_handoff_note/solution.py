"""Exercise 12, reference answer."""
import textwrap

from lab.outcomes import Outcome

# Which lab tools can answer "did you apply this op?" after the fact.
LOOKUP = {"storefront": True, "payments": True, "mailer": False}


# region: ex12_evidence
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
# endregion


# region: ex12_claims
def check_claims(log) -> dict:
    """Sort every claim in the log into current, stale, unsupported."""
    by_seq = {e["seq"]: e for e in log.events}
    out = {"current": [], "stale": [], "unsupported": []}
    for c in (e for e in log.events if e["kind"] == "claim"):
        proof = by_seq.get(c.get("evidence"))
        if proof is None:  # (1)
            out["unsupported"].append({"claim": c["text"]})
            continue
        changes = [e["seq"] for e in log.events
                   if e["kind"] == "change"
                   and e["subject"] == c["subject"]
                   and e["seq"] > proof["seq"]]  # (2)
        entry = {"claim": c["text"], "evidence": proof["seq"]}
        if changes:
            entry["changed"] = changes[0]
            out["stale"].append(entry)
        else:
            out["current"].append(entry)
    return out
# endregion


# region: ex12_handoff
def handoff(log) -> dict:
    """A handoff note built from the log, not from memory."""
    goal = next((e["text"] for e in log.events
                 if e["kind"] == "goal"), "(no goal recorded)")
    paused = [e for e in log.events if e["kind"] in ("pause", "stop")]
    settled, unknown, unfinished = [], [], []
    for op in log.ops():
        events = log.for_op(op)
        intent = next((e for e in events if e["kind"] == "intent"),
                      {"seq": events[0]["seq"]})
        where = {"op": op, "tool": intent.get("tool", "?"),
                 "action": intent.get("action", "?"),
                 "seq": intent["seq"]}
        outcome, proof = evidence_for(events)
        if outcome is Outcome.UNKNOWN:
            unknown.append(where)  # (1)
        elif outcome is Outcome.NEVER_SENT:
            unfinished.append(where)
        else:
            settled.append({**where, "outcome": outcome,
                            "evidence": proof["seq"]})
    claims = check_claims(log)
    return {"goal": goal, "paused": paused[-1] if paused else None,
            "settled": settled, "unknown": unknown,
            "unfinished": unfinished, "stale": claims["stale"],
            "unsupported": claims["unsupported"],
            "next_action": next_action(unknown, claims, unfinished),
            "do_not": do_not(settled, unknown, claims, unfinished)}
# endregion


# region: ex12_next
def next_action(unknown, claims, unfinished) -> dict:
    """The one step that is in bounds now. Read-only steps first."""
    if unknown:
        u = unknown[0]
        if LOOKUP.get(u["tool"]):
            return {"kind": "ask", "target": u["op"],
                    "text": f"ask {u['tool']} whether {u['op']} "
                            "was applied"}
        return {"kind": "escalate", "target": u["op"],
                "text": f"{u['tool']} has no lookup: find evidence "
                        f"for {u['op']} another way"}
    for c in claims["stale"] + claims["unsupported"]:
        return {"kind": "recheck", "target": c["claim"],
                "text": f"recheck before relying on it: {c['claim']}"}
    if unfinished:
        u = unfinished[0]
        return {"kind": "decide", "target": u["op"],
                "text": f"decide whether to resume {u['op']}"}
    return {"kind": "close", "target": None,
            "text": "nothing is open: close the run"}
# endregion


# region: ex12_do_not
def do_not(settled, unknown, claims, unfinished) -> list[dict]:
    """Steps that look helpful and aren't, each with its reason."""
    rules = [{"target": u["op"], "why": "unknown"} for u in unknown]
    for u in unfinished:
        before = [k for k in unknown if k["seq"] < u["seq"]]
        if before:  # (1)
            rules.append({"target": u["op"], "why": "after_unknown",
                          "until": before[0]["op"]})
    for s in settled:
        if s["outcome"] is Outcome.CONFIRMED:
            rules.append({"target": s["op"], "why": "confirmed"})
        elif s["outcome"] is Outcome.FAILED:
            rules.append({"target": s["op"], "why": "failed"})
    rules += [{"target": c["claim"], "why": "stale"}
              for c in claims["stale"]]
    rules += [{"target": c["claim"], "why": "unsupported"}
              for c in claims["unsupported"]]
    return rules
# endregion


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


# region: ex12_render
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
# endregion


if __name__ == "__main__":
    from lab.runlog import RunLog
    from lab.target import fixture
    log = RunLog.load(fixture("ex12_handoff_note", "paused-return.jsonl"))
    print(render(handoff(log)))
