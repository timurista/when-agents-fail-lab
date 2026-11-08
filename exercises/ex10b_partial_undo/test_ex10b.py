"""Checks for exercise 10b. Run: python3 -m lab check 10b"""
import unittest

from lab import target
from lab import undo_workspace as W

EX = "ex10b_partial_undo"
mod = target.load(EX)


def recover(ws, run):
    p = mod.plan(ws, run)
    return p, mod.execute(p, ws)


def kept(p):
    return dict(p["keep"])


class TheControl(unittest.TestCase):
    """Not your code: shows what object-by-object undo leaves behind."""

    def test_object_by_object_leaves_the_edited_widget_dangling(self):
        ws, run = W.edited_widget()
        for id, why in W.object_by_object(ws, run)["remove"]:
            W.delete(ws, id, why)
        self.assertEqual(W.dangling(ws), [("W1", ("name", "late-orders"))])

    def test_object_by_object_hides_an_ambiguous_name(self):
        ws, run = W.ambiguous_name()
        for id, why in W.object_by_object(ws, run)["remove"]:
            W.delete(ws, id, why)
        self.assertEqual(W.dangling(ws), [])  # nothing looks broken
        self.assertEqual(W.resolve(ws, ("name", "late-orders")), ["R0"])


class Recovery(unittest.TestCase):
    def test_an_unchanged_run_fully_reverses(self):
        ws, run = W.unchanged()
        _, done = recover(ws, run)
        self.assertEqual(done["removed"], ["D1", "W1", "R1"])
        self.assertEqual(ws["objects"], {})

    def test_an_edited_widget_keeps_the_rule_it_uses(self):
        ws, run = W.edited_widget()
        p, done = recover(ws, run)
        self.assertEqual(done["removed"], ["D1"])
        self.assertEqual(W.dangling(ws), [])

    def test_the_two_reasons_to_keep_stay_apart(self):
        ws, run = W.edited_widget()
        p = mod.plan(ws, run)
        self.assertTrue(kept(p)["W1"].startswith("changed since the run"))
        self.assertEqual(kept(p).get("R1"), "needed by W1")

    def test_a_transitive_dependency_is_kept(self):
        ws, run = W.transitive()
        _, done = recover(ws, run)
        self.assertEqual(done["removed"], ["D1"])
        self.assertEqual(sorted(ws["objects"]), ["M1", "R1", "W1"])
        self.assertEqual(W.dangling(ws), [])

    def test_an_unrelated_rule_is_still_removed(self):
        ws, run = W.unrelated_rule()
        _, done = recover(ws, run)
        self.assertEqual(sorted(done["removed"]), ["D1", "R2"])
        self.assertEqual(W.dangling(ws), [])

    def test_an_ambiguous_name_is_kept_and_reported(self):
        ws, run = W.ambiguous_name()
        p, _ = recover(ws, run)
        self.assertIn("R1", ws["objects"])
        self.assertIn("R0", ws["objects"])
        self.assertEqual(p["unresolved"],
                         [("W1", "late-orders", ["R0", "R1"])])
        self.assertTrue(any("R0, R1" in line for line in mod.report(p)))

    def test_a_preview_does_not_authorize_a_stale_plan(self):
        ws, run = W.unchanged()
        preview = mod.plan(ws, run)
        W.edit(ws, "W1")
        done = mod.execute(preview, ws)
        self.assertEqual(done["removed"], [])
        self.assertTrue(done["refused"])
        self.assertEqual(sorted(ws["objects"]), ["D1", "R1", "W1"])
        _, again = recover(ws, run)
        self.assertEqual(again["removed"], ["D1"])

    def test_repeating_recovery_adds_no_effects(self):
        ws, run = W.edited_widget()
        recover(ws, run)
        effects = list(ws["effects"])
        _, again = recover(ws, run)
        self.assertEqual(again["removed"], [])
        self.assertEqual(ws["effects"], effects)

    def test_a_cycle_is_reported_unsupported(self):
        ws, run = W.cycle()
        p, done = recover(ws, run)
        self.assertEqual(done["removed"], [])
        self.assertTrue((p["error"] or "").startswith("cycle: unsupported"))

    def test_the_report_has_a_line_per_decision(self):
        ws, run = W.edited_widget()
        lines = mod.report(mod.plan(ws, run))
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(line) <= 72 for line in lines))


if __name__ == "__main__":
    unittest.main()
