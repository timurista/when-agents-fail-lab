"""Exercise 11, reference answer."""
import json
import re
import sys
import textwrap

from lab import target

# region: ex11_happened
TOOL = {"storefront": "the storefront", "mailer": "the mailer",
        "payments": "the payment provider"}

HAPPENED = {
    "confirmed": "This landed: {what}.",
    "unknown": "We don't know if this landed: {what}.",
    "failed": "Not applied: {tool} rejected the {what} ({error}).",
    "canceled": "{tool} confirmed it will not apply the {what}.",
    "never_sent": "Never sent: {what}. It did not leave this system.",
}
# endregion


# region: ex11_next
def next_step(item):
    """The one thing an operator should do next, in plain words."""
    out, plan, tool = item["outcome"], item["plan"], TOOL[item["tool"]]
    if out == "unknown" and item["lookup"]:
        return (f"Ask {tool} for the status of {item['op']}. "
                "Don't resend until it answers.")
    if out == "unknown":  # (1)
        return (f"{tool.capitalize()} can't be asked. Confirm with "
                "the recipient, then record a decision and its reason.")
    if out == "failed":
        return f"Fix the cause ({item['error']}), then send again."
    if out == "canceled":
        return "Check what ran before the cancel. Resume if wanted."
    if out == "never_sent":
        return "Discard it, or resume it unchanged."
    if item["done"]:
        return "Nothing left to do for this step."
    if plan == "reverse":
        return f"Reverse it: {tool} puts back what it replaced."
    if plan == "compensate":  # (2)
        return ("Approve or decline a correction. It is a new "
                "message, and the recipient will see both.")
    if item["owner"]:
        return (f"Report it to {item['owner']}. It can't be taken "
                "back, and no correction is defined.")
    return "Inspect it. No recovery is planned for this step."
# endregion


# region: ex11_actions
def actions(item):
    """Every button, enabled or not. A disabled one says why."""
    out, tool = item["outcome"], TOOL[item["tool"]]
    settled_nothing = out in ("failed", "canceled", "never_sent")
    resend = {"label": "Resend", "enabled": settled_nothing,
              "reason": None}
    if out == "confirmed":
        resend["reason"] = "Already applied. Resending would repeat it."
    if out == "unknown":
        resend["reason"] = (f"No answer from {tool} yet. Resending "
                            "could apply it twice.")
    reverse = {"label": "Reverse", "reason": None, "enabled":
               out == "confirmed" and item["reversible"]
               and not item["done"]}
    if not reverse["enabled"]:
        reverse["reason"] = (
            "Nothing settled to reverse yet." if out == "unknown" else
            "Nothing was applied." if settled_nothing else
            "Already reversed." if item["done"] else
            f"{tool.capitalize()} has no way to take this back.")
    correct = {"label": "Send correction", "reason": None, "enabled":
               out == "confirmed" and item["plan"] == "compensate"
               and not item["done"]}
    if not correct["enabled"]:
        correct["reason"] = (
            "Wait for an answer first." if out == "unknown" else
            "Nothing was applied." if settled_nothing else
            "Not needed for this step.")
    return [resend, reverse, correct]
# endregion


def operator_message(item):
    """What happened, the evidence, the next step and the buttons."""
    happened = HAPPENED[item["outcome"]].format(
        **{**item, "tool": TOOL[item["tool"]]})
    return {"happened": happened[0].upper() + happened[1:],
            "evidence": item["evidence"] or "None yet.",
            "next": next_step(item), "actions": actions(item)}


# region: ex11_customer
CUSTOMER = {
    "confirmed": ("We've sent {thing}.",
                  "Reply to this email if you can't see it."),
    "unknown": ("We've asked {via} to send {thing}, and we're "
                "waiting for it to confirm.",
                "We'll email you when it does. You don't need to do "
                "anything."),
    "failed": ("{thing} didn't go through: {via} turned it down.",
               "We're fixing the cause and will email you when it's "
               "sent."),
    "canceled": ("We stopped {thing} before it was sent.",
                 "Reply to this email if you still want it."),
    "never_sent": ("We haven't sent {thing} yet.",
                   "We'll email you when we do."),
}


def customer_message(item):
    """None when the customer can't see this step at all."""
    if not item["customer"]:
        return None
    happened, nxt = CUSTOMER[item["outcome"]]
    text = happened.format(**item["customer"])
    return {"happened": text[0].upper() + text[1:], "next": nxt,
            "actions": []}
# endregion


# region: ex11_rules
BANNED = {
    "unknown-says-failed": (
        lambda i: i["outcome"] == "unknown",
        r"\bfail(ed|ure|s)?\b|\berror\b|\bunsuccessful\b"
        r"|\bdid(n't| not) go through\b|\brejected\b|\bdeclined\b"),
    "compensation-says-undo": (
        lambda i: i["plan"] == "compensate",
        r"\bundo(ne)?\b|\breverted\b|\brolled back\b|\bunsen[dt]\b"
        r"|\bretract(ed)?\b|\brecall(ed)?\b"),
    "stopped-without-ack": (
        lambda i: i["outcome"] != "canceled",
        r"\bstopped\b|\bcancel(l)?ed\b"),
}
INTERNAL = (r"\b(op|rcpt|rf|msg)-\w|\b[A-Z]+_[A-Z]+\b|\bUNKNOWN\b"
            r"|(?i:\bidempoten|\btime(d)? ?out\b|\bstatus lookup\b)")
VAGUE = r"^(try again( later)?|please wait|contact support" \
        r"|something went wrong|n/a)?\.?$"
# endregion


# region: ex11_lint
def lint(message, item, audience):
    """Problems with one message, as "rule: detail" strings."""
    words = " ".join(
        [message["happened"], message.get("evidence", ""),
         message["next"]]
        + [f"{a['label']} {a['reason'] or ''}"
           for a in message["actions"]])
    problems = []
    for rule, (applies, pattern) in BANNED.items():  # (1)
        hit = re.search(pattern, words, re.IGNORECASE)
        if applies(item) and hit:
            problems.append(f"{rule}: {hit.group(0)!r}")
    if re.match(VAGUE, message["next"].strip(), re.IGNORECASE):
        problems.append(f"no-next-step: {message['next']!r}")  # (2)
    for a in message["actions"]:
        if not a["enabled"] and not a["reason"]:
            problems.append(f"disabled-without-reason: {a['label']}")
        if a["enabled"] and a["label"] not in allowed(item):  # (3)
            problems.append(f"action-not-allowed: {a['label']}")
    if audience == "operator" and item["outcome"] == "confirmed" \
            and not item["evidence"]:
        problems.append("confirmed-without-evidence")
    if audience == "customer":
        hit = re.search(INTERNAL, words)  # (4)
        if hit:
            problems.append(f"internal-words: {hit.group(0)!r}")
    return problems


def allowed(item):
    """The buttons an outcome permits, from Chapter 3's rules."""
    out = item["outcome"]
    if out in ("failed", "canceled", "never_sent"):
        return {"Resend"}
    if out == "confirmed" and not item["done"]:
        return ({"Reverse"} if item["reversible"] else set()) | (
            {"Send correction"} if item["plan"] == "compensate"
            else set())
    return set()
# endregion


# region: ex11_render
def render(message, width=72):
    """Plain text: what happened, then what to do, then buttons."""
    lines = [message["happened"]]
    if "evidence" in message:
        lines.append(f"  Evidence: {message['evidence']}")
    lines.append(f"  Next: {message['next']}")
    for a in message["actions"]:
        state = "on " if a["enabled"] else "off"
        why = f": {a['reason']}" if a["reason"] else ""
        lines.append(f"  [{state}] {a['label']}{why}")
    return "\n".join(
        textwrap.fill(line, width, subsequent_indent="    ")
        for line in lines)
# endregion


def load_items():
    path = target.fixture("ex11_messages", "items.json")
    return json.loads(path.read_text())


if __name__ == "__main__":
    wanted = sys.argv[1:]
    for item in load_items():
        if not wanted or item["op"] in wanted:
            print(render(operator_message(item)) + "\n")
