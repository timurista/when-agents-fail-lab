"""Checks for exercise 14. Run: python3 -m lab check 14"""
import unittest
from unittest import mock

from lab import drill, target
from lab.outcomes import Outcome
from lab.runlog import RunLog

EX = "ex14_drill"
mod = target.load(EX)
KEY = drill.load_key()


def fresh():
    return drill.stage()


class TheIncident(unittest.TestCase):
    def test_the_printed_log_is_the_staged_log(self):
        saved = RunLog.load(target.fixture(EX, "incident.jsonl"))
        self.assertEqual(saved.events, fresh().log.events)


class Stages(unittest.TestCase):
    def setUp(self):
        self.incident = fresh()
        self.report = mod.run_drill(self.incident)

    def test_classify_from_the_log_alone(self):
        self.assertEqual(self.report["before"], KEY["before"])

    def test_reconcile_moves_only_what_evidence_moves(self):
        self.assertEqual(self.report["after"], KEY["after"])

    def test_reconcile_records_its_lookups(self):
        asked = {e["op"] for e in self.incident.log.events
                 if e["kind"] == "status"}
        self.assertNotIn("op-m5103", asked)  # the mailer can't answer
        self.assertTrue({"op-r5103", "op-s4471", "op-r5105",
                         "op-s9102"} <= asked)
        for e in self.incident.log.events:
            if e["kind"] == "status":
                self.assertIn("authoritative", e)

    def test_every_decision_is_allowed(self):
        for op, ok in KEY["allowed"].items():
            self.assertIn(self.report["plan"][op], ok, op)

    def test_messages_pass_the_lint(self):
        self.assertEqual(drill.lint(self.report, KEY["after"]), [])

    def test_handoff_names_unknowns_and_stale_claims(self):
        note = self.report["handoff"]
        self.assertEqual(sorted(note["unknown"]),
                         ["op-m5103", "op-r5105", "op-s9102"])
        self.assertEqual(sorted(note["stale_claims"]),
                         KEY["stale_claims"])

    def test_the_drill_passes(self):
        result = drill.score(self.report, self.incident, KEY)
        self.assertEqual(result["critical"], [])
        self.assertIsNone(result["stalled_at"])
        self.assertTrue(result["passed"])


# region: ex14_late_apply
class AMissIsNotAFailure(unittest.TestCase):
    """Regression: a refund still queued when the lookup misses."""

    def test_a_miss_stays_unknown_when_the_refund_lands_later(self):
        incident = drill.stage(late=True)
        report = mod.run_drill(incident)
        self.assertEqual(report["after"]["op-r5105"], "unknown")
        pay = incident.tools["payments"]
        pay.settle()  # the queued refund lands after the lookup
        self.assertIsNotNone(pay.lookup("k-r5105"))
        result = drill.score(report, incident, KEY)
        self.assertEqual(result["critical"], [])  # paid once

    def test_without_closure_the_miss_is_not_trusted(self):
        incident = fresh()
        mod.reconcile(incident)
        miss = [e for e in incident.log.for_op("op-r5105")
                if e["kind"] == "status"]
        self.assertEqual([e["authoritative"] for e in miss], [False])

    def test_claiming_a_closure_the_fake_lacks_is_caught(self):
        sheet = dict(drill.CAPABILITIES["payments"],
                     authoritative=True, closes="deadline")
        with mock.patch.dict(drill.CAPABILITIES, payments=sheet):
            incident = drill.stage(late=True)
            report = mod.run_drill(incident)
        self.assertEqual(report["after"]["op-r5105"], "failed")
        result = drill.score(report, incident, KEY)
        self.assertIn("op-r5105: unknown reported as failed",
                      result["critical"])
# endregion


class Assistance(unittest.TestCase):
    """A pass with help is recorded apart from a pass without it."""

    def test_independent_and_assisted_are_separate(self):
        incident = fresh()
        report = mod.run_drill(incident)
        alone = drill.score(report, incident, KEY)
        self.assertEqual(alone["recovery"], "recovered independently")
        incident = fresh()
        report = mod.run_drill(incident)
        report["assists"] = ["facilitator explained the key lookup"]
        helped = drill.score(report, incident, KEY)
        self.assertTrue(helped["passed"])
        self.assertEqual(helped["recovery"],
                         "recovered with assistance")


class TheRubricCatchesHarm(unittest.TestCase):
    """A rubric that passes everything measures nothing."""

    def test_blind_retry_fails_critically(self):
        incident = fresh()
        result = drill.score(drill.blind_report(incident), incident,
                             KEY)
        self.assertFalse(result["passed"])
        self.assertIn("ORD-5104 refunded 2 times", result["critical"])
        self.assertIn("c5103@example.com got the same email 2 times",
                      result["critical"])
        self.assertIn("op-r5105: unknown reported as failed",
                      result["critical"])
        self.assertEqual(result["recovery"], "not recovered")

    def test_email_before_its_refund_is_caught(self):
        incident = fresh()
        report = mod.run_drill(incident)
        report["plan"]["op-r5105"] = "escalate"
        report["plan"]["op-m5105"] = "resume"
        result = drill.score(report, incident, KEY)
        self.assertIn("c5105@example.com told ORD-5105 was refunded",
                      result["critical"])

    def test_reconcile_never_asks_the_mailer(self):
        incident = fresh()
        mod.reconcile(incident)
        mailer_ops = {"op-m5103", "op-m5105"}
        self.assertFalse(any(e["kind"] == "status"
                             and e["op"] in mailer_ops
                             for e in incident.log.events))


class Classify(unittest.TestCase):
    def test_a_weak_miss_stays_unknown(self):
        events = [{"kind": "sent", "op": "x"},
                  {"kind": "timeout", "op": "x"},
                  {"kind": "status", "op": "x", "found": False,
                   "authoritative": False}]
        self.assertEqual(mod.classify(events), Outcome.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
