"""Checks for exercise 3. Run: python3 -m lab check 03"""
import unittest

from lab import target
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Storefront

EX = "ex03_return_summary"
mod = target.load(EX)
A = mod.Action
O = Outcome


def load():
    return RunLog.load(target.fixture(EX, "return-run.jsonl"))


class Summary(unittest.TestCase):
    def setUp(self):
        self.summary = mod.return_summary(load())
        self.cards = {c.op: c for c in self.summary.cards}

    def test_local_state_is_said_once_not_per_card(self):
        self.assertEqual(self.summary.local, "stopped")
        self.assertEqual(len(self.cards), 7)

    def test_one_outcome_per_operation(self):
        self.assertEqual({op: c.outcome for op, c in self.cards.items()},
                         {"op-4471": O.CONFIRMED, "op-r310": O.CONFIRMED,
                          "op-m310": O.UNKNOWN, "op-r311": O.CANCELED,
                          "op-5530": O.FAILED, "op-9102": O.UNKNOWN,
                          "op-2208": O.NEVER_SENT})

    def test_actions_match_outcome_and_tool(self):
        want = {
            "op-4471": {A.INSPECT, A.REVERSE},     # reversible
            "op-r310": {A.INSPECT, A.COMPENSATE},  # a refund is not
            "op-m310": {A.RECONCILE},
            "op-r311": {A.INSPECT, A.RESUME},
            "op-5530": {A.INSPECT, A.DISCARD},
            "op-9102": {A.RECONCILE},
            "op-2208": {A.DISCARD, A.RESUME},
        }
        for op, actions in want.items():
            self.assertEqual(set(self.cards[op].actions), actions, op)

    def test_every_card_names_its_evidence(self):
        c = self.cards
        self.assertIn("rcpt-0001", c["op-4471"].evidence)
        self.assertIn("rf-0001", c["op-r310"].evidence)
        self.assertIn("archived", c["op-5530"].evidence)
        self.assertIn("cancel", c["op-r311"].evidence)
        for card in self.summary.cards:
            self.assertTrue(card.evidence and card.evidence != "?")

    def test_unknown_names_the_next_evidence_step(self):
        shop = self.cards["op-9102"].next_step
        mail = self.cards["op-m310"].next_step
        self.assertIn("status of op-9102", shop)
        self.assertIn("no lookup", mail)
        for step in (shop, mail):
            self.assertIn("do not resend", step)

    def test_targets_come_from_the_intent(self):
        self.assertEqual(self.cards["op-r310"].target, "FS-310")
        self.assertEqual(self.cards["op-2208"].target, "SKU-2208")


class Refusals(unittest.TestCase):
    def setUp(self):
        self.cards = {c.op: c for c in mod.return_summary(load()).cards}

    def test_reverse_is_allowed_only_on_confirmed_reversible(self):
        mod.check(self.cards["op-4471"], A.REVERSE)
        for op in ("op-r310", "op-m310", "op-r311", "op-5530",
                   "op-9102", "op-2208"):
            with self.assertRaises(mod.Refused, msg=op):
                mod.check(self.cards[op], A.REVERSE)

    def test_irreversible_refusal_says_compensation(self):
        with self.assertRaises(mod.Refused) as ctx:
            mod.check(self.cards["op-r310"], A.REVERSE)
        self.assertIn("compensation", str(ctx.exception))

    def test_unknown_refusal_repeats_the_next_step(self):
        card = self.cards["op-9102"]
        for action in (A.RESUME, A.REVERSE, A.DISCARD):
            with self.assertRaises(mod.Refused) as ctx:
                mod.check(card, action)
            self.assertIn(card.next_step, str(ctx.exception))

    def test_the_policy_never_offers_more_than_it_should(self):
        for outcome in Outcome:
            for reversible in (True, False):
                acts = set(mod.allowed(outcome, reversible))
                if A.REVERSE in acts:
                    self.assertEqual(outcome, O.CONFIRMED)
                    self.assertTrue(reversible)
                if outcome == O.UNKNOWN:
                    self.assertEqual(acts, {A.RECONCILE})
                if A.RESUME in acts:
                    self.assertIn(outcome, {O.CANCELED, O.NEVER_SENT})


class TimeChangesNothing(unittest.TestCase):
    def test_five_more_timeouts_leave_the_card_alone(self):
        log = load()
        before = {c.op: c for c in mod.return_summary(log).cards}
        for _ in range(5):
            log.record("timeout", "op-9102")
        after = {c.op: c for c in mod.return_summary(log).cards}
        self.assertEqual(after["op-9102"], before["op-9102"])


class StoppedProducer(unittest.TestCase):
    """Stop is pressed while SKU-9102's write is in flight."""

    def setUp(self):
        self.log = RunLog()
        runner_box = []

        class Shop(Storefront):
            def set_description(shop, op, sku, text):
                if sku == "SKU-9102":
                    runner_box[0].stop("operator")
                return Storefront.set_description(shop, op, sku, text)

        self.shop = Shop(faults=[Fault.NONE, Fault.LATE_APPLY])
        self.runner = mod.Runner(self.log, {"storefront": self.shop})
        runner_box.append(self.runner)
        for sku, text in (("SKU-4471", "Waxed canvas tote, 18 L"),
                          ("SKU-9102", "Enamel camp mug, 350 ml"),
                          ("SKU-2208", "Wool beanie, charcoal")):
            self.runner.submit(f"op-{sku[4:]}", "storefront",
                               "set_description", sku=sku, text=text)
        self.runner.run()

    def test_three_writes_three_outcomes(self):
        cards = mod.return_summary(self.log).cards
        self.assertEqual([(c.op, c.outcome) for c in cards],
                         [("op-4471", O.CONFIRMED),
                          ("op-9102", O.UNKNOWN),
                          ("op-2208", O.NEVER_SENT)])

    def test_stopped_refuses_new_work(self):
        count = len(self.log.events)
        with self.assertRaises(mod.Stopped):
            self.runner.submit("op-7001", "storefront",
                               "set_description", sku="SKU-7001",
                               text="Trail map")
        self.runner.run()
        self.assertEqual(len(self.log.events), count)
        self.assertNotIn("op-2208", self.shop.applied)

    def test_stop_is_recorded_once(self):
        self.runner.stop("operator")
        stops = [e for e in self.log.events if e["kind"] == "stop"]
        self.assertEqual(len(stops), 1)

    def test_the_late_write_still_lands(self):
        # Stop didn't reach the storefront's queue. Only a lookup
        # can tell you, which is why the card says to ask.
        self.shop.settle()
        self.assertIsNotNone(self.shop.status("op-9102"))


if __name__ == "__main__":
    unittest.main()
