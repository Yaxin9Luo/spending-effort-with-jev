"""Split an amount between several parties without losing or inventing cents."""
from fractions import Fraction

from .money import from_cents, to_cents, to_decimal


def split_by_weights(total, weights):
    """Split `total` into shares proportional to `weights`, to the cent.

    total   -- an amount in dollars (anything to_cents accepts); may be
               negative, e.g. for refunds
    weights -- non-empty sequence of non-negative numbers (int, float or
               Decimal), not all zero. Floats are taken at their shortest repr,
               so [0.1, 0.2] splits exactly like [1, 2].

    Uses the largest-remainder method: each party first gets its exact share
    rounded toward zero to the cent, then the leftover cents are handed out one
    at a time to the parties with the largest discarded fractions (ties go to
    the earlier party). A negative total is split exactly like its absolute
    value, with every share negated. The shares always add up to the total.

    Returns a list of Decimals, one per weight.
    """
    weights = [Fraction(to_decimal(w)) for w in weights]
    if not weights:
        raise ValueError("need at least one weight")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    wsum = sum(weights)
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    cents = to_cents(total)
    sign = -1 if cents < 0 else 1
    cents = abs(cents)
    exact = [cents * w / wsum for w in weights]
    shares = [x.numerator // x.denominator for x in exact]
    leftover = cents - sum(shares)
    # hand out the leftover cents, largest discarded fraction first, ties to the earlier party
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - shares[i]), i))
    for i in order[:leftover]:
        shares[i] += 1
    return [from_cents(sign * s) for s in shares]


def split_evenly(total, n):
    """Split `total` into `n` equal-as-possible shares (see split_by_weights)."""
    if not isinstance(n, int) or n <= 0:
        raise ValueError("n must be a positive integer")
    return split_by_weights(total, [1] * n)
