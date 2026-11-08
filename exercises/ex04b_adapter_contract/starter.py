"""Exercise 4b: map a synthetic provider's replies to outcomes."""
from lab.outcomes import Outcome  # noqa: F401

# What the synthetic provider's docs promise. For a real provider,
# each entry needs a doc reference and a test against its sandbox.
CONTRACT = {
    "key_retention_s": 24 * 3600,   # keys and results kept this long
    "lookup_authoritative": False,  # a 404 may mean "not yet"
}


def adapt_send(raw, key_age_s, contract=CONTRACT):
    """Map one raw reply to a refund request: (outcome, steps).
    See README.md for the rules."""
    raise NotImplementedError("adapt_send")


def adapt_lookup(raw, key_age_s, contract=CONTRACT):
    """Map one raw reply to a lookup by key: (outcome, steps)."""
    raise NotImplementedError("adapt_lookup")
