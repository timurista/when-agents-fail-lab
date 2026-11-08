"""Exercise 2: a run log that survives a crash."""
from collections import namedtuple
from pathlib import Path

from lab import target
from lab.agent import call, request_hash
from lab.outcomes import Outcome
from lab.runlog import RunLog

# recover() classifies with your answer to Exercise 1.
ex01 = target.load("ex01_three_outcomes")


class Crash(Exception):
    """Injected by a test: the process died at this point."""


class LogCorrupt(Exception):
    """A line before the last one is unreadable."""


def op_id(task: str, step: int) -> str:
    """The op id for one step of one task, stable across restarts."""
    raise NotImplementedError("op_id")


class DurableLog:
    """A run log on disk, one JSON object per line."""

    def __init__(self, path, crash_at=None, clock=None):
        self.path = Path(path)
        self.crash_at = crash_at  # (point, op) or None
        self._clock = clock
        # Read what is already there. Cut a torn last line off.
        # Continue seq from the last complete event.
        raise NotImplementedError("DurableLog.__init__")

    def point(self, name: str, op) -> None:
        """A place the process could die. A test picks one."""
        if self.crash_at in {(name, op), (name, None)}:
            raise Crash(f"{name} {op}")

    def record(self, kind: str, op=None, **data) -> dict:
        """Append one event and make it durable before returning.

        Call self.point(f"before_{kind}", op) first and
        self.point(f"after_{kind}", op) last.
        """
        raise NotImplementedError("record")


def read_log(path):
    """(events, torn): every complete line, and a torn tail or None."""
    raise NotImplementedError("read_log")


Recovery = namedtuple("Recovery", "outcomes attention torn")


def recover(path) -> Recovery:
    """Read a log after a crash. Reads only; changes nothing."""
    raise NotImplementedError("recover")


def resume(path, task, plan, tools, crash_at=None) -> dict:
    """Run `plan` for `task`, skipping what the log says is settled."""
    raise NotImplementedError("resume")
