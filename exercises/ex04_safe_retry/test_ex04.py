"""Checks for exercise 4. Run: python3 -m lab check 04"""
import itertools
import unittest
from unittest import mock

from lab import target
from lab.agent import call
from lab.clock import FakeClock
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Mailer, Payments, Storefront

EX = "ex04_safe_retry"
mod = target.load(EX)

REFUND = {"order": "O-5520", "amount": 4200, "key": "refund:op-5520"}


def run(tool, action, args, attempts=3, op="op-5520"):
    clock = FakeClock()
    log = RunLog(clock)
    with mock.patch("time.sleep", side_effect=AssertionError(
            "use the FakeClock, not real sleeps")):
        out, receipt = mod.retry_safely(log, tool, op, action,
                                        dict(args), clock, attempts)
    tool.settle()  # anything still queued lands now
    return out, receipt, log


def kinds(log):
    return [e["kind"] for e in log.events]


class Backoff(unittest.TestCase):
    def test_doubles_and_caps(self):
        self.assertEqual([mod.backoff(n) for n in (1, 2, 3, 4)],
                         [1.0, 2.0, 4.0, 8.0])
        self.assertEqual(mod.backoff(10), 30.0)

    def test_sends_land_on_predictable_times(self):
        _, _, log = run(Payments(faults=[Fault.NOT_DELIVERED] * 2),
                        "refund", REFUND)
        sent = [e["t"] for e in log.events if e["kind"] == "sent"]
        self.assertEqual(sent, [0.0, 1.0, 3.0])


class Payments_(unittest.TestCase):
    def test_lost_reply_is_found_not_resent(self):
        pay = Payments(faults=[Fault.LOST_REPLY])
        out, receipt, log = run(pay, "refund", REFUND)
        self.assertEqual(out, Outcome.CONFIRMED)
        self.assertEqual(pay.calls, 1)
        self.assertEqual(len(pay.refunds), 1)
        self.assertEqual(receipt, pay.refunds[0])

    def test_not_delivered_is_resent_with_the_same_key(self):
        pay = Payments(faults=[Fault.NOT_DELIVERED])
        out, _, log = run(pay, "refund", REFUND)
        self.assertEqual(out, Outcome.CONFIRMED)
        self.assertEqual(pay.calls, 2)
        hashes = {e["request_hash"] for e in log.events
                  if e["kind"] == "intent"}
        self.assertEqual(len(hashes), 1, "every attempt is one request")

    def test_a_key_is_required(self):
        args = {k: v for k, v in REFUND.items() if k != "key"}
        with self.assertRaises(ValueError):
            run(Payments(), "refund", args)

    def test_first_rejection_is_failed_and_not_retried(self):
        pay = Payments(faults=[Fault.REJECT])
        out, _, _ = run(pay, "refund", REFUND)
        self.assertEqual(out, Outcome.FAILED)
        self.assertEqual(pay.calls, 1)

    def test_rejected_retry_after_a_queued_first_is_unknown(self):
        pay = Payments(faults=[Fault.LATE_APPLY, Fault.REJECT])
        out, _, log = run(pay, "refund", REFUND)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertEqual(kinds(log)[-1], "escalate")
        self.assertEqual(len(pay.refunds), 1)  # the first one landed

    def test_out_of_attempts_escalates(self):
        pay = Payments(faults=[Fault.NOT_DELIVERED] * 5)
        out, _, log = run(pay, "refund", REFUND, attempts=3)
        self.assertEqual(out, Outcome.UNKNOWN)
        self.assertEqual(pay.calls, 3)
        self.assertEqual(kinds(log)[-1], "escalate")


class FaultSchedules(unittest.TestCase):
    """Every combination of faults across three calls."""

    # region: ex04_schedules
    def test_never_a_doubled_refund(self):
        for sched in itertools.product(list(Fault), repeat=3):
            with self.subTest(schedule=[f.value for f in sched]):
                pay = Payments(faults=list(sched))
                out, receipt, _ = run(pay, "refund", REFUND)
                self.assertLessEqual(len(pay.refunds), 1)
                if out == Outcome.CONFIRMED:
                    self.assertEqual(len(pay.refunds), 1)
                    self.assertEqual(receipt, pay.refunds[0])
                if out == Outcome.FAILED:
                    self.assertEqual(pay.refunds, [])
    # endregion

    # region: ex04_blind
    def test_the_schedule_catches_a_blind_retry(self):
        """The same check, run on the obvious loop, must fail."""
        def blind(log, tool, op, args):
            for _ in range(3):
                args = dict(args, key=f"{op}:{tool.calls}")
                if call(log, tool, op, "refund", **args):
                    return
        pay = Payments(faults=[Fault.LOST_REPLY])
        blind(RunLog(), pay, "op-5520", REFUND)
        self.assertEqual(len(pay.refunds), 2)
    # endregion


class Storefront_(unittest.TestCase):
    ARGS = {"sku": "SKU-9102", "text": "Enamel camp mug, 350 ml"}

    def test_lost_reply_is_found_by_status(self):
        shop = Storefront(faults=[Fault.LOST_REPLY])
        out, _, _ = run(shop, "set_description", self.ARGS)
        self.assertEqual(out, Outcome.CONFIRMED)
        self.assertEqual(shop.calls, 1)

    def test_a_late_apply_and_a_resend_leave_the_same_text(self):
        shop = Storefront(faults=[Fault.LATE_APPLY])
        out, _, _ = run(shop, "set_description", self.ARGS)
        self.assertEqual(out, Outcome.CONFIRMED)
        self.assertEqual(shop.catalog["SKU-9102"]["text"],
                         self.ARGS["text"])


class Mailer_(unittest.TestCase):
    ARGS = {"to": "customer-5520@example.test",
            "subject": "Your refund for O-5520"}

    def test_unanswered_mail_escalates_and_is_never_resent(self):
        for fault in (Fault.LOST_REPLY, Fault.NOT_DELIVERED,
                      Fault.LATE_APPLY):
            with self.subTest(fault=fault.value):
                mail = Mailer(faults=[fault])
                out, _, log = run(mail, "send", self.ARGS)
                self.assertEqual(out, Outcome.UNKNOWN)
                self.assertEqual(mail.calls, 1)
                self.assertEqual(kinds(log)[-1], "escalate")
                self.assertTrue(log.events[-1]["reason"])

    def test_answered_mail_is_confirmed_once(self):
        mail = Mailer()
        out, _, _ = run(mail, "send", self.ARGS)
        self.assertEqual(out, Outcome.CONFIRMED)
        self.assertEqual(len(mail.outbox), 1)


if __name__ == "__main__":
    unittest.main()
