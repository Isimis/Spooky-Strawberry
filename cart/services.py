from decimal import Decimal

from catalog.models import Product, ProductVariant

CART_SESSION_KEY = "cart"


def get_cart_data(request):
    return request.session.setdefault(CART_SESSION_KEY, {})


def save_cart_for_user(request):
    """Zapisuje koszyk z sesji do trwałego koszyka użytkownika (jeśli zalogowany)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return
    from .models import SavedCart

    cart = request.session.get(CART_SESSION_KEY, {})
    SavedCart.objects.update_or_create(user=user, defaults={"data": cart})


def restore_cart_for_user(request):
    """Po zalogowaniu łączy zapisany koszyk użytkownika z koszykiem z bieżącej sesji."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return
    from .models import SavedCart

    saved = SavedCart.objects.filter(user=user).first()
    if not saved or not saved.data:
        return
    cart = get_cart_data(request)
    for key, item in saved.data.items():
        quantity = int(item.get("quantity", 0)) if isinstance(item, dict) else 0
        if quantity <= 0:
            continue
        current = int(cart.get(key, {}).get("quantity", 0))
        cart[key] = {"quantity": max(current, quantity)}
    request.session.modified = True


def get_cart_quantity(request):
    cart = request.session.get(CART_SESSION_KEY, {})
    return sum(int(item.get("quantity", 0)) for item in cart.values())


def add_to_cart(request, variant, quantity=1):
    cart = get_cart_data(request)
    quantity = clean_quantity(quantity, default=1)
    key = str(variant.pk)

    if not is_variant_buyable(variant):
        return {
            "added": False,
            "quantity": 0,
            "requested": quantity,
            "available": max(variant.stock_quantity, 0),
            "reason": "unavailable",
        }

    current_quantity = int(cart.get(key, {}).get("quantity", 0))
    requested_quantity = current_quantity + quantity
    new_quantity = min(requested_quantity, variant.stock_quantity)
    cart[key] = {"quantity": new_quantity}
    request.session.modified = True
    return {
        "added": new_quantity > current_quantity,
        "quantity": new_quantity,
        "requested": requested_quantity,
        "available": variant.stock_quantity,
        "limited": new_quantity < requested_quantity,
        "reason": "ok",
    }


def update_cart_item(request, variant, quantity):
    cart = get_cart_data(request)
    quantity = clean_quantity(quantity, default=1)
    key = str(variant.pk)

    if quantity <= 0:
        cart.pop(key, None)
        request.session.modified = True
        return {"removed": True, "quantity": 0, "reason": "removed"}

    if not is_variant_buyable(variant):
        cart.pop(key, None)
        request.session.modified = True
        return {"removed": True, "quantity": 0, "reason": "unavailable"}

    new_quantity = min(quantity, variant.stock_quantity)
    cart[key] = {"quantity": new_quantity}
    request.session.modified = True
    return {
        "removed": False,
        "quantity": new_quantity,
        "requested": quantity,
        "available": variant.stock_quantity,
        "limited": new_quantity < quantity,
        "reason": "ok",
    }


def remove_cart_item(request, variant_id):
    cart = get_cart_data(request)
    cart.pop(str(variant_id), None)
    request.session.modified = True


def clear_cart(request):
    request.session[CART_SESSION_KEY] = {}
    request.session.modified = True


def get_cart_items(request):
    cart = request.session.get(CART_SESSION_KEY, {})
    variant_ids = [int(variant_id) for variant_id in cart.keys() if variant_id.isdigit()]
    variants = (
        ProductVariant.objects.filter(pk__in=variant_ids)
        .select_related("product", "color", "size")
        .prefetch_related("product__images")
    )
    variants_by_id = {variant.pk: variant for variant in variants}

    items = []
    adjustments = []
    changed = False
    for variant_id in variant_ids:
        key = str(variant_id)
        variant = variants_by_id.get(variant_id)
        if variant is None or not is_variant_buyable(variant):
            cart.pop(key, None)
            changed = True
            adjustments.append("Usunięto z koszyka produkt, który nie jest już dostępny.")
            continue

        quantity = clean_quantity(cart[key].get("quantity", 0), default=0)
        if quantity <= 0:
            cart.pop(key, None)
            changed = True
            continue
        if quantity > variant.stock_quantity:
            quantity = variant.stock_quantity
            cart[key] = {"quantity": quantity}
            changed = True
            adjustments.append(f"Zmniejszono ilość: {variant.product.name}, bo w magazynie jest {quantity} szt.")

        unit_price = variant.price
        line_total = unit_price * quantity
        items.append(
            {
                "variant": variant,
                "product": variant.product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "image": variant.product.main_image,
                "stock_quantity": variant.stock_quantity,
            }
        )

    if changed:
        request.session.modified = True

    return items, adjustments


def get_cart_summary(request):
    items, adjustments = get_cart_items(request)
    subtotal = sum((item["line_total"] for item in items), Decimal("0.00"))
    quantity = sum(item["quantity"] for item in items)
    return {
        "items": items,
        "subtotal": subtotal,
        "quantity": quantity,
        "adjustments": adjustments,
    }


def is_variant_buyable(variant):
    return (
        variant.is_active
        and variant.stock_quantity > 0
        and variant.product.status == Product.STATUS_ACTIVE
    )


def clean_quantity(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
