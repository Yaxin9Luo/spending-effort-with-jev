TAX_RATE = 0.08


def compute_order_total(items, discount=0.0):
    """Return the order total for (price, qty) pairs, after discount and tax."""
    subtotal = sum(price * qty for price, qty in items)
    subtotal -= subtotal * discount
    return round(subtotal * (1 + TAX_RATE), 2)
