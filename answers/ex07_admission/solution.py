"""Exercise 7, reference answer."""
from lab.stale_results import view_state


# region: ex07_admit
def admit(board, view, result, pause=None):
    """Check the result's decision and update the view in one step."""
    if pause:
        pause()  # (1)
    first = view.results.get(result.id)
    if first is not None:  # (2)
        same = first == result
        return view.keep(result, "duplicate" if same else "rejected")
    status, heads = board.state(result.key)
    if result.decision not in board.decisions:
        label = "rejected"
    elif status == "current" and heads == [result.decision]:
        view.active[result.key] = result
        label = "admitted"
    elif status == "conflict" and result.decision in heads:
        view.held[result.decision] = result  # (3)
        label = "held_conflict"
    elif status == "cancelled":
        label = "cancelled"
    else:
        label = "superseded"
    return view.keep(result, label)  # (4)
# endregion


# region: ex07_resolve
def resolve(board, view, key, chosen):
    """A person picked one of the competing decisions."""
    board.resolve(key, chosen)
    for decision, held in list(view.held.items()):
        if held.key != key:
            continue
        del view.held[decision]
        if decision == chosen:
            view.active[key] = held
            view.labels[held.id] = "admitted"
        else:
            view.labels[held.id] = "superseded"
# endregion


def _count(n, one, many):
    return one if n == 1 else many.format(n=n)


# region: ex07_message
def message(board, view, key) -> str:
    """What the screen says about `key`, from its state."""
    state, shown = view_state(board, view, key)
    _, heads = board.state(key)
    goals = [board.decisions[h].goal for h in heads]
    if state == "current":
        return shown.content
    if state == "pending":
        return f"Updating for your new request ({goals[0]})."
    if state == "conflict":
        options = "; ".join(f"({chr(97 + i)}) {g}"
                            for i, g in enumerate(goals))
        return f"You changed the brief twice. Pick one: {options}."
    if state == "cancelled":
        text = "You cancelled the description rewrite."  # (1)
        late = [r for r, label in view.history
                if r.key == key and label == "cancelled"]
        if late:
            text += " " + _count(
                len(late),
                "One draft came back afterward; it wasn't applied.",
                "{n} drafts came back afterward; none was applied.")
        if any(r.key == key and view.labels[r.id] == "admitted"
               for r in view.results.values()):
            text += (" A draft was applied before you cancelled."
                     " Cancelling doesn't undo it.")  # (2)
        return text
    return "No description has been requested."
# endregion
