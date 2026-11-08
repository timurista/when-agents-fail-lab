"""Checks for exercise 8. Run: python3 -m lab check 08"""
import shutil
import tempfile
import unittest

from lab import target
from lab.agent import request_hash
from lab.clock import FakeClock
from lab.runlog import RunLog
from lab.tools import Mailer, Payments

EX = "ex08_approval_binding"
mod = target.load(EX)

REFUND = {"order": "ORD-5521", "amount": 4800, "key": "rf-ORD-5521"}
EMAIL = {"to": "jo.park@example.com",
         "subject": "Your refund for ORD-5521"}


def kinds(log, op):
    return [e["kind"] for e in log.for_op(op)]


class Grant(unittest.TestCase):
    def test_binds_the_request_hash_and_an_expiry(self):
        clock = FakeClock(100)
        a = mod.grant(clock, "payments", "refund", REFUND, "maya", 900)
        self.assertEqual(a["request_hash"],
                         request_hash("payments", "refund", REFUND))
        self.assertEqual(a["expires_at"], 1000)
        self.assertEqual(a["by"], "maya")

    def test_the_agent_cannot_approve_itself(self):
        with self.assertRaises(ValueError):
            mod.grant(FakeClock(), "mailer", "send", EMAIL, mod.AGENT, 60)
        with self.assertRaises(ValueError):
            mod.grant(FakeClock(), "mailer", "send", EMAIL, "", 60)


class Check(unittest.TestCase):
    def setUp(self):
        self.a = mod.grant(FakeClock(), "payments", "refund", REFUND,
                           "maya", 900)

    def test_unchanged_request_inside_the_window_is_covered(self):
        v = mod.check(self.a, "payments", "refund", dict(REFUND), 899,
                      set())
        self.assertTrue(v.ok)
        self.assertEqual(v.reasons, [])

    def test_each_field_is_checked_on_its_own(self):
        for field, value in [("amount", 5200), ("order", "ORD-5522"),
                             ("key", "rf-other")]:
            args = dict(REFUND, **{field: value})
            v = mod.check(self.a, "payments", "refund", args, 10, set())
            self.assertFalse(v.ok, field)
            self.assertEqual(v.reasons, ["changed"], field)
            self.assertEqual(list(v.changed), [field])
            self.assertEqual(v.changed[field], (REFUND[field], value))

    def test_a_different_action_is_a_different_request(self):
        v = mod.check(self.a, "payments", "charge", REFUND, 10, set())
        self.assertEqual(v.changed, {"action": ("refund", "charge")})

    def test_expiry_is_inclusive_at_the_boundary(self):
        v = mod.check(self.a, "payments", "refund", REFUND, 900, set())
        self.assertEqual(v.reasons, ["expired"])

    def test_a_spent_approval_is_refused(self):
        v = mod.check(self.a, "payments", "refund", REFUND, 10,
                      {self.a["id"]})
        self.assertIn("spent", v.reasons)

    def test_every_reason_is_reported(self):
        args = dict(REFUND, amount=1)
        v = mod.check(self.a, "payments", "refund", args, 5000,
                      {self.a["id"]})
        self.assertEqual(set(v.reasons), {"spent", "expired", "changed"})


class Act(unittest.TestCase):
    def test_changed_recipient_sends_nothing(self):
        clock, log, mailer = FakeClock(), RunLog(), Mailer()
        a = mod.grant(clock, "mailer", "send", EMAIL, "maya", 1800)
        clock.advance(660)
        asked = dict(EMAIL, to="jo.park.home@example.net")
        receipt = mod.act(log, mailer, "op-mail-5521", "send", a, clock,
                          set(), **asked)
        self.assertIsNone(receipt)
        self.assertEqual(mailer.calls, 0)
        self.assertEqual(mailer.outbox, [])
        ev = log.for_op("op-mail-5521")[-1]
        self.assertEqual(ev["kind"], "approval_refused")
        self.assertEqual(ev["reasons"], ["changed"])
        self.assertEqual(ev["changed"]["to"],
                         ["jo.park@example.com", "jo.park.home@example.net"])
        self.assertNotIn("sent", kinds(log, "op-mail-5521"))

    def test_renewed_approval_sends_once_to_the_new_address(self):
        clock, log, mailer = FakeClock(), RunLog(), Mailer()
        spent = set()
        old = mod.grant(clock, "mailer", "send", EMAIL, "maya", 1800)
        clock.advance(660)
        asked = dict(EMAIL, to="jo.park.home@example.net")
        mod.act(log, mailer, "op-mail-5521", "send", old, clock, spent,
                **asked)
        clock.advance(300)
        new = mod.renew(old, asked, clock, "maya", 600)
        self.assertEqual(new["renews"], old["id"])
        self.assertNotEqual(new["id"], old["id"])
        receipt = mod.act(log, mailer, "op-mail-5521b", "send", new,
                          clock, spent, **asked)
        self.assertIsNotNone(receipt)
        self.assertEqual([m["to"] for m in mailer.outbox],
                         ["jo.park.home@example.net"])
        # The old approval still covers only the old address.
        self.assertFalse(mod.check(old, "mailer", "send", asked,
                                   clock.now(), spent).ok)

    def test_checked_at_the_moment_of_action_not_at_plan_time(self):
        clock, log, pay = FakeClock(), RunLog(), Payments()
        a = mod.grant(clock, "payments", "refund", REFUND, "maya", 900)
        clock.advance(100)
        plan_time = mod.check(a, "payments", "refund", REFUND,
                              clock.now(), set())
        self.assertTrue(plan_time.ok)
        clock.advance(2 * 3600)  # paused, then resumed
        receipt = mod.act(log, pay, "op-rf-5521", "refund", a, clock,
                          set(), **REFUND)
        self.assertIsNone(receipt)
        self.assertEqual(pay.refunds, [])
        self.assertEqual(log.for_op("op-rf-5521")[-1]["reasons"],
                         ["expired"])

    def test_one_approval_one_refund(self):
        clock, log, pay = FakeClock(), RunLog(), Payments()
        spent = set()
        a = mod.grant(clock, "payments", "refund", REFUND, "maya", 900)
        first = mod.act(log, pay, "op-rf-5521", "refund", a, clock,
                        spent, **REFUND)
        self.assertIsNotNone(first)
        self.assertIn(a["id"], spent)
        again = mod.act(log, pay, "op-rf-5521x", "refund", a, clock,
                        spent, **REFUND)
        self.assertIsNone(again)
        self.assertEqual(len(pay.refunds), 1)
        self.assertEqual(kinds(log, "op-rf-5521")[:2],
                         ["approval_used", "intent"])

    def test_renewal_needs_a_person(self):
        clock = FakeClock()
        old = mod.grant(clock, "mailer", "send", EMAIL, "maya", 60)
        with self.assertRaises(ValueError):
            mod.renew(old, dict(EMAIL, to="x@example.net"), clock,
                      mod.AGENT, 60)


class Consume(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_only_the_first_consume_spends_it(self):
        self.assertTrue(mod.consume(self.dir, "apr-a"))
        self.assertFalse(mod.consume(self.dir, "apr-a"))
        self.assertTrue(mod.consume(self.dir, "apr-b"))

    def test_the_spend_survives_a_restart(self):
        a = mod.grant(FakeClock(), "payments", "refund", REFUND,
                      "maya", 900)
        self.assertTrue(mod.consume(self.dir, a["id"]))
        # A restart loses the in-memory set: check alone would pass.
        self.assertTrue(mod.check(a, "payments", "refund", REFUND, 10,
                                  set()).ok)
        # The marker on disk does not forget.
        self.assertFalse(mod.consume(self.dir, a["id"]))


class Explain(unittest.TestCase):
    def test_names_what_changed_and_that_nothing_was_sent(self):
        clock = FakeClock()
        a = mod.grant(clock, "mailer", "send", EMAIL, "maya", 1800)
        asked = dict(EMAIL, to="jo.park.home@example.net")
        v = mod.check(a, "mailer", "send", asked, 2000, set())
        text = "\n".join(mod.explain(a, v))
        self.assertIn("jo.park@example.com", text)
        self.assertIn("jo.park.home@example.net", text)
        self.assertIn("expired", text)
        self.assertIn("Nothing was sent", text)
        for line in text.splitlines():
            self.assertLessEqual(len(line), 72, line)


if __name__ == "__main__":
    unittest.main()
