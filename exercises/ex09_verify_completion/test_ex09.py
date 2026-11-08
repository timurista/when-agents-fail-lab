"""Checks for exercise 9. Run: python3 -m lab check 09"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lab import target
from lab.agent import call
from lab.clock import FakeClock
from lab.runlog import RunLog
from lab.tools import Fault, Payments, Storefront

EX = "ex09_verify_completion"
mod = target.load(EX)
FIXTURES = target.fixture(EX, "claims.json").parent


class Run1107(unittest.TestCase):
    def setUp(self):
        doc, ev = mod.load(FIXTURES)
        self.doc = doc
        self.found = {f.id: f for f in mod.verify(doc, ev)}

    def test_each_claim_gets_the_right_label(self):
        L = mod.Label
        self.assertEqual({k: f.label for k, f in self.found.items()}, {
            "c1": L.CONTRADICTED,   # 11 receipts, one rejection
            "c2": L.VERIFIED,       # refund receipt, right amount
            "c3": L.UNSUPPORTED,    # sent, timed out, no lookup
            "c4": L.VERIFIED,       # run-1107, drafts.json unchanged
            "c5": L.VERIFIED,       # one row per SKU the run touched
            "c6": L.UNSUPPORTED,    # nothing checks this
        })

    def test_notes_name_the_evidence(self):
        self.assertIn("SKU-3390", self.found["c1"].note)
        self.assertIn("rf-0013", self.found["c2"].note)

    def test_findings_keep_the_agents_order(self):
        self.assertEqual([f.id for f in mod.verify(*mod.load(FIXTURES))],
                         [c["id"] for c in self.doc["claims"]])

    def test_report(self):
        lines = mod.report("run-1107", list(self.found.values()))
        self.assertIn("3 verified", lines[0])
        self.assertIn("1 contradicted", lines[0])
        self.assertIn("2 unsupported", lines[0])
        self.assertTrue(lines[-1].startswith("Not done"))
        for line in lines:
            self.assertLessEqual(len(line), 72, line)


class Rules(unittest.TestCase):
    """Small runs built in a temporary folder."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def run_claims(self, claims, log=None, files=None):
        doc = {"run": "run-9", "log": "run.jsonl", "claims": claims}
        (self.dir / "claims.json").write_text(json.dumps(doc))
        if log is not None:
            log.save(self.dir / "run.jsonl")
        for name, body in (files or {}).items():
            (self.dir / name).write_text(body)
        return mod.verify(*mod.load(self.dir))

    def one(self, claim, **kw):
        claim = dict({"id": "x", "text": "t"}, **claim)
        return self.run_claims([claim], **kw)[0].label

    def refund_log(self, *faults, amount=4800, times=1, key=None):
        log, pay = RunLog(FakeClock()), Payments(faults=list(faults))
        args = {"key": key} if key else {}
        for i in range(times):
            call(log, pay, f"op-{i}", "refund", order="ORD-1",
                 amount=amount, **args)
        self.paid = pay.refunds
        return log

    REFUND = {"kind": "refund_issued", "order": "ORD-1", "amount": 4800}

    def test_refund_with_receipt_is_verified(self):
        self.assertEqual(self.one(self.REFUND, log=self.refund_log()),
                         mod.Label.VERIFIED)

    def test_wrong_amount_is_contradicted(self):
        log = self.refund_log(amount=5200)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.CONTRADICTED)

    def test_two_refunds_paid_is_contradicted(self):
        log = self.refund_log(times=2)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.CONTRADICTED)

    def test_a_safe_retry_is_one_refund_not_two(self):
        # Regression: two attempts with one idempotency key both
        # return a receipt, but the provider paid once. Count refund
        # ids, not attempts.
        log = self.refund_log(times=2, key="rf-ORD-1")
        self.assertEqual(len(self.paid), 1)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.VERIFIED)

    def test_an_unresolved_second_attempt_keeps_the_total_open(self):
        # Regression: the first attempt's reply is lost but the
        # provider paid; a second attempt with no key is paid and
        # confirmed. One receipt for $48, $96 out. Until the first
        # attempt is reconciled, the total is unsupported.
        log, pay = RunLog(FakeClock()), Payments(
            faults=[Fault.LOST_REPLY])
        call(log, pay, "op-0", "refund", order="ORD-1", amount=4800)
        call(log, pay, "op-1", "refund", order="ORD-1", amount=4800)
        self.assertEqual(sum(r["amount"] for r in pay.refunds), 9600)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.UNSUPPORTED)

    def test_lost_reply_is_unsupported_not_contradicted(self):
        log = self.refund_log(Fault.LOST_REPLY)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.UNSUPPORTED)

    def test_rejected_refund_is_contradicted(self):
        log = self.refund_log(Fault.REJECT)
        self.assertEqual(self.one(self.REFUND, log=log),
                         mod.Label.CONTRADICTED)

    def test_no_run_log_is_unsupported(self):
        self.assertEqual(self.one(self.REFUND), mod.Label.UNSUPPORTED)

    TESTS = {"kind": "tests_pass", "path": "out.txt", "count": 5}

    def out(self, run="run-9", passed=5, failed=0, code=0,
            manifest=True):
        drafts = "SKU-1: new copy\n"
        sha = hashlib.sha256(drafts.encode()).hexdigest()[:16]
        line = f"file: d.txt {sha}\n" if manifest else ""
        return {"d.txt": drafts,
                "out.txt": f"run: {run}\n{line}passed: {passed}\n"
                           f"failed: {failed}\nexit: {code}\n"}

    def test_green_output_from_this_run_is_verified(self):
        self.assertEqual(self.one(self.TESTS, files=self.out()),
                         mod.Label.VERIFIED)

    def test_green_output_from_another_run_is_unsupported(self):
        files = self.out(run="run-8")
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.UNSUPPORTED)

    def test_same_run_but_edited_after_the_tests_is_unsupported(self):
        # The run id matches and every check passed, but d.txt was
        # edited after the tests ran: they tested other content.
        files = self.out()
        files["d.txt"] = "SKU-1: edited after the tests\n"
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.UNSUPPORTED)

    def test_a_tested_file_that_is_gone_is_unsupported(self):
        files = self.out()
        del files["d.txt"]
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.UNSUPPORTED)

    def test_output_with_no_manifest_is_unsupported(self):
        files = self.out(manifest=False)
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.UNSUPPORTED)

    def test_a_failure_is_contradicted(self):
        files = self.out(passed=4, failed=1, code=1)
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.CONTRADICTED)

    def test_fewer_tests_than_claimed_is_contradicted(self):
        files = self.out(passed=3)
        self.assertEqual(self.one(self.TESTS, files=files),
                         mod.Label.CONTRADICTED)

    def test_missing_output_is_unsupported(self):
        self.assertEqual(self.one(self.TESTS), mod.Label.UNSUPPORTED)

    FILE = {"kind": "file_written", "path": "r.csv", "rows": 2}

    def test_file_with_the_claimed_rows_is_verified(self):
        files = {"r.csv": "sku,status\nA,updated\nB,updated\n"}
        self.assertEqual(self.one(self.FILE, files=files),
                         mod.Label.VERIFIED)

    def test_missing_file_is_contradicted(self):
        self.assertEqual(self.one(self.FILE), mod.Label.CONTRADICTED)

    def test_wrong_row_count_is_contradicted(self):
        files = {"r.csv": "sku,status\nA,updated\n"}
        self.assertEqual(self.one(self.FILE, files=files),
                         mod.Label.CONTRADICTED)

    PER_SKU = dict(FILE, one_row_per={"action": "set_description",
                                      "arg": "sku"})

    def sku_log(self, *skus):
        log, shop = RunLog(FakeClock()), Storefront()
        for sku in skus:
            call(log, shop, f"op-{sku}", "set_description", sku=sku,
                 text="new")
        return log

    def per_sku(self, body, log=True):
        log = self.sku_log("A", "B") if log else None
        return self.one(self.PER_SKU, log=log, files={"r.csv": body})

    def test_one_row_per_sku_in_the_run_is_verified(self):
        self.assertEqual(self.per_sku("sku,status\nB,ok\nA,ok\n"),
                         mod.Label.VERIFIED)

    def test_right_count_with_a_repeated_sku_is_contradicted(self):
        self.assertEqual(self.per_sku("sku,status\nA,ok\nA,ok\n"),
                         mod.Label.CONTRADICTED)

    def test_right_count_with_a_sku_not_in_the_run_is_contradicted(self):
        self.assertEqual(self.per_sku("sku,status\nA,ok\nZ,ok\n"),
                         mod.Label.CONTRADICTED)

    def test_one_row_per_sku_without_a_run_log_is_unsupported(self):
        self.assertEqual(self.per_sku("sku,status\nA,ok\nB,ok\n",
                                      log=False),
                         mod.Label.UNSUPPORTED)

    def test_unknown_kind_is_never_verified(self):
        self.assertEqual(self.one({"kind": "vibes_good"}),
                         mod.Label.UNSUPPORTED)

    def test_all_verified_reports_done(self):
        found = self.run_claims(
            [dict(self.REFUND, id="a", text="refund")],
            log=self.refund_log())
        self.assertEqual(mod.report("run-9", found)[-1], "Done.")


if __name__ == "__main__":
    unittest.main()
