"""Checks for exercise 7. Run: python3 -m lab check 07"""
import unittest

from lab import target
from lab.stale_results import (Decision, GoalBoard, Result, View,
                               check_then_write, decide, load_cases,
                               overwrite, replay, view_state)

EX = "ex07_admission"
mod = target.load(EX)
CASES = {c["name"]: c for c in load_cases(target.fixture(EX, "cases.json"))}


def active(view, key):
    r = view.active.get(key)
    return r.content if r else None


class Admission(unittest.TestCase):
    def test_every_case(self):
        for name, case in CASES.items():
            with self.subTest(case=name):
                board, view = replay(case, mod.admit, mod.resolve)
                for key, want in case["expect"].items():
                    state, shown = view_state(board, view, key)
                    self.assertEqual(state, want["state"])
                    self.assertEqual(shown.content if shown else None,
                                     want["content"])
                    got = {rid: view.labels[rid] for rid in want["labels"]}
                    self.assertEqual(got, want["labels"])

    def test_every_arrival_is_kept(self):
        for name, case in CASES.items():
            with self.subTest(case=name):
                _, view = replay(case, mod.admit, mod.resolve)
                arrivals = sum(s[0] == "arrive" for s in case["steps"])
                self.assertEqual(len(view.history), arrivals)

    def test_a_reused_id_with_new_content_is_rejected(self):
        _, view = replay(CASES["reused-id"], mod.admit)
        self.assertEqual(view.history[-1][1], "rejected")

    def test_a_repeat_with_the_same_content_is_a_duplicate(self):
        _, view = replay(CASES["duplicate-delivery"], mod.admit)
        self.assertEqual(view.history[-1][1], "duplicate")

    def test_a_result_for_an_unknown_decision_is_rejected(self):
        board, view = GoalBoard(), View()
        r = Result("r9", "g9", "SKU-4471", "From nowhere.")
        self.assertEqual(mod.admit(board, view, r), "rejected")
        self.assertEqual(view.active, {})


class Controls(unittest.TestCase):
    """The broken policies must fail, or the tests prove nothing."""

    def test_overwrite_lets_the_old_result_win(self):
        _, view = replay(CASES["old-result-after-new"], overwrite)
        self.assertEqual(active(view, "SKU-4471"),
                         "Waxed canvas that shrugs off rain.")

    def test_overwrite_revives_a_cancelled_request(self):
        _, view = replay(CASES["cancel-before-result"], overwrite)
        self.assertIsNotNone(active(view, "SKU-4471"))

    def test_check_then_write_fails_only_the_race(self):
        failed = []
        for name, case in CASES.items():
            _, view = replay(case, check_then_write)
            for key, want in case["expect"].items():
                if active(view, key) != want["content"]:
                    failed.append(name)
        self.assertEqual(failed, ["check-write-race"])


class Resolution(unittest.TestCase):
    def setUp(self):
        self.board, self.view = replay(CASES["competing-corrections"],
                                       mod.admit, mod.resolve)

    def test_conflict_shows_no_answer(self):
        self.assertEqual(view_state(self.board, self.view, "SKU-4471"),
                         ("conflict", None))

    def test_resolution_promotes_the_chosen_result(self):
        mod.resolve(self.board, self.view, "SKU-4471", "g2")
        state, shown = view_state(self.board, self.view, "SKU-4471")
        self.assertEqual(state, "current")
        self.assertEqual(shown.id, "r2")
        self.assertEqual(self.view.labels["r3"], "superseded")
        # Both results stay in history.
        ids = [r.id for r, _ in self.view.history]
        self.assertEqual(sorted(ids), ["r2", "r3"])

    def test_a_result_after_resolution_is_admitted_normally(self):
        board, view = GoalBoard(), View()
        for d in [Decision("g1", "SKU-4471", "waxed canvas"),
                  Decision("g2", "SKU-4471", "recycled lining", "g1"),
                  Decision("g3", "SKU-4471", "free repairs", "g1")]:
            decide(board, view, d)
        mod.resolve(board, view, "SKU-4471", "g3")
        late = Result("r3", "g3", "SKU-4471", "Repaired free.")
        self.assertEqual(mod.admit(board, view, late), "admitted")
        self.assertEqual(mod.admit(
            board, view, Result("r2", "g2", "SKU-4471", "Recycled.")),
            "superseded")


class Wording(unittest.TestCase):
    def say(self, name, key="SKU-4471"):
        board, view = replay(CASES[name], mod.admit, mod.resolve)
        return mod.message(board, view, key)

    def test_current_shows_the_result(self):
        self.assertEqual(self.say("plain"),
                         "Waxed canvas that shrugs off rain.")

    def test_pending_names_the_new_request_not_the_old_answer(self):
        text = self.say("old-result-first")
        self.assertIn("recycled lining", text)
        self.assertNotIn("Waxed canvas", text)

    def test_cancelled_never_claims_the_worker_stopped(self):
        for name in ["cancel-before-result", "cancel-after-admit"]:
            text = self.say(name).lower()
            self.assertIn("cancelled", text)
            for word in ["stopped", "failed", "error"]:
                self.assertNotIn(word, text)

    def test_cancelled_mentions_the_late_draft(self):
        self.assertIn("afterward", self.say("cancel-before-result"))

    def test_cancel_after_admit_says_it_is_not_undone(self):
        self.assertIn("undo", self.say("cancel-after-admit"))

    def test_conflict_lists_both_in_a_fixed_order(self):
        case = CASES["competing-corrections"]
        flipped = dict(case, steps=case["steps"][:3]
                       + case["steps"][3:][::-1])
        a = self.say("competing-corrections")
        board, view = replay(flipped, mod.admit, mod.resolve)
        b = mod.message(board, view, "SKU-4471")
        self.assertEqual(a, b)  # finish order changes nothing
        self.assertIn("recycled lining", a)
        self.assertIn("free repairs", a)


if __name__ == "__main__":
    unittest.main()
