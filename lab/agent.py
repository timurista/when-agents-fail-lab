"""The one way exercises call a tool: through the run log."""
import hashlib
import json

from .tools import ToolRejected, ToolTimeout


def request_hash(tool: str, action: str, args: dict) -> str:
    body = json.dumps([tool, action, args], sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# region: call
def call(log, tool, op, action, **args):
    """Call `tool.action`, recording intent before and outcome after.

    Returns the receipt, or None when there is no receipt. None does
    not mean failed: read the log to see why there is no receipt.
    """
    log.record("intent", op, tool=tool.name, action=action, args=args,
               request_hash=request_hash(tool.name, action, args))
    log.record("sent", op)
    try:
        receipt = getattr(tool, action)(op, **args)
    except ToolTimeout:
        log.record("timeout", op)
        return None
    except ToolRejected as err:
        log.record("response", op, ok=False, error=str(err))
        return None
    log.record("response", op, ok=True, receipt=receipt)
    return receipt
# endregion
