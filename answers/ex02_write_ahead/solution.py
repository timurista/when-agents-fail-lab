"""Exercise 2, reference answer."""
import json
import os
from collections import namedtuple
from pathlib import Path

from lab import target
from lab.agent import call, request_hash
from lab.outcomes import Outcome
from lab.runlog import RunLog

# Classification is Exercise 1's job. With LAB_TARGET=solution this
# loads the reference answer; otherwise it loads your own.
ex01 = target.load("ex01_three_outcomes")


class Crash(Exception):
    """Injected by a test: the process died at this point."""


class LogCorrupt(Exception):
    """A line before the last one is unreadable."""


# region: ex02_op_id
def op_id(task: str, step: int) -> str:
    """The op id for one step of one task.

    Built only from things a restarted run still knows, so the
    restart asks about the same operation instead of starting a new
    one. Never use a timestamp, a random value or a counter here.
    """
    return f"op-{task}-{step}"
# endregion


# region: ex02_durable_log
class DurableLog:
    """A run log on disk, one JSON object per line.

    A record is durable when record() returns. Opening a log that
    ends in a torn line cuts that line off before anything is added.
    """

    def __init__(self, path, crash_at=None, clock=None):
        self.path = Path(path)
        self.crash_at = crash_at  # (point, op) or None
        self._clock = clock
        events, torn = read_log(self.path)
        if torn is not None:  # (1)
            size = self.path.stat().st_size
            os.truncate(self.path, size - len(torn))
        self._seq = events[-1]["seq"] if events else 0

    def point(self, name: str, op) -> None:
        """A place the process could die. A test picks one."""
        if self.crash_at in {(name, op), (name, None)}:
            raise Crash(f"{name} {op}")

    def record(self, kind: str, op=None, **data) -> dict:
        self.point(f"before_{kind}", op)
        self._seq += 1
        event = {"seq": self._seq, "kind": kind, "op": op}
        if self._clock is not None:
            event["t"] = self._clock.now()
        event.update(data)
        line = json.dumps(event, sort_keys=True) + "\n"  # (2)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()  # (3)
            os.fsync(f.fileno())  # (4)
        self.point(f"after_{kind}", op)
        return event
# endregion


# region: ex02_read_log
def read_log(path):
    """(events, torn): every complete line, and a torn tail or None.

    A line counts only once its newline is on disk. A missing or bad
    line anywhere before the last one is not a crash; it is damage,
    and recovery stops instead of guessing.
    """
    path = Path(path)
    if not path.exists():
        return [], None
    lines = path.read_bytes().split(b"\n")
    tail = lines.pop()  # (1)
    events = []
    for n, line in enumerate(lines, 1):
        try:
            events.append(json.loads(line))
        except ValueError:  # (2)
            raise LogCorrupt(f"{path}: line {n} is unreadable")
    return events, (tail or None)
# endregion


# region: ex02_recover
Recovery = namedtuple("Recovery", "outcomes attention torn")

NEEDS_ATTENTION = {Outcome.UNKNOWN, Outcome.NEVER_SENT}


def recover(path) -> Recovery:
    """Read a log after a crash. Reads only; changes nothing."""
    events, torn = read_log(path)
    log = RunLog()
    log.events = events
    outcomes = ex01.summarize(log)
    attention = {op: o for op, o in outcomes.items()
                 if o in NEEDS_ATTENTION}
    if torn is not None:
        torn = torn.decode("utf-8", errors="replace")
    return Recovery(outcomes, attention, torn)
# endregion


# region: ex02_resume
def resume(path, task, plan, tools, crash_at=None) -> dict:
    """Run `plan` for `task`, skipping what the log says is settled.

    plan is a list of (tool name, action, args). Returns {op: note}.
    """
    found = recover(path)
    intents = {e["op"]: e for e in read_log(path)[0]
               if e["kind"] == "intent"}
    log = DurableLog(path, crash_at=crash_at)
    notes = {}
    for step, (name, action, args) in enumerate(plan, 1):
        op = op_id(task, step)  # (1)
        outcome = found.outcomes.get(op)
        if outcome is None:
            call(log, tools[name], op, action, **args)
            notes[op] = "sent"
        elif outcome == Outcome.NEVER_SENT:
            wanted = request_hash(name, action, args)
            if intents[op]["request_hash"] != wanted:  # (2)
                notes[op] = "changed since the crash: review"
                continue
            call(log, tools[name], op, action, **args)
            notes[op] = "resumed"
        elif outcome == Outcome.UNKNOWN:
            notes[op] = "unknown: not resent"  # (3)
        else:
            notes[op] = f"settled: {outcome.value}"
    return notes
# endregion
