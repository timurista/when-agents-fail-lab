"""Exercise 5, reference answer."""
from lab.stores import StoreUnavailable, apply_projection


# region: ex05_audit
def audit(legacy, projection):
    """Classify every expected order: matched, mismatched, missing.

    The expected set is legacy, the source of truth during the
    cutover. Orphans are projection rows legacy doesn't have.
    """
    old = legacy.read("orders")
    new = projection.read("orders")
    out = {"expected": len(old), "matched": [], "mismatched": [],
           "missing": [], "orphans": sorted(set(new) - set(old))}
    for oid in sorted(old):
        want = (old[oid]["order_status"], old[oid]["version"])
        if oid not in new:
            out["missing"].append(oid)
        elif (new[oid]["status"], new[oid]["version"]) != want:
            out["mismatched"].append(oid)
        else:
            out["matched"].append(oid)
    out["ok"] = (len(out["matched"]) == out["expected"]
                 and not out["orphans"])
    return out
# endregion


# region: ex05_reconcile
def reconcile(legacy, projection):
    """Finish projection writes that a durable intent says are owed.

    Writes only from an intent, never over a newer row, and nothing
    at all when either store can't be read.
    """
    result = {"repaired": [], "already": [], "conflicts": [],
              "writes": 0, "unavailable": None}
    try:
        intents = legacy.read("intents")  # (1)
        applied = projection.read("applied_ops")
        rows = projection.read("orders")
    except StoreUnavailable as err:
        result["unavailable"] = str(err)  # (2)
        return result
    for op_id in sorted(intents):
        intent = intents[op_id]
        if intent["projected"]:
            continue
        row = rows.get(intent["order"])
        same = row is not None and (row["status"], row["version"]) \
            == (intent["status"], intent["version"])
        if op_id in applied or same:  # (3)
            result["already"].append(op_id)
        elif row is not None and row["version"] >= intent["version"]:
            result["conflicts"].append(op_id)  # (4)
            continue
        else:
            apply_projection(projection, intent)
            result["writes"] += 1
            result["repaired"].append(op_id)
        legacy.commit([("intents", op_id,
                        dict(intent, projected=True))])  # (5)
    return result
# endregion
