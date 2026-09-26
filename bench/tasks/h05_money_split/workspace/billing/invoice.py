"""Invoices: lines, discount, tax, and splitting the total between payers."""
from dataclasses import dataclass

from .money import format_money, from_cents, to_cents, to_decimal
from .split import split_by_weights


@dataclass(frozen=True)
class Line:
    description: str
    qty: object
    unit_price: object
    cents: int


class Invoice:
    """An invoice with a percentage discount and a percentage tax.

    Each line total (qty * unit_price) is rounded to the cent, halves away
    from zero. The discount is discount_pct percent of the subtotal and the
    tax is tax_pct percent of (subtotal - discount); each is rounded to the
    cent the same way. Quantities and prices may be negative (credits).
    """

    def __init__(self, discount_pct=0, tax_pct=0):
        self.discount_pct = to_decimal(discount_pct)
        self.tax_pct = to_decimal(tax_pct)
        self._lines = []

    def add_line(self, description, qty, unit_price):
        cents = to_cents(to_decimal(qty) * to_decimal(unit_price))
        self._lines.append(Line(description, qty, unit_price, cents))
        return self

    @property
    def lines(self):
        return list(self._lines)

    def subtotal_cents(self):
        return sum(line.cents for line in self._lines)

    def discount_cents(self):
        return to_cents(from_cents(self.subtotal_cents()) * self.discount_pct / 100)

    def tax_cents(self):
        taxable = self.subtotal_cents() - self.discount_cents()
        return to_cents(from_cents(taxable) * self.tax_pct / 100)

    def total_cents(self):
        return self.subtotal_cents() - self.discount_cents() + self.tax_cents()

    def split(self, weights):
        """Split the invoice total between payers (see split.split_by_weights)."""
        return split_by_weights(from_cents(self.total_cents()), weights)

    def render(self):
        rows = [f"{l.description:<24}{format_money(l.cents):>14}" for l in self._lines]
        rows.append(f"{'Subtotal':<24}{format_money(self.subtotal_cents()):>14}")
        if self.discount_pct:
            rows.append(f"{'Discount':<24}{format_money(-self.discount_cents()):>14}")
        if self.tax_pct:
            rows.append(f"{'Tax':<24}{format_money(self.tax_cents()):>14}")
        rows.append(f"{'Total':<24}{format_money(self.total_cents()):>14}")
        return "\n".join(rows)
