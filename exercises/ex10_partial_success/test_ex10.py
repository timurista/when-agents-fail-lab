"""Checks for exercise 10. Run: python3 -m lab check 10"""
import unittest

from lab import target
from lab.agent import request_hash
from lab.compensation import STEPS, reference_classify, run_workflow
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Mailer, Payments, Storefront

EX = "ex10_partial_success"
mod = target.load(EX)
classify = reference_classify()

CATALOG = {
    "SKU-4471": {"text": "Wool camp blanket, 140 x 200 cm", "version": 2},
    "SKU-4472": {"text": "Enamel camp mug, 350 ml", "version": 5},
}
COMP = STEPS[2]["compensation"]
APPROVED = {"op-7731-email": request_hash(COMP["tool"], COMP["action"],
                                          COMP["args"])}


def partial_run():
    """The run from the chapter: the second storefront write loses
    its reply, so the agent halts before the QA note."""
    tools = {"storefront": Storefront(CATALOG,
                                      faults=[Fault.NONE,
                                              Fault.LOST_REPLY]),
             "payments": Payments(), "mailer": Mailer()}
    log = run_workflow(RunLog(), tools, STEPS)
    return tools, log


def by_op(plan):
    return {item["op"]: item for item in plan}


class TheRun(unittest.TestCase):
    def test_the_fault_schedule_leaves_five_different_states(self):
        _, log = partial_run()
        got = {op: classify(log.for_op(op)) for op in log.ops()}
        self.assertEqual(got, {
            "op-4471-hold": Outcome.CONFIRMED,
            "op-7731-refund": Outcome.CONFIRMED,
            "op-7731-email": Outcome.CONFIRMED,
            "op-4472-hold": Outcome.UNKNOWN,
            "op-qa-note": Outcome.NEVER_SENT,
        })


class Planning(unittest.TestCase):
    def setUp(self):
        self.tools, self.log = partial_run()
        self.plan = mod.plan_recovery(self.log, STEPS)

    def test_one_choice_per_step(self):
        self.assertEqual({op: i["do"] for op, i in by_op(self.plan).items()},
                         {"op-4471-hold": "reverse",
                          "op-7731-refund": "leave",
                          "op-7731-email": "compensate",
                          "op-4472-hold": "wait",
                          "op-qa-note": "leave"})

    def test_newest_first(self):
        self.assertEqual([i["op"] for i in self.plan],
                         ["op-qa-note", "op-4472-hold", "op-7731-email",
                          "op-7731-refund", "op-4471-hold"])

    def test_compensation_is_a_new_request_that_needs_approval(self):
        item = by_op(self.plan)["op-7731-email"]
        self.assertTrue(item["needs_approval"])
        self.assertEqual(item["request"], COMP)

    def test_reverse_carries_the_receipt(self):
        item = by_op(self.plan)["op-4471-hold"]
        self.assertEqual(item["receipt"]["sku"], "SKU-4471")
        self.assertFalse(item["needs_approval"])

    def test_every_item_says_why(self):
        for item in self.plan:
            self.assertTrue(item["why"], item["op"])

    def test_unknown_is_never_reversed_even_on_a_reversible_tool(self):
        item = by_op(self.plan)["op-4472-hold"]
        self.assertEqual(item["do"], "wait")
        self.assertIsNone(item["request"])

    def test_nothing_to_undo_for_failed_or_canceled(self):
        step = STEPS[0]
        for outcome in (Outcome.FAILED, Outcome.CANCELED,
                        Outcome.NEVER_SENT):
            self.assertEqual(mod.plan_step(step, outcome, None)["do"],
                             "leave")


class Applying(unittest.TestCase):
    def setUp(self):
        self.tools, self.log = partial_run()
        self.plan = mod.plan_recovery(self.log, STEPS)

    def test_without_approval_only_the_reversal_happens(self):
        result = mod.apply_plan(self.plan, self.tools, self.log)
        shop = self.tools["storefront"]
        self.assertEqual(shop.catalog["SKU-4471"]["text"],
                         CATALOG["SKU-4471"]["text"])
        self.assertEqual(result["op-7731-email"], "awaiting approval")
        self.assertEqual(len(self.tools["mailer"].outbox), 1)
        self.assertEqual(len(self.tools["payments"].refunds), 1)

    def test_the_unknown_write_is_left_alone(self):
        mod.apply_plan(self.plan, self.tools, self.log)
        # The lost reply was applied; only the storefront knows that.
        shop = self.tools["storefront"]
        self.assertEqual(shop.catalog["SKU-4472"]["text"],
                         "On hold: quality check")

    def test_approved_compensation_sends_a_second_email(self):
        result = mod.apply_plan(self.plan, self.tools, self.log,
                                APPROVED)
        outbox = self.tools["mailer"].outbox
        self.assertEqual(result["op-7731-email"],
                         "compensation confirmed")
        # The recipient now has both emails. Nothing was unsent.
        self.assertEqual([m["subject"] for m in outbox],
                         [STEPS[2]["args"]["subject"],
                          COMP["args"]["subject"]])

    def test_an_approval_for_a_different_request_does_not_count(self):
        other = {"op-7731-email": request_hash("mailer", "send",
                                               {"to": "someone@else"})}
        result = mod.apply_plan(self.plan, self.tools, self.log, other)
        self.assertEqual(result["op-7731-email"], "awaiting approval")
        self.assertEqual(len(self.tools["mailer"].outbox), 1)

    def test_reverse_refuses_when_someone_edited_since(self):
        shop = self.tools["storefront"]
        shop.catalog["SKU-4471"]["text"] = "Edited by a merchandiser"
        shop.catalog["SKU-4471"]["version"] += 1
        result = mod.apply_plan(self.plan, self.tools, self.log)
        self.assertTrue(result["op-4471-hold"].startswith("refused"))
        self.assertEqual(shop.catalog["SKU-4471"]["text"],
                         "Edited by a merchandiser")

    def test_twice_is_the_same_as_once(self):
        mod.apply_plan(self.plan, self.tools, self.log, APPROVED)
        shop = self.tools["storefront"]
        version = shop.catalog["SKU-4471"]["version"]
        again = mod.plan_recovery(self.log, STEPS)
        mod.apply_plan(again, self.tools, self.log, APPROVED)
        self.assertEqual(shop.catalog["SKU-4471"]["version"], version)
        self.assertEqual(len(self.tools["mailer"].outbox), 2)
        self.assertEqual({i["do"] for i in again
                          if i["op"] != "op-4472-hold"}, {"leave"})


class Reconcile(unittest.TestCase):
    def test_a_status_answer_turns_wait_into_reverse(self):
        tools, log = partial_run()
        shop = tools["storefront"]
        # region: ex10_reconcile
        found = shop.status("op-4472-hold")
        log.record("status", "op-4472-hold", found=found is not None,
                   receipt=found)
        item = by_op(mod.plan_recovery(log, STEPS))["op-4472-hold"]
        self.assertEqual(item["do"], "reverse")
        # endregion
        mod.apply_plan([item], tools, log)
        self.assertEqual(shop.catalog["SKU-4472"]["text"],
                         CATALOG["SKU-4472"]["text"])


if __name__ == "__main__":
    unittest.main()
