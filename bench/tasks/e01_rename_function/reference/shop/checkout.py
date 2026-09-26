from shop.pricing import compute_order_total

COUPONS = {"SAVE10": 0.10, "SAVE25": 0.25}


def checkout(cart, coupon=None):
    discount = COUPONS.get(coupon, 0.0)
    total = compute_order_total(cart, discount=discount)
    return {"items": sum(qty for _, qty in cart), "total": total}
