"""Exercise 9, reference answer."""
import csv
import hashlib
import json
from collections import namedtuple
from enum import Enum
from pathlib import Path

from lab.runlog import RunLog


# region: ex09_label
class Label(str, Enum):
    # Saved evidence from this run agrees with every part.
    VERIFIED = "verified"
    # Saved evidence says something the claim does not.
    CONTRADICTED = "contradicted"
    # Nothing saved can settle it either way.
    UNSUPPORTED = "unsupported"


Finding = namedtuple("Finding", "id text label note")
# endregion


def load(root):
    """The claims document and the evidence it points at."""
    root = Path(root)
    doc = json.loads((root / "claims.json").read_text())
    return doc, evidence(doc, root)


def evidence(doc, root):
    root = Path(root)
    log_path = root / doc.get("log", "run.jsonl")
    log = RunLog.load(log_path) if log_path.exists() else None
    return {"root": root, "run": doc["run"], "log": log}


# region: ex09_effects
def effects(log, action):
    """Per operation of `action`: its args and what the log proves."""
    out = {}
    for op in (log.ops() if log else []):
        events = log.for_op(op)
        intent = next((e for e in events if e["kind"] == "intent"),
                      None)
        if not intent or intent["action"] != action:
            continue
        result, detail = "unknown", None
        for e in events:
            if e["kind"] == "response" and e["ok"]:
                result, detail = "confirmed", e["receipt"]
                break
            if e["kind"] == "status" and e.get("found"):
                result, detail = "confirmed", e.get("receipt")
                break
            if e["kind"] == "response" and not e["ok"]:
                result, detail = "rejected", e.get("error")
        out[op] = {"args": intent["args"], "result": result,
                   "detail": detail}
    return out
# endregion


# region: ex09_descriptions
def check_descriptions(claim, ev):
    done = effects(ev["log"], "set_description").values()
    ok = {e["args"]["sku"] for e in done if e["result"] == "confirmed"}
    no = sorted({e["args"]["sku"] for e in done
                 if e["result"] == "rejected"} - ok)  # (1)
    n = claim["count"]
    if len(ok) == n:
        return Label.VERIFIED, f"{n} SKUs with receipts"
    if len(ok) > n:
        return Label.CONTRADICTED, f"{len(ok)} SKUs changed, not {n}"
    if no:
        return (Label.CONTRADICTED,
                f"{len(ok)} receipts; rejected: {', '.join(no)}")
    return Label.UNSUPPORTED, f"{len(ok)} receipts for {n} claimed"
# endregion


# region: ex09_refund
def check_refund(claim, ev):
    mine = {op: e for op, e in effects(ev["log"], "refund").items()
            if e["args"]["order"] == claim["order"]}
    paid = {e["detail"]["refund"]: e["detail"] for e in mine.values()
            if e["result"] == "confirmed"}  # (1)
    if len(paid) > 1:
        return (Label.CONTRADICTED,
                f"{len(paid)} refunds paid: {', '.join(paid)}")
    receipt = next(iter(paid.values()), None)
    if receipt and receipt["amount"] != claim["amount"]:
        return (Label.CONTRADICTED,
                f"receipt says {receipt['amount']}")
    keys = {e["args"].get("key") for e in mine.values()
            if e["result"] == "confirmed"} - {None}
    open_ = [op for op, e in mine.items() if e["result"] == "unknown"
             and e["args"].get("key") not in keys]  # (2)
    if receipt and open_:
        return (Label.UNSUPPORTED,
                f"{', '.join(open_)} unresolved; total unknown")
    if receipt:
        return Label.VERIFIED, f"receipt {receipt['refund']}"
    if any(e["result"] == "rejected" for e in mine.values()):
        return Label.CONTRADICTED, "the provider rejected it"
    return Label.UNSUPPORTED, "no receipt in the run log"  # (3)
# endregion


def check_email(claim, ev):
    mine = [e for e in effects(ev["log"], "send").values()
            if e["args"]["to"] == claim["to"]]
    if any(e["result"] == "confirmed" for e in mine):
        return Label.VERIFIED, "mailer returned a message id"
    if any(e["result"] == "rejected" for e in mine):
        return Label.CONTRADICTED, "the mailer rejected it"
    if mine:
        return Label.UNSUPPORTED, "sent, no receipt; outcome unknown"
    return Label.UNSUPPORTED, "no send in the run log"


# region: ex09_manifest
def digest(path):
    """First 16 hex digits of the file's SHA-256, or None."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def changed_since(root, lines):
    """Files the output lists as tested whose content is different
    now. A line reads: file: <path> <digest>."""
    tested = [ln.split()[1:3] for ln in lines
              if ln.startswith("file: ")]
    if not tested:
        return None  # (1)
    return [name for name, was in tested
            if digest(root / name) != was]  # (2)
# endregion


# region: ex09_tests
def check_tests(claim, ev):
    path = ev["root"] / claim["path"]
    if not path.exists():
        return Label.UNSUPPORTED, f"no {claim['path']}"
    lines = path.read_text().splitlines()
    out = dict(ln.split(": ", 1) for ln in lines if ": " in ln)
    if out.get("run") != ev["run"]:  # (1)
        return Label.UNSUPPORTED, f"output is from {out.get('run')}"
    changed = changed_since(ev["root"], lines)
    if changed is None:
        return Label.UNSUPPORTED, "output names no tested files"
    if changed:  # (2)
        return (Label.UNSUPPORTED,
                f"changed after the tests: {', '.join(changed)}")
    try:
        passed, failed = int(out["passed"]), int(out["failed"])
        code = int(out["exit"])
    except (KeyError, ValueError):
        return Label.UNSUPPORTED, "can't read the test output"
    if failed or code:
        return Label.CONTRADICTED, f"{failed} failed, exit {code}"
    if passed != claim["count"]:
        return (Label.CONTRADICTED,
                f"{passed} passed, not {claim['count']}")  # (3)
    return (Label.VERIFIED,
            f"{passed} passed in {ev['run']}, files unchanged")
# endregion


# region: ex09_file
def check_file(claim, ev):
    root = ev["root"].resolve()
    path = (root / claim["path"]).resolve()
    if root not in path.parents:
        return Label.UNSUPPORTED, "path is outside the evidence"
    if not path.exists():
        return Label.CONTRADICTED, f"no {claim['path']}"
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if "rows" in claim and len(rows) != claim["rows"]:
        return (Label.CONTRADICTED,
                f"{len(rows)} rows, not {claim['rows']}")
    per = claim.get("one_row_per")
    if not per:
        return Label.VERIFIED, f"exists, {len(rows)} rows"
    key = per["arg"]
    want = {e["args"][key]
            for e in effects(ev["log"], per["action"]).values()}
    if not want:  # (1)
        return Label.UNSUPPORTED, f"no {key}s in the run log"
    got = [r.get(key) or "" for r in rows]
    found = [(why, sorted(ks)) for why, ks in (
        ("repeated", {k for k in got if got.count(k) > 1}),  # (2)
        ("not in the run", set(got) - want),
        ("missing", want - set(got))) if ks]
    if found:
        return Label.CONTRADICTED, "; ".join(
            f"{why}: {', '.join(ks)}" for why, ks in found)
    return Label.VERIFIED, f"{len(rows)} rows, one per {key} in the run"
# endregion


# region: ex09_verify
CHECKS = {
    "descriptions_updated": check_descriptions,
    "refund_issued": check_refund,
    "email_sent": check_email,
    "tests_pass": check_tests,
    "file_written": check_file,
}


def verify(doc, ev):
    """One Finding per claim, in the order the agent made them."""
    found = []
    for c in doc["claims"]:
        fn = CHECKS.get(c["kind"])
        if fn is None:
            label, note = Label.UNSUPPORTED, "no check for this claim"
        else:
            label, note = fn(c, ev)  # (1)
        found.append(Finding(c["id"], c["text"], label, note))
    return found
# endregion


# region: ex09_report
def report(run, findings):
    """The handoff, rewritten as what the evidence supports."""
    count = {k: 0 for k in Label}
    for f in findings:
        count[f.label] += 1
    lines = [f"{run}: " + ", ".join(
        f"{count[k]} {k.value}" for k in Label)]
    for f in findings:
        lines.append(f"{f.label.value.upper():<13} {f.id}  {f.text}")
        lines.append(f"{'':<13} {'':<4}{f.note}")
    todo = len(findings) - count[Label.VERIFIED]
    lines.append("Done." if not todo else
                 f"Not done: {todo} of {len(findings)} claims need"
                 " a person.")
    return lines
# endregion


if __name__ == "__main__":
    # Run: python3 -m answers.ex09_verify_completion.solution
    here = Path(__file__).resolve().parents[2]
    doc, ev = load(here / "exercises/ex09_verify_completion/fixtures")
    print("\n".join(report(doc["run"], verify(doc, ev))))
