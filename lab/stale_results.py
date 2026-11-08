"""Goal versions, results that arrive late, and the view they update.

Every job is started for a decision: the user's goal at that moment.
A correction or a cancel is a new decision that names the one it
replaces. The board (the authority) orders decisions by those links,
never by timestamps. A result carries the id of the decision its job
was started for, and an admission policy decides what the view shows.

The two policies in this module are controls. They are wrong on
purpose, so the tests can prove the failures they let through.
"""
import json
from dataclasses import dataclass
from pathlib import Path


# region: decision
@dataclass(frozen=True)
class Decision:
    id: str                 # e.g. "g2"
    key: str                # what it decides, e.g. "SKU-4471"
    goal: str | None        # the brief; None means cancel
    replaces: str | None = None


@dataclass(frozen=True)
class Result:
    id: str                 # the worker's completion id
    decision: str           # the decision its job was started for
    key: str
    content: str
# endregion


# region: board
class GoalBoard:
    """The authority: every decision it has received, and the links."""

    def __init__(self):
        self.decisions = {}
        self.dropped = set()   # heads set aside by a resolution

    def record(self, d: Decision) -> None:
        self.decisions[d.id] = d

    def heads(self, key: str) -> list[str]:
        """Decisions for `key` that nothing has replaced."""
        mine = [d for d in self.decisions.values() if d.key == key]
        replaced = {d.replaces for d in mine} | self.dropped
        return sorted(d.id for d in mine if d.id not in replaced)

    def state(self, key: str) -> tuple[str, list[str]]:
        heads = self.heads(key)
        if not heads:
            return "empty", []
        if len(heads) > 1:
            return "conflict", heads  # (1)
        if self.decisions[heads[0]].goal is None:
            return "cancelled", heads
        return "current", heads

    def is_current(self, decision_id: str) -> bool:
        d = self.decisions.get(decision_id)
        return d is not None and self.state(d.key) == (
            "current", [decision_id])
# endregion

    def resolve(self, key: str, chosen: str) -> None:
        """Set aside every competing head except `chosen`."""
        status, heads = self.state(key)
        if status != "conflict" or chosen not in heads:
            raise ValueError(f"nothing to resolve to {chosen}")
        self.dropped.update(h for h in heads if h != chosen)


class View:
    """What the product shows, and a receipt for every result."""

    def __init__(self):
        self.active = {}     # key -> Result the screen may show
        self.held = {}       # decision id -> Result waiting on a choice
        self.results = {}    # result id -> first Result with that id
        self.labels = {}     # result id -> receipt label
        self.history = []    # (Result, label) for every arrival

    def keep(self, result: Result, label: str) -> str:
        self.history.append((result, label))
        if result.id not in self.labels:
            self.results[result.id] = result
            self.labels[result.id] = label
        return label


# region: view_state
def decide(board, view, d: Decision) -> None:
    """Record a decision, and in the same step clear an active result
    that no longer answers the current decision."""
    board.record(d)
    active = view.active.get(d.key)
    if active is not None and not board.is_current(active.decision):
        del view.active[d.key]


def view_state(board, view, key) -> tuple[str, Result | None]:
    """current, pending, cancelled, conflict or empty, and what to show.

    Reads what admission stored. It does not re-check the result's
    decision, so whatever a policy let in is what the screen shows.
    """
    status, _ = board.state(key)
    if status != "current":
        return status, None
    active = view.active.get(key)
    return ("current", active) if active else ("pending", None)
# endregion


# region: overwrite
def overwrite(board, view, result, pause=None):
    """Control 1: the newest arrival wins."""
    if pause:
        pause()
    view.active[result.key] = result
    return view.keep(result, "admitted")
# endregion


# region: check_then_write
def check_then_write(board, view, result, pause=None):
    """Control 2: check, then write after a pause, never rechecking."""
    ok = (result.id not in view.results
          and board.is_current(result.decision))
    if pause:
        pause()  # (1)
    if not ok:
        return view.keep(result, "superseded")
    view.active[result.key] = result  # (2)
    return view.keep(result, "admitted")
# endregion


def load_cases(path) -> list[dict]:
    return json.loads(Path(path).read_text())


def replay(case: dict, admit, resolve=None):
    """Run one scripted case through a policy. Returns (board, view).

    Steps:
      ["decide", {decision}]
      ["arrive", {result}]
      ["arrive", {result}, {decision}]  the decision lands during the
                                        policy's pause
      ["resolve", key, chosen]
    """
    board, view = GoalBoard(), View()
    for step in case["steps"]:
        if step[0] == "decide":
            decide(board, view, Decision(**step[1]))
        elif step[0] == "arrive":
            result = Result(**step[1])
            pause = None
            if len(step) > 2:
                late = Decision(**step[2])
                pause = lambda late=late: decide(board, view, late)
            admit(board, view, result, pause=pause)
        elif step[0] == "resolve":
            if resolve is not None:
                resolve(board, view, step[1], step[2])
            else:
                board.resolve(step[1], step[2])
    return board, view
