"""Exercise 7: admit results only while their goal is current."""
from lab.stale_results import view_state


def admit(board, view, result, pause=None):
    """Check the result's decision and update the view in one step.

    Call pause() first if one is given. Return the receipt label:
    admitted, superseded, cancelled, held_conflict, duplicate or
    rejected. Keep every result with view.keep(result, label).
    """
    raise NotImplementedError("admit")


def resolve(board, view, key, chosen):
    """A person picked `chosen` among competing decisions for `key`."""
    raise NotImplementedError("resolve")


def message(board, view, key) -> str:
    """What the screen says about `key`. See the README for wording."""
    raise NotImplementedError("message")
