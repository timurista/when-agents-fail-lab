"""Exercise 9: check each claim in a handoff against saved evidence."""
import csv  # noqa: F401
import hashlib
import json
from collections import namedtuple
from enum import Enum
from pathlib import Path

from lab.runlog import RunLog


class Label(str, Enum):
    # Saved evidence from this run agrees with every part.
    VERIFIED = "verified"
    # Saved evidence says something the claim does not.
    CONTRADICTED = "contradicted"
    # Nothing saved can settle it either way.
    UNSUPPORTED = "unsupported"


Finding = namedtuple("Finding", "id text label note")


# Given: loading, and reading effects out of the run log.

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


def digest(path):
    """First 16 hex digits of the file's SHA-256, or None."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# Given: one check, as a worked example.

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


# Yours. Each check returns (Label, note). Keep notes short.

def check_descriptions(claim, ev):
    """claim: {"count": n}. Compare with set_description receipts."""
    raise NotImplementedError("check_descriptions")


def check_refund(claim, ev):
    """claim: {"order", "amount"}. Compare with refund receipts.
    Count refunds by the provider's refund id, not by attempts. An
    unresolved attempt the confirmed key doesn't cover leaves the
    total unsupported."""
    raise NotImplementedError("check_refund")


def check_tests(claim, ev):
    """claim: {"path", "count"}. Read the saved test output. Its
    "file: <path> <digest>" lines say what the tests ran against."""
    raise NotImplementedError("check_tests")


def check_file(claim, ev):
    """claim: {"path", "rows"?, "one_row_per"?}. Look at the file.
    one_row_per: {"action", "arg"}: the expected keys are that arg
    of every operation of that action in the run log."""
    raise NotImplementedError("check_file")


CHECKS = {
    "descriptions_updated": check_descriptions,
    "refund_issued": check_refund,
    "email_sent": check_email,
    "tests_pass": check_tests,
    "file_written": check_file,
}


def verify(doc, ev):
    """One Finding per claim, in the order the agent made them."""
    raise NotImplementedError("verify")


def report(run, findings):
    """Lines of text: a count line, two lines per claim, a verdict."""
    raise NotImplementedError("report")


if __name__ == "__main__":
    # Run: python3 -m exercises.ex09_verify_completion.starter
    here = Path(__file__).resolve().parents[2]
    doc, ev = load(here / "exercises/ex09_verify_completion/fixtures")
    print("\n".join(report(doc["run"], verify(doc, ev))))
