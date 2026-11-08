# Exercise 12: A handoff note from the log

Chapter 12. Synthetic.

Fernhill Supply's operations agent was processing a return for order
ORD-5531 when its token budget ran out. `fixtures/paused-return.jsonl`
is its run log. Besides the usual tool events it holds four new kinds:

  goal     what finished looks like (text)
  claim    something the agent asserted: text, subject, and evidence,
           the seq of the event that backs it (or null)
  change   someone outside the run changed a subject
  pause    the run stopped because the assistant went away

`starter.py` gives you `evidence_for` (Chapter 1's classifier, which
also returns the event that decided the outcome) and `render`. Write:

- `check_claims(log)` returns `{"current": [...], "stale": [...],
  "unsupported": [...]}`. Each entry is a dict with `claim` (the text);
  current and stale entries also carry `evidence` (a seq), and stale
  entries carry `changed`, the seq of the first later change.
- `next_action(unknown, claims, unfinished)` returns one dict with
  `kind`, `target` and `text`.
- `do_not(settled, unknown, claims, unfinished)` returns a list of
  `{"target", "why"}` dicts (plus `until` for `after_unknown`).
- `handoff(log)` returns the note: `goal`, `paused`, `settled`,
  `unknown`, `unfinished`, `stale`, `unsupported`, `next_action`,
  `do_not`. Entries in `settled`, `unknown` and `unfinished` carry
  `op`, `tool`, `action` and `seq` (the intent's seq); settled entries
  add `outcome` and `evidence` (the seq of the deciding event).

Rules the checks enforce:

1. Every settled line points at the event that proves it, and that
   event belongs to the same operation.
2. A claim is stale when a change to its subject has a higher seq than
   its evidence. Order in the log decides, not timestamps.
3. A claim that cites no event, or an event that isn't in the log, is
   unsupported.
4. Next action, in this order: ask about the first unknown operation
   (`ask` if its tool has a lookup, `escalate` if not); then `recheck`
   the first stale or unsupported claim; then `decide` on the first
   never-sent operation; otherwise `close`.
5. Do-not reasons: `unknown` for every unknown op; `after_unknown` for
   a never-sent op planned after an unknown one; `confirmed` and
   `failed` for settled ops; `stale` and `unsupported` for claims.
6. Following the note never resends an unknown operation.

Before you run the checks, write your own note for the fixture by
hand. Then:

    python3 -m lab check 12

When you have tried it once, `python3 -m lab reveal 12` shows the
reference answer.
