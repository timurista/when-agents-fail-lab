# Exercise 13: Every failure becomes a test

Chapter 13. Synthetic.

Fernhill Supply's return workflow refunds an order (payments), emails
the customer (mailer) and marks the item back in stock (storefront).
`starter.py` gives you three versions of it:

- `process_return_naive`, the version that refunded ORD-5531 twice.
- `process_return_v1`, a first fix: an idempotency key and a lookup.
- `process_return`, the version the checks expect to hold.
- `process_return_empty`, a control that does nothing at all.

It also gives you `run(workflow, schedule)`, which runs a workflow once
on fresh fake tools and a fake clock, then lets queued work land.
A schedule is a dict of fault tuples, one fault per call, per tool:

    {"payments": (Fault.LOST_REPLY, Fault.NONE, Fault.NONE),
     "mailer": (Fault.NONE,), "storefront": (Fault.NONE,)}

`fixtures/incident-ord-5531.jsonl` is the naive version's run log from
the incident.

Write seven functions in `starter.py`:

- `schedules(shape)` yields every schedule for a shape such as
  `{"payments": 3, "mailer": 1, "storefront": 1}`: one fault from
  `Fault` for each call, every combination, in `itertools.product`
  order.
- `check_invariants(result)` returns the sorted names of the rules a
  run broke: `doubled_refund`, `doubled_email`,
  `unknown_marked_failed` (the report says FAILED and the log doesn't),
  `applied_marked_failed` (the report says FAILED and the tool applied
  it) and `expired_approval` (a refund op was sent at or after the
  approval's `expires_at`; refund ops start with `op-refund`).
- `explore(workflow, shape)` returns `(schedule, broken)` for every
  schedule that breaks at least one rule.
- `reaches_goal(result)` returns True when the run's fake tools show
  the goal: exactly one refund paid, exactly one email sent, and the
  SKU's text set to "Back in stock".
- `assess(workflow, shape)` returns `{"unsafe": ..., "completes": ...}`:
  `explore`'s list, and whether the workflow reaches its goal under
  the schedule with no faults at all.
- `consistent_faults(log)` returns `{tool: [faults, ...]}` with one
  tuple per sent call, in `Fault` order: the faults that could have
  produced what the log shows after that `sent`.
- `incident_schedules(log)` yields every schedule built from those
  tuples.

Rules the checks enforce:

1. A run is a function of its schedule: same schedule, same log.
2. A timeout fits three faults. The log can't say which, so a test
   built from it must try all three.
3. Safety and completion are separate results. The do-nothing control
   breaks no safety rule under any schedule and never reaches the goal.
4. A regression test passes on the fixed code and fails on the code
   that caused the incident.

Then:

    python3 -m lab check 13
    PYTHONPATH=. python3 exercises/ex13_fault_schedules/starter.py

When you have tried it once, `python3 -m lab reveal 13` shows the
reference answer.
