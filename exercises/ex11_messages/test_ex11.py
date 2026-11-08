"""Checks for exercise 11. Run: python3 -m lab check 11"""
import json
import re
import unittest

from lab import target

EX = "ex11_messages"
mod = target.load(EX)
ITEMS = json.loads(target.fixture(EX, "items.json").read_text())
BAD = json.loads(target.fixture(EX, "bad-messages.json").read_text())
BY_OP = {i["op"]: i for i in ITEMS}
OUTCOMES = ["confirmed", "unknown", "failed", "canceled", "never_sent"]


def words(message):
    return " ".join([message["happened"], message.get("evidence", ""),
                     message["next"]] + [
        f"{a['label']} {a['reason'] or ''}" for a in message["actions"]])


def rules(problems):
    return [p.split(":")[0] for p in problems]


class OperatorMessages(unittest.TestCase):
    def test_every_generated_message_passes_its_own_lint(self):
        for item in ITEMS:
            msg = mod.operator_message(item)
            self.assertEqual(mod.lint(msg, item, "operator"), [],
                             item["op"])

    def test_unknown_is_never_called_failed(self):
        for item in ITEMS:
            if item["outcome"] == "unknown":
                text = words(mod.operator_message(item))
                self.assertNotRegex(text, r"(?i)fail|error|rejected")

    def test_unknown_offers_no_resend(self):
        msg = mod.operator_message(BY_OP["op-7713-refund"])
        resend = [a for a in msg["actions"] if a["label"] == "Resend"]
        self.assertFalse(resend[0]["enabled"])
        self.assertTrue(resend[0]["reason"])

    def test_every_disabled_action_says_why(self):
        for item in ITEMS:
            for a in mod.operator_message(item)["actions"]:
                if not a["enabled"]:
                    self.assertTrue(a["reason"], (item["op"], a))

    def test_a_correction_is_never_called_undo(self):
        text = words(mod.operator_message(BY_OP["op-7731-email"]))
        self.assertNotRegex(text, r"(?i)\bundo|unsen")
        self.assertRegex(text, r"(?i)both")

    def test_confirmed_cites_its_evidence(self):
        msg = mod.operator_message(BY_OP["op-7731-refund"])
        self.assertIn("rf-0001", msg["evidence"])

    def test_the_next_step_names_the_operation_to_ask_about(self):
        msg = mod.operator_message(BY_OP["op-4472-hold"])
        self.assertIn("op-4472-hold", msg["next"])

    def test_render_keeps_lines_inside_72_columns(self):
        for item in ITEMS:
            text = mod.render(mod.operator_message(item))
            self.assertTrue(all(len(l) <= 72 for l in text.splitlines()))


class CustomerMessages(unittest.TestCase):
    def test_internal_steps_produce_no_customer_message(self):
        self.assertIsNone(mod.customer_message(BY_OP["op-4471-hold"]))

    def test_every_outcome_has_clean_customer_wording(self):
        base = dict(BY_OP["op-7713-refund"])
        for outcome in OUTCOMES:
            item = {**base, "outcome": outcome,
                    "evidence": "payments receipt rf-0009"}
            msg = mod.customer_message(item)
            self.assertTrue(msg["next"], outcome)
            self.assertEqual(mod.lint(msg, item, "customer"), [],
                             outcome)
            self.assertNotRegex(words(msg), r"rf-|op-|_")


class Lint(unittest.TestCase):
    def test_each_bad_message_trips_its_rule(self):
        for case in BAD:
            item = {**BY_OP[case["op"]], **case.get("override", {})}
            got = rules(mod.lint(case["message"], item,
                                 case["audience"]))
            self.assertIn(case["expect"], got, case["name"])

    def test_failed_may_say_failed(self):
        item = BY_OP["op-7713-email"]
        msg = {"happened": "Failed: the mailer rejected it.",
               "evidence": "mailer rejection",
               "next": "Fix the address, then send again.",
               "actions": []}
        self.assertEqual(mod.lint(msg, item, "operator"), [])

    def test_reverse_offered_on_unknown_is_not_allowed(self):
        item = BY_OP["op-4472-hold"]
        msg = mod.operator_message(item)
        msg["actions"] = [{"label": "Reverse", "enabled": True,
                           "reason": None}]
        self.assertIn("action-not-allowed",
                      rules(mod.lint(msg, item, "operator")))


if __name__ == "__main__":
    unittest.main()
