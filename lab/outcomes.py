"""The outcome vocabulary every exercise shares."""
from enum import Enum


# region: outcome
class Outcome(str, Enum):
    # The other system said it happened, and gave evidence.
    CONFIRMED = "confirmed"
    # The other system said it did not happen.
    FAILED = "failed"
    # Nobody has said either. Elapsed time is not an answer.
    UNKNOWN = "unknown"
    # The other system acknowledged a cancel before applying.
    CANCELED = "canceled"
    # The request never left this process.
    NEVER_SENT = "never_sent"
# endregion


# region: settled
SETTLED = {Outcome.CONFIRMED, Outcome.FAILED,
           Outcome.CANCELED, Outcome.NEVER_SENT}


def is_settled(outcome: Outcome) -> bool:
    """True when acting on this outcome cannot double an effect."""
    return outcome in SETTLED
# endregion
