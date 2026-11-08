"""Two stores for a dual write, and a writer that can die between them.

Fernhill is moving order status from its old orders store (`legacy`,
field `order_status`) to a read model in a new service (`projection`,
field `status`). During the cutover every change is written to both.
They are separate stores, so a write to both is two commits, and a
crash can land between them.

Everything here is in memory and synthetic. A Store keeps its tables
after the writer "dies", the way a database outlives the process that
was writing to it.
"""
import copy


class StoreUnavailable(Exception):
    """The store could not be read or written. Says nothing about
    what is in it."""


class Crash(Exception):
    """The writer died here. Nothing after this point ran."""


# region: stores_commit
class Store:
    def __init__(self, name, tables):
        self.name = name
        self.tables = {t: {} for t in tables}
        self.available = True
        self.commits = 0

    def read(self, table) -> dict:
        if not self.available:
            raise StoreUnavailable(self.name)
        return copy.deepcopy(self.tables[table])

    def commit(self, writes):
        """Apply every (table, key, row) in `writes`, or none."""
        if not self.available:
            raise StoreUnavailable(self.name)
        for table, key, row in writes:
            self.tables[table][key] = copy.deepcopy(row)
        self.commits += 1
# endregion


def new_stores(orders):
    """A legacy store and a projection, both backfilled with `orders`:
    {order_id: (status, version)}."""
    legacy = Store("legacy", ["orders", "applied_ops", "intents"])
    projection = Store("projection", ["orders", "applied_ops"])
    legacy.commit([("orders", oid, {"order_status": s, "version": v})
                   for oid, (s, v) in orders.items()])
    projection.commit([("orders", oid, {"status": s, "version": v})
                       for oid, (s, v) in orders.items()])
    return legacy, projection


# region: stores_apply
def apply_projection(projection, op):
    """Write `op` to the projection once, and never over a newer
    version. Returns True if it wrote."""
    if op["op"] in projection.read("applied_ops"):
        return False
    row = projection.read("orders").get(op["order"])
    writes = [("applied_ops", op["op"], True)]
    if row is None or row["version"] < op["version"]:
        writes.append(("orders", op["order"],
                       {"status": op["status"],
                        "version": op["version"]}))
    projection.commit(writes)  # one commit: the effect and its record
    return True
# endregion


# region: stores_dual_write
def dual_write(legacy, projection, ops, crash_after=None,
               with_intent=False):
    """Apply each op to legacy, then to the projection.

    `crash_after` names an op: the writer dies right after that op's
    legacy commit. Ops legacy already applied are skipped, which is
    the ordinary resume rule, and the reason a crash goes unnoticed.
    """
    for op in ops:
        if op["op"] in legacy.read("applied_ops"):  # (1)
            continue
        writes = [("orders", op["order"],
                   {"order_status": op["status"],
                    "version": op["version"]}),
                  ("applied_ops", op["op"], True)]
        if with_intent:
            writes.append(("intents", op["op"],
                           dict(op, projected=False)))  # (2)
        legacy.commit(writes)  # commit 1
        if op["op"] == crash_after:
            raise Crash(op["op"])  # (3)
        apply_projection(projection, op)  # commit 2
        if with_intent:
            legacy.commit([("intents", op["op"],
                            dict(op, projected=True))])  # commit 3
# endregion


# region: stores_pair_check
def pair_check(legacy, projection):
    """The validation that only compares rows present in both."""
    old = legacy.read("orders")
    new = projection.read("orders")
    both = sorted(set(old) & set(new))
    differ = [i for i in both
              if old[i]["order_status"] != new[i]["status"]]
    return {"compared": len(both), "mismatched": differ}
# endregion
