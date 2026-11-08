# Exercise 6: Two workers, one effect

Chapter 6. Synthetic.

Two copies of Fernhill Supply's catalog worker share a job queue. A
lease from `lab.leases.LeaseService` says which worker owns a job, and
for how long. Worker A takes the job for SKU-4471, then pauses for
longer than its lease. Worker B takes the job over. Then A wakes up.

There are no threads. Each function takes a `pause` hook that it calls
at a named point. The checks use the hook to move the `FakeClock` and
let the other worker act, so every interleaving is a repeatable script.

`naive_update` in `starter.py` is finished and deliberately wrong. It is
the control that proves the race happens. Write the other three:

- `fenced_update(store, lease, sku, text, pause)` writes through a
  `FencedStore` with the lease's token and returns `"written"` or
  `"fenced"`. It does not check the lease itself.
- `send_once(log, leases, claims, lease, mailer, op, to, subject, pause)`
  sends one email through the `Mailer`, which can't check a token.
- `late_sends(log)` lists ops whose `sent` event came at or after the
  expiry recorded in their `claim` event.

Rules for `send_once`, in order:

1. If the lease is not current, record a `fenced` event and return
   `"lost_lease"`. Then call `pause("after_check")`.
2. If `claims` (a `FencedStore` keyed by op) holds a claim with an older
   token, another worker may already have sent. Record `escalate` and
   return `"escalate"`. Never send on top of someone else's claim.
3. Write your claim to `claims` with your token. If the store refuses
   it, record `fenced` and return `"lost_lease"`.
4. Record a `claim` event with `holder`, `token` and `expires`, then
   call `pause("before_send")`, then send with `lab.agent.call`.
5. Return `"sent"` with a receipt, `"no_receipt"` without one.

One check shows the window that is left: a pause after the claim and
before the send. Nothing in `send_once` can close it. `late_sends` is
how you find it afterwards.

    python3 -m lab check 06

When you have tried it once, `python3 -m lab reveal 06` shows the
reference answer.
