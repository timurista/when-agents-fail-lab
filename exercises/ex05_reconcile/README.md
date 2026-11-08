# Exercise 5: Reconcile from evidence

Chapter 5. Synthetic.

Fernhill is moving order status from its legacy orders store to a
projection in a new service. `lab/stores.py` writes every change to
both, as two commits, and can die between them. `fixtures/cutover.json`
holds six orders already in both stores and four operations.
`lab.stores.pair_check` is the validation that only compares rows
present in both. The checks show where it goes blind.

Write two functions in `starter.py`:

- `audit(legacy, projection)` starts from every order in legacy (the
  source of truth) and returns lists `matched`, `mismatched` (status or
  version differ), `missing`, and `orphans` (in the projection only),
  plus `expected` (a count) and `ok`.
- `reconcile(legacy, projection)` finishes projection writes that an
  unprojected intent in legacy says are owed.

Rules the checks enforce:

1. `ok` is true only when every expected order matched and there are
   no orphans. Zero mismatches is not enough.
2. Repair only from an intent. A missing row with no intent stays
   missing, and the audit keeps reporting it.
3. Never write over a projection row whose version is the same or
   newer with a different value. Report a conflict and leave the
   intent unprojected.
4. If the projection already has the op (in `applied_ops`, or the same
   status and version), mark the intent projected and write nothing.
5. Repair at most once: a second run makes no writes.
6. If either store can't be read, write nothing and say which.

Before you run the checks, predict what `pair_check` and your `audit`
report after a crash right after `op-17`, and after one right after
`op-14`. Then:

    python3 -m lab check 05

When you have tried it once, `python3 -m lab reveal 05` shows the
reference answer.
