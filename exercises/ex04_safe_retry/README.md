# Exercise 4: Retry without doubling

Chapter 4. Synthetic.

Fernhill's agent issues a refund for order O-5520, updates a product
description, and emails the customer. Any of those calls can time out.
Write a retry that settles the unanswered ones by asking, and refuses
to guess where it can't ask.

Write three functions in `starter.py`. `CAPABILITIES` is given.

- `backoff(attempt)` returns the wait before retry `attempt`: 1, 2, 4,
  8 seconds and so on, never more than 30. No randomness.
- `ask(log, tool, op, args)` asks the tool whether the operation
  happened (Payments: `lookup(key)`; Storefront: `status(op)`; Mailer:
  it can't be asked). Record a `status` event with `found`, `receipt`
  and `authoritative=False`, and return the receipt or None.
- `retry_safely(log, tool, op, action, args, clock, attempts=3)`
  returns `(outcome, receipt)`.

Rules the checks enforce:

1. Every send goes through `lab.agent.call`, so the log sees it.
2. Before any resend, wait with `clock.advance(backoff(n))` and ask.
   If the answer is a receipt, stop: the outcome is CONFIRMED.
3. Resend only if the tool dedupes by key or a repeat is harmless.
   Every resend uses the same arguments, including the same key.
   A keyed tool called without a key raises ValueError.
4. A tool you can neither ask nor safely resend (the Mailer) is never
   sent twice. Record an `escalate` event with a reason and return
   UNKNOWN.
5. A rejection of the first send is FAILED. A rejection of a resend
   is not: an earlier attempt may still apply. Escalate.
6. Out of attempts: escalate. Never sleep for real.

The checks run every combination of faults across three calls (125
schedules) and assert that Payments never pays twice. One more check
runs the same schedule against a blind retry loop and expects it to
pay twice, so you can see the test has teeth.

    python3 -m lab check 04

When you have tried it once, `python3 -m lab reveal 04` shows the
reference answer.
