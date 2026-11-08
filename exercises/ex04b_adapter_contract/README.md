# Exercise 4b: An adapter contract

Chapter 4. Synthetic.

The lab's fake tools raise `ToolTimeout` and `ToolRejected`. A real
provider sends status codes and bodies. Between the two sits an
adapter, and the adapter is where "202" becomes a recovery decision.

`lab/synthetic_provider.py` holds raw replies from an invented refunds
API: `SEND` for refund requests, `LOOKUP` for lookups by key. No real
provider is modelled. `CONTRACT` in `starter.py` is what that invented
provider's docs promise: how long it keeps keys, and whether a 404
from its lookup can be trusted.

Write two functions in `starter.py`. Each takes one raw reply (or
None for "no reply before our deadline") and the age of the key in
seconds, and returns `(Outcome, steps)`, where steps is a frozenset
drawn from:

    record           keep the receipt; nothing more to do
    send_again       a new request, after fixing what was rejected
    lookup           ask by key
    resend_same_key  send again with the same key
    escalate         hand it to a person, with a reason

Rules the checks enforce:

1. No reply, or any 5xx, is UNKNOWN. A gateway's 504 is not the
   provider saying no.
2. A 200 with a refund id is CONFIRMED: `{"record"}`.
3. A 4xx with an error body is FAILED: `{"send_again"}`. (This maps
   one reply. Whether a rejected *resend* settles the operation is
   `retry_safely`'s job, as in exercise 4.)
4. A 202, or a lookup that says "pending", is UNKNOWN, but the
   provider has the request: lookup or escalate, never resend.
5. A lookup 404 is FAILED only if the contract says the lookup is
   authoritative and the key is still inside retention. Otherwise it
   is UNKNOWN.
6. UNKNOWN allows `resend_same_key` only while the key is younger than
   `key_retention_s`. Past that, the provider would treat the resend as
   new, and a lookup can't answer: the only step is `escalate`.
7. Anything you don't recognize is UNKNOWN with `{"escalate"}`. An
   adapter must not guess.

What the checks prove: your mapping follows the contract. What they
can't prove: that the contract is true of any real provider. That
comes from the provider's documentation and from tests against its
own test environment.

    python3 -m lab check 4b

When you have tried it once, `python3 -m lab reveal 4b` shows the
reference answer.
