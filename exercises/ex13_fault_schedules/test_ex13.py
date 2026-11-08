"""Checks for exercise 13. Run: python3 -m lab check 13"""
import unittest

from lab import target
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault

EX = "ex13_fault_schedules"
mod = target.load(EX)
N, LR, ND, RJ, LA = (Fault.NONE, Fault.LOST_REPLY, Fault.NOT_DELIVERED,
                     Fault.REJECT, Fault.LATE_APPLY)


class Schedules(unittest.TestCase):
    def test_every_combination_once(self):
        got = list(mod.schedules({"payments": 2, "mailer": 1}))
        self.assertEqual(len(got), 5 ** 3)
        self.assertEqual(got[0], {"payments": (N, N), "mailer": (N,)})
        keys = {tuple(sorted(s.items())) for s in got}
        self.assertEqual(len(keys), 125)

    def test_the_full_shape(self):
        self.assertEqual(sum(1 for _ in mod.schedules(mod.SHAPE)), 3125)

    def test_a_schedule_is_repeatable(self):
        sched = {"payments": (LA, LR, N), "mailer": (LR,),
                 "storefront": (ND,)}
        a = mod.run(mod.process_return, sched)["log"].events
        b = mod.run(mod.process_return, sched)["log"].events
        self.assertEqual(a, b)


class Invariants(unittest.TestCase):
    def broken(self, workflow, **schedule):
        return mod.check_invariants(mod.run(workflow, schedule))

    def test_clean_run_holds(self):
        self.assertEqual(self.broken(mod.process_return_naive), [])

    def test_lost_reply_doubles_the_naive_refund(self):
        self.assertEqual(
            self.broken(mod.process_return_naive, payments=(LR,)),
            ["doubled_refund"])

    def test_naive_calls_a_lost_request_failed(self):
        self.assertIn(
            "unknown_marked_failed",
            self.broken(mod.process_return_naive,
                        payments=(ND, ND, ND)))

    def test_naive_calls_an_applied_write_failed(self):
        self.assertEqual(
            self.broken(mod.process_return_naive, storefront=(LR,)),
            ["applied_marked_failed", "unknown_marked_failed"])

    def test_v1_sends_on_an_expired_approval(self):
        self.assertEqual(
            self.broken(mod.process_return_v1, payments=(ND, ND, N)),
            ["expired_approval"])

    def test_v1_lets_a_rejected_retry_hide_a_late_refund(self):
        self.assertEqual(
            self.broken(mod.process_return_v1, payments=(LA, RJ)),
            ["applied_marked_failed"])

    def test_fixed_version_holds_on_both(self):
        self.assertEqual(
            self.broken(mod.process_return, payments=(ND, ND, N)), [])
        self.assertEqual(
            self.broken(mod.process_return, payments=(LA, RJ)), [])


class Explore(unittest.TestCase):
    def rules(self, workflow):
        return {r for _, broken in mod.explore(workflow, mod.SHAPE)
                for r in broken}

    def test_naive_breaks_every_rule(self):
        self.assertEqual(self.rules(mod.process_return_naive), {
            "doubled_refund", "doubled_email", "unknown_marked_failed",
            "applied_marked_failed", "expired_approval"})

    def test_v1_breaks_two(self):
        self.assertEqual(self.rules(mod.process_return_v1),
                         {"expired_approval", "applied_marked_failed"})

    def test_fixed_version_holds_everywhere(self):
        self.assertEqual(mod.explore(mod.process_return, mod.SHAPE), [])


# region: ex13_control
class TheDoNothingControl(unittest.TestCase):
    """Safety alone rewards doing nothing. Completion is separate."""

    def test_doing_nothing_is_safe_everywhere(self):
        self.assertEqual(
            mod.explore(mod.process_return_empty, mod.SHAPE), [])

    def test_doing_nothing_never_reaches_the_goal(self):
        got = mod.assess(mod.process_return_empty)
        self.assertEqual(got["unsafe"], [])
        self.assertFalse(got["completes"])

    def test_the_fixed_version_is_safe_and_completes(self):
        got = mod.assess(mod.process_return)
        self.assertEqual(got["unsafe"], [])
        self.assertTrue(got["completes"])
# endregion


# region: ex13_regression
class IncidentORD5531(unittest.TestCase):
    """Synthetic incident: ORD-5531 was refunded twice."""

    def setUp(self):
        self.log = RunLog.load(
            target.fixture(EX, "incident-ord-5531.jsonl"))
        self.cases = list(mod.incident_schedules(self.log))

    def test_the_log_still_reads_as_it_did(self):  # (1)
        self.assertEqual(mod.classify(self.log.for_op("op-refund")),
                         Outcome.CONFIRMED)
        self.assertEqual(mod.consistent_faults(self.log)["payments"],
                         [(LR, ND, LA), (N,)])

    def test_every_schedule_the_log_allows_now_holds(self):  # (2)
        self.assertEqual(len(self.cases), 3)
        for schedule in self.cases:
            with self.subTest(schedule=mod.describe(schedule)):
                result = mod.run(mod.process_return, schedule)
                self.assertEqual(mod.check_invariants(result), [])

    def test_the_old_code_fails_it(self):  # (3)
        broken = [mod.check_invariants(
                      mod.run(mod.process_return_naive, s))
                  for s in self.cases]
        self.assertIn(["doubled_refund"], broken)
# endregion


if __name__ == "__main__":
    unittest.main()
