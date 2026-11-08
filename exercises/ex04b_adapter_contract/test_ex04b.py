"""Checks for exercise 4b. Run: python3 -m lab check 4b"""
import unittest

from lab import target
from lab.outcomes import Outcome
from lab.synthetic_provider import LOOKUP, SEND

EX = "ex04b_adapter_contract"
mod = target.load(EX)

DAY = 24 * 3600
YOUNG = 60          # a key sent a minute ago
OLD = DAY + 1       # past the synthetic provider's retention
TRUSTED = dict(mod.CONTRACT, lookup_authoritative=True)


class Send(unittest.TestCase):
    def test_paid_is_confirmed(self):
        self.assertEqual(mod.adapt_send(SEND["paid"], YOUNG),
                         (Outcome.CONFIRMED, frozenset({"record"})))

    def test_declined_is_failed(self):
        self.assertEqual(mod.adapt_send(SEND["declined"], YOUNG),
                         (Outcome.FAILED, frozenset({"send_again"})))

    def test_timeout_and_gateway_are_unknown_not_failed(self):
        for name in ("timeout", "gateway"):
            with self.subTest(reply=name):
                out, steps = mod.adapt_send(SEND[name], YOUNG)
                self.assertEqual(out, Outcome.UNKNOWN)
                self.assertEqual(steps, {"lookup", "escalate",
                                         "resend_same_key"})

    def test_accepted_is_unknown_and_never_resent(self):
        out, steps = mod.adapt_send(SEND["accepted"], YOUNG)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertEqual(steps, {"lookup", "escalate"})

    def test_an_unrecognized_reply_escalates(self):
        for raw in ({"status": 200, "body": {}},
                    {"status": 302, "body": None},
                    {"status": 400, "body": None}):
            with self.subTest(raw=raw):
                self.assertEqual(mod.adapt_send(raw, YOUNG),
                                 (Outcome.UNKNOWN,
                                  frozenset({"escalate"})))


class Lookup(unittest.TestCase):
    def test_found_is_confirmed(self):
        self.assertEqual(mod.adapt_lookup(LOOKUP["found"], YOUNG),
                         (Outcome.CONFIRMED, frozenset({"record"})))

    def test_failed_state_is_failed(self):
        out, _ = mod.adapt_lookup(LOOKUP["failed"], YOUNG)
        self.assertEqual(out, Outcome.FAILED)

    def test_pending_is_unknown_and_never_resent(self):
        out, steps = mod.adapt_lookup(LOOKUP["pending"], YOUNG)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertNotIn("resend_same_key", steps)

    def test_a_miss_is_not_a_failure_by_default(self):
        out, steps = mod.adapt_lookup(LOOKUP["not_found"], YOUNG)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertIn("resend_same_key", steps)

    def test_the_contract_decides_what_a_miss_means(self):
        out, _ = mod.adapt_lookup(LOOKUP["not_found"], YOUNG, TRUSTED)
        self.assertEqual(out, Outcome.FAILED)

    def test_a_forgotten_key_proves_nothing(self):
        out, steps = mod.adapt_lookup(LOOKUP["not_found"], OLD, TRUSTED)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertEqual(steps, {"escalate"})


class Invariants(unittest.TestCase):
    """Every reply, at every key age, under both contracts."""

    # region: ex04b_sweep
    def test_no_mapping_resends_a_forgotten_key(self):
        replies = [(mod.adapt_send, r) for r in SEND.values()]
        replies += [(mod.adapt_lookup, r) for r in LOOKUP.values()]
        for contract in (mod.CONTRACT, TRUSTED):
            for adapt, raw in replies:
                for age in (0, YOUNG, DAY - 1, DAY, OLD):
                    out, steps = adapt(raw, age, contract)
                    if "resend_same_key" in steps:
                        self.assertEqual(out, Outcome.UNKNOWN)
                        self.assertLess(age, DAY)
                    if out == Outcome.CONFIRMED:
                        self.assertEqual(steps, {"record"})
                    if out == Outcome.UNKNOWN:
                        self.assertIn("escalate", steps)
    # endregion


if __name__ == "__main__":
    unittest.main()
