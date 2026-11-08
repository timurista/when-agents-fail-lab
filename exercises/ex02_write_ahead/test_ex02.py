"""Checks for exercise 2. Run: python3 -m lab check 02"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lab import target
from lab.agent import call
from lab.outcomes import Outcome
from lab.tools import Fault, Storefront

EX = "ex02_write_ahead"
mod = target.load(EX)

PLAN = [
    ("storefront", "set_description",
     {"sku": "SKU-4471", "text": "Waxed canvas tote, 18 L"}),
    ("storefront", "set_description",
     {"sku": "SKU-9102", "text": "Enamel camp mug, 350 ml"}),
    ("storefront", "set_description",
     {"sku": "SKU-2208", "text": "Wool beanie, charcoal"}),
]

# Every gap between two steps of one call, and what a crash there
# must leave behind once the log is read back.
CRASHES = {
    "before_intent": None,               # nothing on disk for this op
    "after_intent": Outcome.NEVER_SENT,
    "after_sent": Outcome.UNKNOWN,       # the call never happened
    "before_response": Outcome.UNKNOWN,  # the call happened
    "after_response": Outcome.CONFIRMED,
}


class TempDir(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "run.jsonl"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def copy(self, name):
        shutil.copy(target.fixture(EX, name), self.path)
        return self.path


class OpIds(unittest.TestCase):
    def test_same_task_and_step_same_id(self):
        self.assertEqual(mod.op_id("t0412", 2), mod.op_id("t0412", 2))

    def test_different_steps_and_tasks_differ(self):
        ids = {mod.op_id(t, s) for t in ("t1", "t2") for s in (1, 2)}
        self.assertEqual(len(ids), 4)


class Durability(TempDir):
    def test_each_record_is_one_line_and_fsynced(self):
        with mock.patch("os.fsync", wraps=__import__("os").fsync) as f:
            log = mod.DurableLog(self.path)
            log.record("intent", "op-1", tool="storefront")
            log.record("sent", "op-1")
        self.assertEqual(f.call_count, 2)
        raw = self.path.read_text()
        self.assertTrue(raw.endswith("\n"))
        kinds = [json.loads(x)["kind"] for x in raw.splitlines()]
        self.assertEqual(kinds, ["intent", "sent"])

    def test_seq_continues_after_reopen(self):
        mod.DurableLog(self.path).record("intent", "op-1")
        event = mod.DurableLog(self.path).record("sent", "op-1")
        self.assertEqual(event["seq"], 2)

    def test_lab_call_writes_through_a_durable_log(self):
        log = mod.DurableLog(self.path)
        call(log, Storefront(), "op-1", "set_description",
             sku="SKU-1", text="new")
        events, torn = mod.read_log(self.path)
        self.assertIsNone(torn)
        self.assertEqual([e["kind"] for e in events],
                         ["intent", "sent", "response"])


class TornTail(TempDir):
    def test_torn_last_line_is_dropped_and_reported(self):
        found = mod.recover(target.fixture(EX, "torn-tail.jsonl"))
        self.assertTrue(found.torn.startswith('{"kind": "response"'))
        self.assertEqual(found.outcomes, {
            "op-t0412-1": Outcome.CONFIRMED,
            "op-t0412-2": Outcome.UNKNOWN,
        })
        self.assertEqual(found.attention,
                         {"op-t0412-2": Outcome.UNKNOWN})

    def test_recover_changes_nothing_on_disk(self):
        before = self.copy("torn-tail.jsonl").read_bytes()
        mod.recover(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_opening_to_append_cuts_the_torn_tail_first(self):
        self.copy("torn-tail.jsonl")
        mod.DurableLog(self.path).record("stop", None, by="operator")
        events, torn = mod.read_log(self.path)
        self.assertIsNone(torn)
        self.assertEqual(events[-1]["kind"], "stop")
        self.assertEqual(events[-1]["seq"], 6)

    def test_a_bad_line_before_the_last_is_damage(self):
        with self.assertRaises(mod.LogCorrupt):
            mod.recover(target.fixture(EX, "glued.jsonl"))


class CrashEverywhere(TempDir):
    """Crash at every gap of every step, then restart the run."""

    def crash_then_resume(self, point, step):
        shop = Storefront()
        op = mod.op_id("t0412", step)
        with self.assertRaises(mod.Crash):
            mod.resume(self.path, "t0412", PLAN, {"storefront": shop},
                       crash_at=(point, op))
        self.applied_at_crash = set(shop.applied)
        found = mod.recover(self.path)
        notes = mod.resume(self.path, "t0412", PLAN,
                           {"storefront": shop})
        return shop, op, found, notes

    def test_every_crash_point_leaves_the_right_outcome(self):
        for step in (1, 2, 3):
            for point, want in CRASHES.items():
                with self.subTest(step=step, point=point):
                    self.path.unlink(missing_ok=True)
                    shop, op, found, _ = self.crash_then_resume(point,
                                                                step)
                    self.assertEqual(found.outcomes.get(op), want)

    def test_never_sent_is_never_wrong(self):
        # The log may over-report (UNKNOWN for a call that never
        # happened). It must never under-report.
        for step in (1, 2, 3):
            for point in CRASHES:
                with self.subTest(step=step, point=point):
                    self.path.unlink(missing_ok=True)
                    shop, op, found, _ = self.crash_then_resume(point,
                                                                step)
                    if found.outcomes.get(op) == Outcome.NEVER_SENT:
                        self.assertNotIn(op, self.applied_at_crash)

    def test_a_restart_never_applies_anything_twice(self):
        for step in (1, 2, 3):
            for point in CRASHES:
                with self.subTest(step=step, point=point):
                    self.path.unlink(missing_ok=True)
                    shop, op, _, notes = self.crash_then_resume(point,
                                                                step)
                    for item in shop.catalog.values():
                        self.assertLessEqual(item["version"], 1)
                    if CRASHES[point] == Outcome.UNKNOWN:
                        self.assertEqual(notes[op],
                                         "unknown: not resent")

    def test_restart_refuses_a_request_that_changed(self):
        shop = Storefront()
        op = mod.op_id("t0412", 2)
        with self.assertRaises(mod.Crash):
            mod.resume(self.path, "t0412", PLAN, {"storefront": shop},
                       crash_at=("after_intent", op))
        changed = list(PLAN)
        changed[1] = ("storefront", "set_description",
                      {"sku": "SKU-9102", "text": "Enamel mug, 12 oz"})
        notes = mod.resume(self.path, "t0412", changed,
                           {"storefront": shop})
        self.assertEqual(notes[op], "changed since the crash: review")
        self.assertNotIn(op, shop.applied)

    def test_a_timeout_before_the_crash_stays_unknown(self):
        shop = Storefront(faults=[Fault.NONE, Fault.LOST_REPLY])
        mod.resume(self.path, "t0412", PLAN, {"storefront": shop})
        found = mod.recover(self.path)
        self.assertEqual(found.attention,
                         {mod.op_id("t0412", 2): Outcome.UNKNOWN})


if __name__ == "__main__":
    unittest.main()
