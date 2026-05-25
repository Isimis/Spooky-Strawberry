from .services import get_cart_quantity


def cart(request):
    return {
        "cart_item_count": get_cart_quantity(request),
    }
