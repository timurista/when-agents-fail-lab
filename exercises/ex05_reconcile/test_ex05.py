"""Checks for exercise 5. Run: python3 -m lab check 05"""
import json
import unittest

from lab import target
from lab.stores import (Crash, apply_projection, dual_write,
                        new_stores, pair_check)

EX = "ex05_reconcile"
mod = target.load(EX)
CUTOVER = json.loads(target.fixture(EX, "cutover.json").read_text())


def cutover(crash_after=None, with_intent=False):
    """Run the four ops; if the writer dies, restart it once."""
    legacy, projection = new_stores(
        {k: tuple(v) for k, v in CUTOVER["orders"].items()})
    try:
        dual_write(legacy, projection, CUTOVER["ops"], crash_after,
                   with_intent)
    except Crash:
        dual_write(legacy, projection, CUTOVER["ops"],
                   with_intent=with_intent)  # the restarted writer
    return legacy, projection


class TheGap(unittest.TestCase):
    def test_no_crash_is_clean_both_ways(self):
        legacy, projection = cutover()
        self.assertEqual(pair_check(legacy, projection),
                         {"compared": 8, "mismatched": []})
        a = mod.audit(legacy, projection)
        self.assertEqual((a["expected"], len(a["matched"])), (8, 8))
        self.assertTrue(a["ok"])

    def test_pair_check_calls_a_missing_row_clean(self):
        legacy, projection = cutover(crash_after="op-17")
        self.assertEqual(pair_check(legacy, projection),
                         {"compared": 7, "mismatched": []})

    def test_audit_finds_the_missing_row(self):
        legacy, projection = cutover(crash_after="op-17")
        a = mod.audit(legacy, projection)
        self.assertEqual(a["expected"], 8)
        self.assertEqual(len(a["matched"]), 7)
        self.assertEqual(a["missing"], ["O-17"])
        self.assertFalse(a["ok"])

    def test_a_crash_during_an_update_is_a_mismatch(self):
        legacy, projection = cutover(crash_after="op-14")
        self.assertEqual(pair_check(legacy, projection)["mismatched"],
                         ["O-14"])
        a = mod.audit(legacy, projection)
        self.assertEqual((a["missing"], a["mismatched"]),
                         ([], ["O-14"]))

    def test_audit_reports_orphans(self):
        legacy, projection = cutover()
        projection.commit([("orders", "O-99",
                            {"status": "paid", "version": 1})])
        a = mod.audit(legacy, projection)
        self.assertEqual(a["orphans"], ["O-99"])
        self.assertFalse(a["ok"])


class Repair(unittest.TestCase):
    def test_repairs_from_the_intent_once(self):
        legacy, projection = cutover("op-17", with_intent=True)
        first = mod.reconcile(legacy, projection)
        self.assertEqual((first["repaired"], first["writes"]),
                         (["op-17"], 1))
        self.assertTrue(mod.audit(legacy, projection)["ok"])
        second = mod.reconcile(legacy, projection)
        self.assertEqual(second["writes"], 0)

    def test_repairs_a_stale_update(self):
        legacy, projection = cutover("op-14", with_intent=True)
        self.assertEqual(mod.reconcile(legacy, projection)["repaired"],
                         ["op-14"])
        self.assertTrue(mod.audit(legacy, projection)["ok"])

    def test_never_overwrites_a_newer_row(self):
        legacy, projection = cutover("op-17", with_intent=True)
        newer = {"status": "cancelled", "version": 2}
        projection.commit([("orders", "O-17", newer)])
        r = mod.reconcile(legacy, projection)
        self.assertEqual((r["conflicts"], r["writes"]), (["op-17"], 0))
        self.assertEqual(projection.read("orders")["O-17"], newer)
        self.assertEqual(mod.audit(legacy, projection)["mismatched"],
                         ["O-17"])

    def test_already_applied_is_marked_not_rewritten(self):
        legacy, projection = cutover("op-17", with_intent=True)
        before = projection.commits
        projection.commit([("orders", "O-17", {"status": "paid",
                                               "version": 1})])
        r = mod.reconcile(legacy, projection)
        self.assertEqual((r["already"], r["writes"]), (["op-17"], 0))
        self.assertEqual(projection.commits, before + 1)
        self.assertTrue(legacy.read("intents")["op-17"]["projected"])

    def test_a_crash_before_commit_3_is_safe_to_rerun(self):
        legacy, projection = cutover("op-17", with_intent=True)
        apply_projection(projection, legacy.read("intents")["op-17"])
        r = mod.reconcile(legacy, projection)
        self.assertEqual((r["already"], r["writes"]), (["op-17"], 0))
        self.assertTrue(mod.audit(legacy, projection)["ok"])

    def test_no_source_no_write(self):
        legacy, projection = cutover("op-17", with_intent=True)
        legacy.available = False
        before = projection.commits
        r = mod.reconcile(legacy, projection)
        self.assertEqual(r["writes"], 0)
        self.assertEqual(r["unavailable"], "legacy")
        self.assertEqual(projection.commits, before)
        legacy.available = True
        self.assertEqual(mod.audit(legacy, projection)["missing"],
                         ["O-17"])

    def test_no_intent_no_repair(self):
        legacy, projection = cutover("op-17", with_intent=False)
        r = mod.reconcile(legacy, projection)
        self.assertEqual((r["repaired"], r["writes"]), ([], 0))
        self.assertEqual(mod.audit(legacy, projection)["missing"],
                         ["O-17"])


if __name__ == "__main__":
    unittest.main()
