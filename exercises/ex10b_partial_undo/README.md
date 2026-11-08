# Exercise 10b: Keep what the kept work needs

Chapter 10, optional. Synthetic.

Fernhill's agent built an ops dashboard in run-1108: a rule named
`late-orders`, a widget that uses the rule by name, and a dashboard that
holds the widget. Before anyone backed the run out, a colleague edited the
widget. Chapter 10's rule says to keep anything changed since the run. So
the widget stays. What about the rule it uses?

`lab/undo_workspace.py` holds the model, six fixtures and
`object_by_object`, which applies Chapter 10's rule one object at a time.
It is the control: it keeps the edited widget and removes the rule, and
the widget is left pointing at nothing.

Write three functions in `starter.py`:

- `plan(ws, run)` returns what to remove and what to keep, each with a
  reason.
- `execute(p, ws)` carries out a plan.
- `report(p)` turns a plan into lines a person reads.

Rules the checks enforce:

1. Remove only what the run created. Never touch what existed before.
2. Keep anything that changed since the run.
3. Keep everything a kept object uses, and what that uses in turn. Every
   object that existed before the run counts as kept.
4. Say which reason applies: "changed since the run" and "needed by W1"
   are different reasons.
5. A name that matches more than one object is not a guess. Keep the
   run's candidate and list the name as unresolved, with every match.
6. A plan records the state it was made against. If that state changed,
   `execute` refuses and removes nothing.
7. Remove users before the things they use. Running it twice removes
   nothing more.
8. Run-created objects that use each other in a loop are out of scope:
   plan nothing and say "cycle: unsupported".

Before you run the checks, write the report you expect for the edited
widget: one line per object, with its reason. Then:

    python3 -m lab check 10b

The checks show the control's failure first, then test yours against six
fixtures. One fixture has two rules with the same name, and there the
control's result looks fine: nothing dangles. Work out why that's worse
before you read the check.

When you have tried it once, `python3 -m lab reveal 10b` shows the
reference answer.
