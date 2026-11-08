"""Checks for exercise 1. Run: python3 -m lab check 01"""
import unittest

from lab import target
from lab.agent import call
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Storefront

EX = "ex01_three_outcomes"
mod = target.load(EX)


class StopRun(unittest.TestCase):
    def test_three_skus_three_outcomes(self):
        log = RunLog.load(target.fixture(EX, "stop-run.jsonl"))
        self.assertEqual(mod.summarize(log), {
            "op-4471": Outcome.CONFIRMED,
            "op-9102": Outcome.UNKNOWN,
            "op-2208": Outcome.NEVER_SENT,
        })


class Mixed(unittest.TestCase):
    def setUp(self):
        self.out = mod.summarize(
            RunLog.load(target.fixture(EX, "mixed.jsonl")))

    def test_explicit_rejection_is_failed(self):
        self.assertEqual(self.out["op-a"], Outcome.FAILED)

    def test_an_hour_of_timeouts_is_still_unknown(self):
        self.assertEqual(self.out["op-b"], Outcome.UNKNOWN)

    def test_a_status_receipt_confirms(self):
        self.assertEqual(self.out["op-c"], Outcome.CONFIRMED)

    def test_not_found_from_a_weak_lookup_proves_nothing(self):
        self.assertEqual(self.out["op-d"], Outcome.UNKNOWN)

    def test_cancel_ack_is_canceled(self):
        self.assertEqual(self.out["op-e"], Outcome.CANCELED)

    def test_a_recorded_decision_settles_it(self):
        self.assertEqual(self.out["op-f"], Outcome.CONFIRMED)


class Rules(unittest.TestCase):
    def test_decision_without_reason_is_refused(self):
        events = [{"kind": "sent", "op": "x"},
                  {"kind": "decision", "op": "x", "outcome": "failed"}]
        with self.assertRaises(ValueError):
            mod.classify(events)

    def test_authoritative_not_found_is_failed(self):
        events = [{"kind": "sent", "op": "x"},
                  {"kind": "timeout", "op": "x"},
                  {"kind": "status", "op": "x", "found": False,
                   "authoritative": True}]
        self.assertEqual(mod.classify(events), Outcome.FAILED)

    def test_receipt_beats_a_later_timeout(self):
        events = [{"kind": "sent", "op": "x"},
                  {"kind": "response", "op": "x", "ok": True,
                   "receipt": {}},
                  {"kind": "timeout", "op": "x"}]
        self.assertEqual(mod.classify(events), Outcome.CONFIRMED)


class TwoFaultsOneLog(unittest.TestCase):
    """LOST_REPLY and NOT_DELIVERED leave the same log behind."""

    def run_with(self, fault):
        shop = Storefront(faults=[fault])
        log = RunLog()
        call(log, shop, "op-1", "set_description",
             sku="SKU-1", text="new")
        return shop, log

    def test_the_logs_match_and_both_are_unknown(self):
        shop_a, log_a = self.run_with(Fault.LOST_REPLY)
        shop_b, log_b = self.run_with(Fault.NOT_DELIVERED)
        kinds = lambda log: [e["kind"] for e in log.events]
        self.assertEqual(kinds(log_a), kinds(log_b))
        self.assertEqual(mod.summarize(log_a)["op-1"], Outcome.UNKNOWN)
        self.assertEqual(mod.summarize(log_b)["op-1"], Outcome.UNKNOWN)
        # Only the other system knows the difference.
        self.assertIsNotNone(shop_a.status("op-1"))
        self.assertIsNone(shop_b.status("op-1"))


if __name__ == "__main__":
    unittest.main()
