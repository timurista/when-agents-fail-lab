# Exercise 2: The run log is evidence

Chapter 2. Synthetic.

The run log from Exercise 1 lived in memory. Here you put it on disk so
that a crash can't take it away, and you read it back the way a
restarted agent would.

Write these in `starter.py`:

- `op_id(task, step)`: the same task and step always give the same id.
- `DurableLog(path, crash_at=None)`: appends one JSON line per event,
  and the event is on disk before `record()` returns. Opening a log
  whose last line is torn cuts that line off first. It works with the
  lab's `call()` from Chapter 1 unchanged.
- `read_log(path)`: returns `(events, torn)`. A line counts only once
  its newline is on disk. An unreadable line before the last one
  raises `LogCorrupt`.
- `recover(path)`: returns `Recovery(outcomes, attention, torn)`, where
  `attention` holds every UNKNOWN and NEVER_SENT operation. It must not
  change the file.
- `resume(path, task, plan, tools)`: runs the plan again after a crash.
  It skips settled steps, resumes NEVER_SENT steps only if the request
  is unchanged, and never resends an UNKNOWN step.

`recover()` uses your `summarize()` from Exercise 1, so finish that
first.

Crash points are injected, not real: `crash_at=("after_sent", op)`
makes `point()` raise `Crash` at that spot. The checks crash every step
of a three-step run at every gap and then restart it.

Rules the checks enforce:

1. The log may over-report (UNKNOWN for a call that never happened). It
   must never under-report (NEVER_SENT for a call that did).
2. A restart applies nothing twice.
3. A torn last line is dropped and reported. A bad line anywhere else
   stops recovery.

Before you run the checks, predict the outcome each crash point leaves
behind. Then:

    python3 -m lab check 02

When you have tried it once, `python3 -m lab reveal 02` shows the
reference answer.
