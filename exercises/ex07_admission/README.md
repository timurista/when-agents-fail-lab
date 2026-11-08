# Exercise 7: Admit results only while their goal is current

Chapter 7. Synthetic.

Fernhill Supply's merchandising lead asks the agent for a new description
of SKU-4471, then changes the brief while the first job is still
running. Every brief is a `Decision` that names the decision it
replaces; a cancel is a decision with no goal. Every job's `Result`
carries the id of the decision it was started for.

`lab/stale_results.py` has the model (`GoalBoard`, `View`, `decide`,
`view_state`), the replay harness, and two admission policies that are
wrong on purpose: `overwrite` and `check_then_write`. Read them first.
`fixtures/cases.json` holds eleven scripted cases with the state, the
active draft and the receipt labels each one should end with.

Write three functions in `starter.py`:

- `admit(board, view, result, pause=None)` calls `pause()` first if one
  is given, then checks the result's decision and updates the view in
  one step. It returns the label it gave the result:

  | label           | when                                                 |
  |-----------------|------------------------------------------------------|
  | `admitted`      | its decision is the current one; it becomes active   |
  | `superseded`    | its decision was replaced                            |
  | `cancelled`     | the goal for its key is cancelled                    |
  | `held_conflict` | its decision is one of competing heads; hold it      |
  | `duplicate`     | same id and same content as a result already kept    |
  | `rejected`      | same id, different content; or an unknown decision   |

  Keep every result with `view.keep(result, label)`. Put held results
  in `view.held[decision_id]`.
- `resolve(board, view, key, chosen)` records the choice on the board,
  makes the held result for `chosen` active and labels it `admitted`,
  and labels the other held results for the key `superseded`.
- `message(board, view, key)` returns what the screen says:
  - current: the draft's content
  - pending: "Updating for your new request (<new goal>)." and never
    the old draft
  - cancelled: says the rewrite was cancelled; mentions a draft that
    came back afterward; says cancelling doesn't undo a draft that was
    already applied. Never "stopped", "failed" or "error".
  - conflict: both goals, in an order that doesn't depend on which job
    finished first, and asks the user to pick one

Before you run the checks, predict the state and labels for the
`check-write-race` case under all three policies. Then:

    python3 -m lab check 07

When you have tried it once, `python3 -m lab reveal 07` shows the
reference answer.
