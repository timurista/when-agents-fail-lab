# Exercise 10: Reverse, compensate, or leave it

Chapter 10. Synthetic.

Ticket T-2207 asked Fernhill's agent to refund order ORD-7713, apologize
to the buyer, put the products on hold and tell QA. The ticket said
ORD-7731. The agent ran the five steps in `lab/compensation.py` against
the wrong order, and one storefront write lost its reply, so the run
halted with the QA note unsent. You want to back the run out.

Write three functions in `starter.py`:

- `plan_step(step, outcome, receipt)` returns one plan item.
- `plan_recovery(log, steps)` returns a plan item per step, newest first.
- `apply_plan(plan, tools, log, approvals)` carries a plan out.

Rules the checks enforce:

1. Reverse only a CONFIRMED write on a tool that can reverse it, and
   only if nobody has changed the item since the write.
2. A CONFIRMED write that can't be reversed is compensated (a new
   action, from the step's `compensation`) or left and reported. A
   compensation needs an approval that matches its exact request.
3. UNKNOWN means wait. Never reverse or compensate an unknown.
4. FAILED, CANCELED and NEVER_SENT have no effect to undo: leave them.
5. Planning and applying twice must not reverse or compensate twice.
6. Every plan item says why.

Before you run the checks, write down what you expect for each of the
five steps. Then:

    python3 -m lab check 10

When you have tried it once, `python3 -m lab reveal 10` shows the
reference answer.
