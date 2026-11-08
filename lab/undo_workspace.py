"""Exercise 10b: a synthetic workspace a run built, for partial undo.
No products, accounts or network. Fixtures at the bottom; the
object-by-object control is `object_by_object`."""
import copy


def obj(id, kind, name, version=1, uses=()):
    """uses: ("id", other_id) or ("name", other_name) pairs."""
    return {"id": id, "kind": kind, "name": name, "version": version,
            "uses": list(uses)}


def new_workspace(*objects):
    return {"objects": {o["id"]: o for o in objects}, "effects": []}


def run_creates(ws, *objects):
    """The run under recovery. Returns its record: (id, version) per
    object it created, in creation order."""
    created = []
    for o in objects:
        ws["objects"][o["id"]] = copy.deepcopy(o)
        created.append((o["id"], o["version"]))
    return {"run": "run-1108", "created": created}


def edit(ws, id):
    """A colleague changes an object after the run."""
    ws["objects"][id]["version"] += 1


def delete(ws, id, why):
    """The only effect undo has. Recorded so a repeat can be checked."""
    del ws["objects"][id]
    ws["effects"].append(("delete", id, why))


def resolve(ws, use):
    """The ids a use could point at right now."""
    how, ref = use
    if how == "id":
        return [ref] if ref in ws["objects"] else []
    return sorted(i for i, o in ws["objects"].items() if o["name"] == ref)


def dangling(ws):
    """Uses that point at nothing. Returns (object id, use) pairs."""
    return [(i, u) for i, o in ws["objects"].items() for u in o["uses"]
            if not resolve(ws, u)]


def fingerprint(ws):
    """What a plan was computed against: every id and its version."""
    return tuple(sorted((i, o["version"]) for i, o in ws["objects"].items()))


# The fixtures from EXPECTATIONS.md. Each returns (workspace, run record).

def unchanged():
    ws = new_workspace()
    run = run_creates(ws,
                      obj("R1", "rule", "late-orders"),
                      obj("W1", "widget", "late orders",
                          uses=[("name", "late-orders")]),
                      obj("D1", "dashboard", "ops", uses=[("id", "W1")]))
    return ws, run


def edited_widget():
    ws, run = unchanged()
    edit(ws, "W1")
    return ws, run


def transitive():
    ws = new_workspace()
    run = run_creates(ws,
                      obj("R1", "rule", "late-orders"),
                      obj("M1", "metric", "late-count", uses=[("id", "R1")]),
                      obj("W1", "widget", "late orders",
                          uses=[("name", "late-count")]),
                      obj("D1", "dashboard", "ops", uses=[("id", "W1")]))
    edit(ws, "W1")
    return ws, run


def unrelated_rule():
    ws = new_workspace()
    run = run_creates(ws,
                      obj("R1", "rule", "late-orders"),
                      obj("R2", "rule", "stale-carts"),
                      obj("W1", "widget", "late orders",
                          uses=[("name", "late-orders")]),
                      obj("D1", "dashboard", "ops", uses=[("id", "W1")]))
    edit(ws, "W1")
    return ws, run


def ambiguous_name():
    ws = new_workspace(obj("R0", "rule", "late-orders", version=4))
    run = run_creates(ws,
                      obj("R1", "rule", "late-orders"),
                      obj("W1", "widget", "late orders",
                          uses=[("name", "late-orders")]))
    edit(ws, "W1")
    return ws, run


def cycle():
    ws = new_workspace()
    run = run_creates(ws,
                      obj("M1", "metric", "a", uses=[("id", "M2")]),
                      obj("M2", "metric", "b", uses=[("id", "M1")]))
    return ws, run


# region: ex10b_control
def object_by_object(ws, run):
    """The control: Chapter 10's rule applied one object at a time.
    Newest first; remove what is unchanged, keep what changed. It knows
    nothing about what a kept object uses, and doesn't recheck a preview.
    Returns the same plan shape the exercise asks you for."""
    remove, keep = [], []
    for id, version in reversed(run["created"]):
        if id not in ws["objects"]:
            continue
        current = ws["objects"][id]["version"]
        if current != version:
            keep.append((id, f"changed since the run (v{version} to v{current})"))
        else:
            remove.append((id, "created by the run, unchanged"))
    return {"against": fingerprint(ws), "remove": remove, "keep": keep,
            "unresolved": [], "error": None}
# endregion
