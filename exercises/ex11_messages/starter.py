"""Exercise 11: messages generated from outcomes, and a wording lint."""
import json  # noqa: F401
import re  # noqa: F401
import textwrap  # noqa: F401

from lab import target  # noqa: F401


def operator_message(item):
    """{"happened", "evidence", "next", "actions"} for an operator.
    Each action is {"label", "enabled", "reason"}; labels are
    "Resend", "Reverse" and "Send correction"."""
    raise NotImplementedError("operator_message")


def customer_message(item):
    """{"happened", "next", "actions": []} for the customer, or None
    when item["customer"] is empty."""
    raise NotImplementedError("customer_message")


def lint(message, item, audience):
    """A list of "rule: detail" strings; [] when the message is clean.
    Rules: unknown-says-failed, compensation-says-undo,
    stopped-without-ack, no-next-step, disabled-without-reason,
    action-not-allowed, confirmed-without-evidence, internal-words."""
    raise NotImplementedError("lint")


def render(message, width=72):
    """Plain text, every line at most `width` columns."""
    raise NotImplementedError("render")
