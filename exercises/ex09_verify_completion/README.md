# Exercise 9: It said it finished

Chapter 9. Synthetic.

Fernhill Supply's operations agent finished run-1107 and wrote
`fixtures/handoff.md`: a tidy list of six things it did, ending with
"Nothing needs your attention." The same six claims are in
`fixtures/claims.json` in a form code can read. The rest of
`fixtures/` is what the run saved: its run log (`run.jsonl`), the
output of the description checks (`test-output.txt`), the drafts those
checks ran against (`drafts.json`) and the report it wrote
(`report.csv`).

Label every claim as one of:

- VERIFIED: saved evidence from this run agrees with every part.
- CONTRADICTED: saved evidence says something the claim does not.
- UNSUPPORTED: nothing saved can settle it either way.

`starter.py` gives you the loading code, an `effects` helper that reads
operations out of the run log, a `digest` helper that hashes a file, and
`check_email` as a worked example.
Write `check_descriptions`, `check_refund`, `check_tests`, `check_file`,
`verify` and `report`.

Rules the checks enforce:

1. Evidence comes from the saved artifacts, never from the handoff's
   own wording. The prose in handoff.md is not evidence.
2. A receipt confirms. An explicit rejection contradicts. A timeout,
   with no receipt, leaves a claim UNSUPPORTED.
3. Test output only counts if it names this run. Output from another
   run is UNSUPPORTED, however green it is.
4. Test output must also list the files it ran against, one
   `file: <path> <digest>` line each (the evidence manifest). No
   manifest, or a listed file whose digest is different now, is
   UNSUPPORTED: the tests ran against other content.
5. A claim with no check is UNSUPPORTED, never VERIFIED.
6. A refund claim is CONTRADICTED if more than one refund was paid for
   the order, or if the amount differs. Count distinct refund ids from
   the provider: two attempts under one idempotency key that return
   the same refund id are one refund.
   A receipt is not enough while another attempt for the order is
   unresolved and the confirmed attempt's key doesn't cover it: that
   attempt may also have paid, so the claim is UNSUPPORTED.
7. A file claim with `one_row_per` needs exactly one row for each key
   the run log names: no repeats, no extras, none missing. Without a
   run log to name them, it is UNSUPPORTED.
8. The handoff is done only when every claim is VERIFIED. Report lines
   fit in 72 columns.

Before you run the checks, label the six claims by hand from the
fixtures. Then:

    python3 -m lab check 09

When you have tried it once, `python3 -m lab reveal 09` shows the
reference answer.
