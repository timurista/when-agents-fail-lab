"""An append-only record of what the agent did and what it was told.

Each event is a dict with at least `seq`, `t`, `kind` and `op`. The
kinds the lab uses:

  intent       about to call a tool: tool, action, args, request_hash
  sent         the request left this process
  response     the tool answered: ok (bool), receipt or error
  timeout      we stopped waiting; says nothing about the other side
  stop         the operator pressed Stop
  cancel_ack   the tool confirmed it will not apply the request
  status       a status lookup answered: found (bool), receipt
  decision     a human or policy resolved an outcome, with a reason
"""
import json
from pathlib import Path


# region: runlog
class RunLog:
    def __init__(self, clock=None):
        self.events = []
        self._clock = clock

    def record(self, kind: str, op: str | None = None, **data):
        event = {"seq": len(self.events) + 1, "kind": kind, "op": op}
        if self._clock is not None:
            event["t"] = self._clock.now()
        event.update(data)
        self.events.append(event)
        return event

    def for_op(self, op: str) -> list[dict]:
        return [e for e in self.events if e.get("op") == op]

    def ops(self) -> list[str]:
        seen = []
        for e in self.events:
            if e.get("op") and e["op"] not in seen:
                seen.append(e["op"])
        return seen
# endregion

    def save(self, path) -> None:
        lines = [json.dumps(e, sort_keys=True) for e in self.events]
        Path(path).write_text("\n".join(lines) + "\n")

    @classmethod
    def load(cls, path) -> "RunLog":
        log = cls()
        for line in Path(path).read_text().splitlines():
            if line.strip():
                log.events.append(json.loads(line))
        return log
