# Exercise 1: Three outcomes, not two

Chapter 1. Synthetic.

An agent updated product descriptions for three SKUs and was stopped
partway. `fixtures/stop-run.jsonl` is its run log. `fixtures/mixed.jsonl`
holds six more operations, each ending a different way.

Write two functions in `starter.py`:

- `classify(events)` takes the events for one operation and returns an
  `Outcome`.
- `summarize(log)` returns `{op: Outcome}` for every operation in a
  `RunLog`.

Rules the checks enforce:

1. Only the other system can make an outcome CONFIRMED or FAILED: a
   receipt, an explicit rejection, or an authoritative status lookup.
2. A timeout, a Stop, or any amount of elapsed time never makes an
   outcome FAILED.
3. A request that was never sent is NEVER_SENT, not FAILED.
4. A recorded human decision settles an outcome, and only with a reason.

Before you run the checks, write down your prediction for each of the
nine operations. Then:

    python3 -m lab check 01

When you have tried it once, `python3 -m lab reveal 01` shows the
reference answer.
