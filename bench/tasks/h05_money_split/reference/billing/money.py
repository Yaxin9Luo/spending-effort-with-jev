"""Conversions between user-facing amounts and integer cents."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def to_decimal(value):
    """Convert an int, float, str or Decimal to Decimal.

    Floats are taken at their shortest repr (0.1 -> Decimal('0.1')), never at
    their exact binary value.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, (int, str)):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError(f"not a number: {value!r}") from None
    raise TypeError(f"unsupported amount type: {type(value).__name__}")


def to_cents(amount):
    """Convert an amount in dollars to integer cents.

    Accepts int, float, str or Decimal (floats are taken at their shortest
    repr, like to_decimal). Anything finer than a cent is rounded to the
    nearest cent, halves away from zero: 1.005 -> 101, -1.005 -> -101.
    """
    return int((to_decimal(amount) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_cents(cents):
    """Integer cents -> Decimal dollars with exactly two places."""
    return (Decimal(int(cents)) / 100).quantize(CENT)


def format_money(cents):
    """Format integer cents for display: 123456 -> '$1,234.56', -5 -> '-$0.05'."""
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(int(cents)), 100)
    return f"{sign}${dollars:,}.{rest:02d}"


def parse_money(text):
    """Parse '$1,234.56', '-$0.05' or accounting-style '(3.50)' into integer cents."""
    s = text.strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1].strip()
    if s.startswith("-"):
        negative, s = not negative, s[1:].strip()
    s = s.replace("$", "").replace(",", "").strip()
    cents = to_cents(s)
    return -cents if negative else cents
