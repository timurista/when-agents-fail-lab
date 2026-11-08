"""Checks for exercise 12. Run: python3 -m lab check 12"""
import unittest

from lab import target
from lab.agent import call
from lab.outcomes import Outcome
from lab.runlog import RunLog
from lab.tools import Fault, Mailer, Payments, Storefront

EX = "ex12_handoff_note"
mod = target.load(EX)


def paused_return():
    return RunLog.load(target.fixture(EX, "paused-return.jsonl"))


class PausedReturn(unittest.TestCase):
    def setUp(self):
        self.log = paused_return()
        self.note = mod.handoff(self.log)

    def test_goal_and_pause(self):
        self.assertTrue(self.note["goal"].startswith("Return for"))
        self.assertEqual(self.note["paused"]["kind"], "pause")

    def test_settled_points_at_its_own_proof(self):
        by_seq = {e["seq"]: e for e in self.log.events}
        got = {s["op"]: s["outcome"] for s in self.note["settled"]}
        self.assertEqual(got, {"op-7730-stock": Outcome.CONFIRMED,
                               "op-5531-refund-a": Outcome.FAILED})
        for s in self.note["settled"]:
            proof = by_seq[s["evidence"]]
            self.assertEqual(proof["op"], s["op"])
            self.assertIn(proof["kind"], {"response", "status",
                                          "decision", "cancel_ack"})

    def test_unknown_and_unfinished(self):
        self.assertEqual([u["op"] for u in self.note["unknown"]],
                         ["op-5531-refund-b"])
        self.assertEqual([u["op"] for u in self.note["unfinished"]],
                         ["op-5531-email"])

    def test_claims(self):
        self.assertEqual(self.note["stale"], [
            {"claim": "SKU-7730 says Back in stock", "evidence": 4,
             "changed": 15}])
        self.assertEqual(self.note["unsupported"],
                         [{"claim": "Refund for ORD-5531 issued"}])

    def test_one_next_action_and_it_is_read_only(self):
        act = self.note["next_action"]
        self.assertEqual((act["kind"], act["target"]),
                         ("ask", "op-5531-refund-b"))

    def test_do_not(self):
        got = {(r["target"], r["why"]) for r in self.note["do_not"]}
        self.assertEqual(got, {
            ("op-5531-refund-b", "unknown"),
            ("op-5531-email", "after_unknown"),
            ("op-7730-stock", "confirmed"),
            ("op-5531-refund-a", "failed"),
            ("SKU-7730 says Back in stock", "stale"),
            ("Refund for ORD-5531 issued", "unsupported"),
        })

    def test_render_fits_the_page(self):
        text = mod.render(self.note)
        self.assertTrue(all(len(line) <= 72
                            for line in text.splitlines()))
        self.assertIn("ask payments whether op-5531-refund-b", text)


class Rules(unittest.TestCase):
    def test_settling_the_refund_moves_to_the_stale_claim(self):
        log = paused_return()
        log.record("status", "op-5531-refund-b", found=True,
                   receipt={"refund": "rf-0001"})
        act = mod.handoff(log)["next_action"]
        self.assertEqual((act["kind"], act["target"]),
                         ("recheck", "SKU-7730 says Back in stock"))

    def test_seq_decides_staleness_not_the_clock(self):
        log = RunLog()
        log.record("intent", "op-1", tool="storefront", action="x")
        log.record("sent", "op-1")
        log.record("response", "op-1", ok=True, receipt={}, t=50.0)
        log.record("change", None, subject="SKU-1", t=10.0)
        log.record("claim", None, subject="SKU-1", text="it is live",
                   evidence=3)
        claims = mod.check_claims(log)
        self.assertEqual([c["claim"] for c in claims["stale"]],
                         ["it is live"])

    def test_a_change_to_another_subject_is_not_staleness(self):
        log = paused_return()
        log.events = [e for e in log.events if e["kind"] != "change"]
        log.record("change", None, subject="SKU-0001")
        self.assertEqual(mod.check_claims(log)["stale"], [])

    def test_unknown_with_no_lookup_escalates(self):
        log = RunLog()
        call(log, Mailer([Fault.LOST_REPLY]), "op-mail", "send",
             to="a@example.test", subject="hi")
        act = mod.handoff(log)["next_action"]
        self.assertEqual((act["kind"], act["target"]),
                         ("escalate", "op-mail"))

    def test_nothing_open_means_close(self):
        log = RunLog()
        call(log, Storefront(), "op-1", "set_description",
             sku="SKU-1", text="x")
        self.assertEqual(mod.handoff(log)["next_action"]["kind"],
                         "close")


class DepartureDrill(unittest.TestCase):
    """A scripted next owner who does only what the note allows."""

    def build(self, fault):
        """Stock confirmed, refund under `fault`, email planned."""
        self.shop, self.mail = Storefront(), Mailer()
        self.pay = Payments([fault])
        self.log = RunLog()
        call(self.log, self.shop, "op-stock", "set_description",
             sku="SKU-7730", text="Back in stock")
        call(self.log, self.pay, "op-refund", "refund",
             order="ORD-5531", amount=58.0, key="ORD-5531-refund")
        self.log.record("intent", "op-email", tool="mailer",
                        action="send",
                        args={"to": "c@example.test",
                              "subject": "Refund"})
        self.log.record("pause", None, reason="token budget exhausted")

    def steward(self, limit=6):
        tools = {"storefront": self.shop, "payments": self.pay,
                 "mailer": self.mail}
        for _ in range(limit):
            note = mod.handoff(self.log)
            act = note["next_action"]
            if act["kind"] == "close":
                return note
            if act["kind"] == "ask":
                tool = next(tools[u["tool"]] for u in note["unknown"]
                            if u["op"] == act["target"])
                receipt = tool.status(act["target"])
                self.log.record("status", act["target"],
                                found=receipt is not None,
                                receipt=receipt, authoritative=False)
            elif act["kind"] == "decide":
                intent = next(e for e in self.log.for_op(act["target"])
                              if e["kind"] == "intent")
                call(self.log, tools[intent["tool"]], act["target"],
                     intent["action"], **intent["args"])
            else:
                self.fail(f"unexpected next action {act}")
        return mod.handoff(self.log)

    def test_lost_reply_is_found_then_the_email_goes_once(self):
        self.build(Fault.LOST_REPLY)
        note = self.steward()
        self.assertEqual(note["next_action"]["kind"], "close")
        self.assertEqual(len(self.pay.refunds), 1)
        self.assertEqual(self.pay.calls, 1)
        self.assertEqual(len(self.mail.outbox), 1)

    def test_lost_request_stays_unknown_and_blocks_the_email(self):
        self.build(Fault.NOT_DELIVERED)
        note = self.steward()
        self.assertEqual(note["next_action"]["kind"], "ask")
        self.assertEqual(self.pay.refunds, [])
        self.assertEqual(self.pay.calls, 1)
        self.assertEqual(self.mail.outbox, [])


if __name__ == "__main__":
    unittest.main()
