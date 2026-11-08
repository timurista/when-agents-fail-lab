"""Checks for exercise 6. Run: python3 -m lab check 06

Every interleaving here is a script. A "pause" is a hook the worker
calls at a named point; the test uses it to move the clock and let the
other worker act. There are no threads and no sleeps.
"""
import unittest

from lab import target
from lab.clock import FakeClock
from lab.leases import FencedStore, LeaseService
from lab.runlog import RunLog
from lab.tools import Fault, Mailer

EX = "ex06_fencing"
mod = target.load(EX)

TTL = 30.0
OLD = "Waxed canvas tote. Lead with durability."
NEW = "Waxed canvas tote. Lead with the recycled lining."


# region: ex06_at
def at(point, action):
    """A pause hook that runs `action` once, at the named point."""
    def pause(where):
        if where == point:
            action()
    return pause
# endregion


class Setup(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.leases = LeaseService(self.clock, ttl=TTL)
        self.a = self.leases.acquire("job-4471", "worker-a")


class PausedWorker(Setup):
    """Worker A pauses past its lease; worker B takes over and writes."""

    def takeover(self, write):
        def action():
            self.clock.advance(TTL + 10)
            self.b = self.leases.acquire("job-4471", "worker-b")
            self.assertIsNotNone(self.b)
            self.assertEqual(write(self.b, NEW), "written")
        return action

    def test_control_the_naive_worker_overwrites(self):
        catalog = {}
        write_b = lambda lease, text: mod.naive_update(
            self.leases, catalog, lease, "SKU-4471", text)
        result = mod.naive_update(
            self.leases, catalog, self.a, "SKU-4471", OLD,
            pause=at("before_write", self.takeover(write_b)))
        # The race is real: A's stale text is what customers see.
        self.assertEqual(result, "written")
        self.assertEqual(catalog["SKU-4471"], OLD)

    # region: ex06_scripted
    def test_the_store_refuses_the_older_token(self):
        store = FencedStore()
        write_b = lambda lease, text: mod.fenced_update(
            store, lease, "SKU-4471", text)
        result = mod.fenced_update(
            store, self.a, "SKU-4471", OLD,
            pause=at("before_write", self.takeover(write_b)))
        self.assertEqual(result, "fenced")
        self.assertEqual(store.read("SKU-4471"), NEW)
        self.assertEqual(store.rejected[0]["token"], self.a.token)
    # endregion

    def test_tokens_only_go_up(self):
        store = FencedStore()
        mod.fenced_update(
            store, self.a, "SKU-4471", OLD,
            pause=at("before_write", self.takeover(
                lambda lease, text: mod.fenced_update(
                    store, lease, "SKU-4471", text))))
        self.assertGreater(self.b.token, self.a.token)


class NoPause(Setup):
    def test_a_live_lease_writes(self):
        store = FencedStore()
        self.assertEqual(
            mod.fenced_update(store, self.a, "SKU-4471", OLD),
            "written")
        self.assertEqual(store.highest["SKU-4471"], self.a.token)

    def test_the_same_token_may_write_twice(self):
        store = FencedStore()
        mod.fenced_update(store, self.a, "SKU-4471", OLD)
        self.assertEqual(
            mod.fenced_update(store, self.a, "SKU-4471", NEW),
            "written")


class Unfenceable(Setup):
    """The mailer can't check a token. Narrow the window and log it."""

    def setUp(self):
        super().setUp()
        self.log = RunLog(self.clock)
        self.claims = FencedStore()

    def send(self, lease, mailer, pause=None):
        kw = {"pause": pause} if pause else {}
        return mod.send_once(self.log, self.leases, self.claims, lease,
                             mailer, "op-mail-4471", "pat@example.test",
                             "Back in stock", **kw)

    def test_a_live_lease_sends_and_records_its_token(self):
        mailer = Mailer()
        self.assertEqual(self.send(self.a, mailer), "sent")
        self.assertEqual(len(mailer.outbox), 1)
        claim = [e for e in self.log.events if e["kind"] == "claim"]
        self.assertEqual(claim[0]["token"], self.a.token)
        kinds = [e["kind"] for e in self.log.events]
        self.assertLess(kinds.index("claim"), kinds.index("sent"))

    def test_a_lapsed_lease_does_not_send(self):
        mailer = Mailer()
        self.clock.advance(TTL + 1)
        self.assertEqual(self.send(self.a, mailer), "lost_lease")
        self.assertEqual(mailer.outbox, [])
        self.assertIn("fenced", [e["kind"] for e in self.log.events])

    def test_successor_does_not_resend_an_unknown(self):
        mailer = Mailer(faults=[Fault.LOST_REPLY])
        self.assertEqual(self.send(self.a, mailer), "no_receipt")
        self.clock.advance(TTL + 1)
        b = self.leases.acquire("job-4471", "worker-b")
        self.assertEqual(self.send(b, mailer), "escalate")
        self.assertEqual(len(mailer.outbox), 1)

    def test_pause_before_the_claim_is_fenced(self):
        mailer = Mailer()

        def takeover():
            self.clock.advance(TTL + 10)
            b = self.leases.acquire("job-4471", "worker-b")
            self.assertEqual(self.send(b, mailer), "sent")
        result = self.send(self.a, mailer,
                           pause=at("after_check", takeover))
        self.assertEqual(result, "lost_lease")
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mod.late_sends(self.log), [])

    def test_pause_after_the_claim_is_the_residual_window(self):
        mailer = Mailer()
        outcomes = []

        def takeover():
            self.clock.advance(TTL + 10)
            b = self.leases.acquire("job-4471", "worker-b")
            outcomes.append(self.send(b, mailer))
        result = self.send(self.a, mailer,
                           pause=at("before_send", takeover))
        # B saw A's claim and stood down, so there is one email.
        self.assertEqual(outcomes, ["escalate"])
        self.assertEqual(result, "sent")
        self.assertEqual(len(mailer.outbox), 1)
        # But A sent it after its lease ended, and the log can show it.
        self.assertEqual(mod.late_sends(self.log), ["op-mail-4471"])

    def test_no_late_sends_in_a_clean_run(self):
        self.send(self.a, Mailer())
        self.assertEqual(mod.late_sends(self.log), [])


if __name__ == "__main__":
    unittest.main()
