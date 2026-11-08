# Exercise 8: Approvals that expire and recipients that change

Chapter 8. Synthetic.

Fernhill Supply's operations agent asks a person before it refunds an
order or emails a customer. In the run this exercise is built on, the
operator approved a refund and an apology email at the same time. The
refund went out. Before the email went out, the agent resolved the
customer's address again and got a different one.

Write six functions in `starter.py`:

- `grant(clock, tool, action, args, by, ttl)` records an approval for
  one exact request, bound to `lab.agent.request_hash` and an expiry.
- `check(approval, tool, action, args, now, spent)` says whether the
  approval covers this request at this moment, and if not, why.
- `act(log, tool, op, action, approval, clock, spent, **args)` checks
  at the moment of sending, then sends through `lab.agent.call`.
- `consume(spent_dir, approval_id)` spends an approval on disk, so
  the spend survives a restart.
- `renew(old, args, clock, by, ttl)` makes a new approval for a
  changed request.
- `explain(approval, verdict)` words a refusal for the approver.

Rules the checks enforce:

1. An approval covers one request hash. Any change to the tool, the
   action or any argument (order, amount, recipient, subject, text)
   means it no longer applies.
2. Expiry is checked on the FakeClock at the moment of action, not
   when the plan was made. An approval is expired when now is equal
   to or later than `expires_at`.
3. An approval is spent the first time it is used, before the request
   is sent. A second request on it is refused.
4. A refusal sends nothing and records why in the run log.
5. Only a person can grant or renew. The agent can't approve itself.
6. A renewed approval is a new record. It never widens the old one.
7. `act` keeps its spent set in memory, which a restart loses.
   `consume` records the spend in one step that both checks and
   records it: it creates a marker file only if none exists, flushes
   it, and returns False when the approval was already spent.

Amounts are in cents. Email addresses use the reserved example.com and
example.net domains.

    python3 -m lab check 08

When you have tried it once, `python3 -m lab reveal 08` shows the
reference answer.
