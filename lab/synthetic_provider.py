"""Raw replies from a synthetic refunds API, for exercise 4b.

No real provider is modelled here. The status codes, field names and
states are invented so that an adapter has something concrete to map.
A real provider's replies, and what they mean, come from its own
documentation and its own test environment, not from this file.
"""

# region: provider_replies
# Replies to POST /refunds (key sent in a header). None: no reply
# arrived before our deadline.
SEND = {
    "paid":     {"status": 200, "body": {"state": "succeeded",
                                         "refund_id": "rf-7001"}},
    "accepted": {"status": 202, "body": {"state": "pending"}},
    "declined": {"status": 422, "body": {"error": "over_refund"}},
    "gateway":  {"status": 504, "body": None},
    "timeout":  None,
}

# Replies to GET /refunds?key=... after an unanswered send.
LOOKUP = {
    "found":     {"status": 200, "body": {"state": "succeeded",
                                          "refund_id": "rf-7001"}},
    "pending":   {"status": 200, "body": {"state": "pending"}},
    "failed":    {"status": 200, "body": {"state": "failed",
                                          "error": "over_refund"}},
    "not_found": {"status": 404, "body": {"error": "no_such_key"}},
}
# endregion
