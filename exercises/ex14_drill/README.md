# Exercise 14: Run a recovery drill

Chapter 14. Synthetic. The capstone.

Fernhill Supply's operations agent was refunding three returned orders
(ORD-5103, ORD-5104, ORD-5105), emailing each customer and putting the
returned items back on sale, when an operator pressed Stop. Every tool
had a fault scheduled. `lab.drill.stage()` replays the run;
`fixtures/incident.jsonl` is the log it leaves.

You are the responder. Work through five stages in order, writing one
function for each in `starter.py`, and return a drill report from
`run_drill`:

1. **Classify** every operation from the log alone (`before`).
2. **Reconcile**: ask each tool that can answer about each UNKNOWN,
   record the answer in the log, and classify again (`after`).
3. **Decide** one action per operation, from `lab.drill.ACTIONS`.
4. **Message**: one line per operation and a headline for the run.
5. **Hand off**: the note the next owner reads first.

`lab.drill.score` grades the report. Its rules are public: read them.
The answer key (`fixtures/answer-key.json`) is the facilitator's. If
you are running this alone, don't open it until you have a score.

Rules the rubric enforces:

1. The stages are checked in order. The first one that fails is where
   your drill stalled.
2. Only evidence from the other system moves an operation out of
   UNKNOWN. A lookup miss is a failure only when the lookup is
   authoritative AND the protocol rules out a late apply
   (`miss_proves_failure`). Read `CAPABILITIES` for each tool.
3. Resuming or discarding an UNKNOWN operation is a critical failure,
   whatever the other stages say. So is resending one, unless its tool
   has an idempotency key that absorbs the repeat.
4. After your plan is carried out against the fake tools, no order may
   be refunded twice, no customer may get the same email twice, and
   no customer may be told about a refund that wasn't paid.
5. A pass is recorded as "recovered independently", or as "recovered
   with assistance" when the report lists any `assists`.
6. Messages name the outcome and the next step, and never say "failed"
   about something that didn't. The headline counts the unknowns.

Before you write code, fill in the drill sheet in Chapter 14 by hand:
your outcome for each of the seven operations, before and after
reconciling. Then:

    python3 -m lab check 14
    python3 -m lab.drill            # your scorecard

When you have tried it once, `python3 -m lab reveal 14` shows the
reference answer.
