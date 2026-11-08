# Exercise 3: The return summary

Chapter 3. Synthetic.

An operator pressed Stop while an agent was working through seven
steps across the storefront, the payment provider and the mailer.
`fixtures/return-run.jsonl` is its run log. Build what the operator
sees when they come back: the local state once, then one card per
operation.

Write these in `starter.py`:

- `Runner.stop`, `Runner.submit` and `Runner.run`: a producer that
  drafts steps, sends them in order, and refuses new work once stopped.
- `allowed(outcome, reversible)`: the actions a card may offer.
- `evidence(events, outcome)` and `next_step(tool, op, outcome)`: the
  card's words.
- `return_summary(log)`: a `Summary(local, cards)`.
- `check(card, action)`: raises `Refused` with a reason when the action
  isn't open.

`return_summary()` uses your `summarize()` from Exercise 1, so finish
that first.

Rules the checks enforce:

1. "Stopped" describes the runner, once. It is never an operation's
   outcome.
2. Reverse is open only for a confirmed effect on a reversible tool. A
   confirmed effect that can't be reversed offers compensation instead.
3. An unknown operation offers one action: reconcile. Every refusal on
   it repeats the next evidence step.
4. Timeouts change nothing on a card.
5. After Stop, `submit()` raises `Stopped` and nothing new is sent.

Before you run the checks, write down the actions you expect on each of
the seven cards. Then:

    python3 -m lab check 03

When you have tried it once, `python3 -m lab reveal 03` shows the
reference answer.
