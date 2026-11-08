"""Exercise 10b, reference answer."""
from lab.undo_workspace import delete, fingerprint, resolve


# region: ex10b_plan
def plan(ws, run):
    """Undo what the run created, except what changed since and
    everything a kept object still uses."""
    objects = ws["objects"]
    created = {id: v for id, v in run["created"] if id in objects}
    result = {"against": fingerprint(ws), "remove": [], "keep": [],
              "unresolved": [], "error": None}

    loop = find_cycle(ws, created)
    if loop:  # (1)
        result["error"] = f"cycle: unsupported ({' -> '.join(loop)})"
        return result

    why = {}
    for id, version in created.items():  # (2)
        if objects[id]["version"] != version:
            why[id] = (f"changed since the run "
                       f"(v{version} to v{objects[id]['version']})")
    retained = [id for id in objects if id not in created] + list(why)
    while retained:  # (3)
        holder = retained.pop()
        for use in objects[holder]["uses"]:
            targets = resolve(ws, use)
            if len(targets) > 1:  # (4)
                result["unresolved"].append(
                    (holder, use[1], targets))
            for t in targets:
                if t in created and t not in why:
                    why[t] = (f"needed by {holder}" if len(targets) == 1
                              else f"may be needed by {holder} "
                                   f"('{use[1]}' is ambiguous)")
                    retained.append(t)

    result["keep"] = [(id, why[id]) for id in created if id in why]
    gone = [id for id in created if id not in why]
    result["remove"] = [(id, "created by the run; nothing retained uses it")
                        for id in removal_order(ws, gone)]
    return result
# endregion


# region: ex10b_execute
def execute(p, ws):
    """Carry out a plan, after checking nothing changed since it was made."""
    if p["error"]:
        return {"removed": [], "refused": p["error"]}
    if fingerprint(ws) != p["against"]:  # (1)
        return {"removed": [], "refused": "state changed since the plan; replan"}
    done = []
    for id, why in p["remove"]:
        if id in ws["objects"]:  # (2)
            delete(ws, id, why)
            done.append(id)
    return {"removed": done, "refused": None}
# endregion


def report(p):
    if p["error"]:
        return [p["error"], "nothing removed"]
    lines = [f"remove {id:<3} {why}" for id, why in p["remove"]]
    lines += [f"keep   {id:<3} {why}" for id, why in p["keep"]]
    lines += [f"unresolved: {h} uses '{name}', which matches {', '.join(ts)}"
              for h, name, ts in p["unresolved"]]
    return lines


def edges(ws, id):
    return [t for u in ws["objects"][id]["uses"] for t in resolve(ws, u)]


def find_cycle(ws, created):
    """A loop among run-created objects, or None."""
    state = {}

    def visit(id, path):
        state[id] = "open"
        for t in edges(ws, id):
            if t not in created:
                continue
            if state.get(t) == "open":
                return path[path.index(t):] + [t]
            if t not in state:
                found = visit(t, path + [t])
                if found:
                    return found
        state[id] = "done"
        return None

    for id in created:
        if id not in state:
            found = visit(id, [id])
            if found:
                return found
    return None


def removal_order(ws, gone):
    """Users before the things they use, so nothing dangles midway."""
    left, order = list(gone), []
    while left:
        for id in left:
            if not any(id in edges(ws, other) for other in left if other != id):
                order.append(id)
                left.remove(id)
                break
    return order


def demo():
    """Each fixture: the plan's report, then what dangles afterwards."""
    from lab import undo_workspace as W
    for name in ("unchanged", "edited_widget", "transitive",
                 "unrelated_rule", "ambiguous_name", "cycle"):
        ws, run = getattr(W, name)()
        p = plan(ws, run)
        execute(p, ws)
        print(f"# {name}")
        for line in report(p):
            print("  " + line)
        print(f"  dangling after: {W.dangling(ws) or 'none'}")


if __name__ == "__main__":
    demo()
