"""Leases that expire, fencing tokens, and a store that checks them.

A lease says "this worker may act on this resource until time T". It is
a promise from the lease service, and the worker can only ever learn
about it from a message that is already old when it arrives. A worker
that pauses (a long garbage collection, a suspended VM, a laptop lid)
can wake up after T and still believe it holds the lease.

The fix in this module is the standard one: every lease carries a
fencing token that only goes up, and the store that holds the effect
remembers the highest token it has seen per key and refuses anything
older. The worker's own belief about its lease is never consulted.

Time comes from the lab's FakeClock, so every interleaving in the tests
is a script, not a race. There are no threads anywhere in the lab.
"""
from dataclasses import dataclass, replace


class StaleToken(Exception):
    """The store has already seen a newer token for this key."""


# region: lease
@dataclass(frozen=True)
class Lease:
    resource: str   # what the lease covers, e.g. "job-4471"
    holder: str     # which worker holds it
    token: int      # fencing token; a later lease has a larger one
    expires: float  # clock time after which the lease is void


class LeaseService:
    def __init__(self, clock, ttl: float = 30.0):
        self.clock = clock
        self.ttl = ttl
        self._held = {}     # resource -> Lease
        self._last = 0      # last token issued, for any resource

    def acquire(self, resource: str, holder: str) -> Lease | None:
        """A new lease, or None while someone else's is still live."""
        now = self.clock.now()
        live = self._held.get(resource)
        if live is not None and live.expires > now:
            return None
        self._last += 1  # never reused, never goes down
        lease = Lease(resource, holder, self._last, now + self.ttl)
        self._held[resource] = lease
        return lease

    def is_current(self, lease: Lease) -> bool:
        """True at the moment of asking. Old as soon as it returns."""
        live = self._held.get(lease.resource)
        return (live is not None and live.token == lease.token
                and live.expires > self.clock.now())
# endregion

    def renew(self, lease: Lease) -> Lease | None:
        """Extend a lease that is still current; None if it lapsed."""
        if not self.is_current(lease):
            return None
        renewed = replace(lease, expires=self.clock.now() + self.ttl)
        self._held[lease.resource] = renewed
        return renewed

    def release(self, lease: Lease) -> None:
        if self.is_current(lease):
            del self._held[lease.resource]


# region: store
class FencedStore:
    """Key-value data that refuses writes carrying an older token."""

    def __init__(self):
        self.data = {}
        self.highest = {}    # key -> highest token accepted
        self.rejected = []   # every write refused, for the log

    def write(self, key: str, value, token: int) -> dict:
        seen = self.highest.get(key, 0)
        if token < seen:  # (1)
            self.rejected.append(
                {"key": key, "token": token, "seen": seen})
            raise StaleToken(f"{key}: token {token} < {seen}")
        self.highest[key] = token  # (2)
        self.data[key] = value
        return {"key": key, "token": token}

    def read(self, key: str):
        return self.data.get(key)
# endregion
