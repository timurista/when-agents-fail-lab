# Exercise 11: Telling people what happened

Chapter 11. Synthetic.

`fixtures/items.json` holds seven steps from Fernhill's ticket T-2207
and the follow-up run, each with its outcome, its evidence and its
recovery plan from Exercise 10. `fixtures/bad-messages.json` holds
eight messages someone wrote by hand, each wrong in one way.

Write four functions in `starter.py`:

- `operator_message(item)`: what happened, the evidence, the next step
  and every button, enabled or not.
- `customer_message(item)`: what happened and what happens next, in
  words a customer can use, or None for steps the customer can't see.
- `lint(message, item, audience)`: the rules a message breaks.
- `render(message)`: plain text within 72 columns.

Rules the checks enforce:

1. An UNKNOWN outcome is never described as failed, an error or
   rejected.
2. A compensation is never described as undo, unsent or recalled.
3. "Stopped" and "canceled" are only for a CANCELED outcome.
4. Every message names a next step, and "Please wait" is not one.
5. Every disabled button says why; no button is enabled that the
   outcome doesn't allow.
6. An operator message for a CONFIRMED step cites its evidence.
7. A customer message has no operation ids, receipt ids, enum names or
   words like "timeout".

Your generated messages must pass your own lint, and your lint must
catch every message in the bad fixture. Then:

    python3 -m lab check 11

When you have tried it once, `python3 -m lab reveal 11` shows the
reference answer.
