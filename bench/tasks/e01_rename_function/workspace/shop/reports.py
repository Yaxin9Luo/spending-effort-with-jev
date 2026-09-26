from shop import pricing


def daily_summary(orders):
    """Summarise a day's orders (each a list of (price, qty) pairs)."""
    totals = [pricing.calc_total(order) for order in orders]
    return {
        "orders": len(orders),
        "revenue": round(sum(totals), 2),
        "largest": max(totals) if totals else 0.0,
    }
