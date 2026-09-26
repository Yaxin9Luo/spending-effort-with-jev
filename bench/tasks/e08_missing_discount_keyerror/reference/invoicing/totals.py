def line_gross(line):
    return line["unit_price"] * line["quantity"]


def line_discount(line):
    """Fractional discount for a line; lines without one are not discounted."""
    return line.get("discount", 0.0)


def line_total(line):
    """Price of one invoice line after its fractional discount (0.1 = 10% off)."""
    return round(line_gross(line) * (1 - line_discount(line)), 2)


def invoice_total(invoice):
    return round(sum(line_total(line) for line in invoice["lines"]), 2)


def invoice_savings(invoice):
    """Total amount knocked off by discounts across the invoice."""
    return round(sum(line_gross(line) * line_discount(line) for line in invoice["lines"]), 2)
