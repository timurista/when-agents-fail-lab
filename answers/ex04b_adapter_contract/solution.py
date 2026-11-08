"""Exercise 4b, reference answer."""
from lab.outcomes import Outcome

# region: ex04b_contract
# What the synthetic provider's docs promise. For a real provider,
# each entry needs a doc reference and a test against its sandbox.
CONTRACT = {
    "key_retention_s": 24 * 3600,   # keys and results kept this long
    "lookup_authoritative": False,  # a 404 may mean "not yet"
}
# endregion


# region: ex04b_steps
def unknown_steps(key_age_s, contract, provider_has_it=False):
    """What may follow UNKNOWN. A resend needs a key the provider
    still remembers, and is pointless once the provider has the
    request. Past retention the key answers nothing: escalate."""
    if key_age_s >= contract["key_retention_s"]:
        return frozenset({"escalate"})
    steps = {"lookup", "escalate"}
    if not provider_has_it:
        steps.add("resend_same_key")
    return frozenset(steps)
# endregion


# region: ex04b_send
def adapt_send(raw, key_age_s, contract=CONTRACT):
    """Map one raw reply to a refund request: (outcome, steps)."""
    if raw is None or raw["status"] >= 500:  # (1)
        return Outcome.UNKNOWN, unknown_steps(key_age_s, contract)
    body = raw.get("body") or {}
    if raw["status"] == 200 and body.get("refund_id"):
        return Outcome.CONFIRMED, frozenset({"record"})
    if raw["status"] == 202:  # (2)
        return Outcome.UNKNOWN, unknown_steps(
            key_age_s, contract, provider_has_it=True)
    if 400 <= raw["status"] < 500 and body.get("error"):  # (3)
        return Outcome.FAILED, frozenset({"send_again"})
    return Outcome.UNKNOWN, frozenset({"escalate"})  # (4)
# endregion


# region: ex04b_lookup
def adapt_lookup(raw, key_age_s, contract=CONTRACT):
    """Map one raw reply to a lookup by key: (outcome, steps)."""
    if raw is None or raw["status"] >= 500:
        return Outcome.UNKNOWN, unknown_steps(key_age_s, contract)
    body = raw.get("body") or {}
    state = body.get("state")
    if raw["status"] == 200 and state == "succeeded" \
            and body.get("refund_id"):
        return Outcome.CONFIRMED, frozenset({"record"})
    if raw["status"] == 200 and state == "failed":
        return Outcome.FAILED, frozenset({"send_again"})
    if raw["status"] == 200 and state == "pending":
        return Outcome.UNKNOWN, unknown_steps(
            key_age_s, contract, provider_has_it=True)
    if raw["status"] == 404:
        trusted = (contract["lookup_authoritative"]
                   and key_age_s < contract["key_retention_s"])
        if trusted:
            return Outcome.FAILED, frozenset({"send_again"})
        return Outcome.UNKNOWN, unknown_steps(key_age_s, contract)
    return Outcome.UNKNOWN, frozenset({"escalate"})
# endregion
