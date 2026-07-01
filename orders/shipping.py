from decimal import Decimal


FREE_SHIPPING_THRESHOLD = Decimal("60.00")

SHIPPING_METHOD_DEFINITIONS = (
    {
        "code": "paczkomat",
        "name": "Paczkomat",
        "description": "Dostawa do paczkomatu InPost w 1-2 dni robocze.",
        "price": Decimal("10.99"),
        "sort_order": 10,
    },
    {
        "code": "kurier",
        "name": "Kurier",
        "description": "Dostawa kurierem pod wskazany adres w 1-2 dni robocze.",
        "price": Decimal("13.99"),
        "sort_order": 20,
    },
)

DEFAULT_SHIPPING_PRICE = SHIPPING_METHOD_DEFINITIONS[0]["price"]


def shipping_cost_for_method(method, subtotal):
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        return Decimal("0.00")
    if method is None:
        return DEFAULT_SHIPPING_PRICE
    return method.price


def get_shipping_estimate(subtotal):
    from .models import ShippingMethod

    method = ShippingMethod.objects.filter(is_active=True).order_by("price", "sort_order").first()
    cost = shipping_cost_for_method(method, subtotal)
    remaining = Decimal("0.00") if subtotal >= FREE_SHIPPING_THRESHOLD else FREE_SHIPPING_THRESHOLD - subtotal
    return cost, FREE_SHIPPING_THRESHOLD, remaining
