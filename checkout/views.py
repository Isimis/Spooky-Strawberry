from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from analytics.services import track_event
from cart.services import clear_cart, get_cart_summary
from cart.views import get_shipping_estimate
from orders.models import Order, OrderItem, ShippingMethod

from .forms import CheckoutForm

CHECKOUT_SESSION_KEY = "checkout"

PAYMENT_METHODS = [
    ("blik", "BLIK", "Szybko, kodem z aplikacji banku"),
    ("card", "Karta płatnicza", "Visa, Mastercard"),
    ("p24", "Przelewy24", "Przelew online z Twojego banku"),
    ("wallet", "Apple Pay / Google Pay", "Płatność jednym dotknięciem"),
]
PAYMENT_LABELS = {code: label for code, label, _ in PAYMENT_METHODS}


def _shipping_cost_for(method, subtotal):
    if method is None:
        cost, _, _ = get_shipping_estimate(subtotal)
        return cost
    free_from = method.free_from_amount
    if free_from is not None and subtotal >= free_from:
        return Decimal("0.00")
    return method.price


def shipping(request):
    summary = get_cart_summary(request)
    if not summary["items"]:
        messages.info(request, "Twój koszyk jest pusty.")
        return redirect("cart:detail")

    saved = request.session.get(CHECKOUT_SESSION_KEY, {})
    form = CheckoutForm(request.POST or None, initial=dict(saved))

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        request.session[CHECKOUT_SESSION_KEY] = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email": data["email"],
            "phone": data["phone"],
            "shipping_method": data["shipping_method"].id,
            "address_line_1": data["address_line_1"],
            "address_line_2": data["address_line_2"],
            "postal_code": data["postal_code"],
            "city": data["city"],
        }
        request.session.modified = True
        return redirect("checkout:payment")

    methods = list(ShippingMethod.objects.filter(is_active=True).order_by("sort_order", "price"))
    selected_method_id = saved.get("shipping_method") or (methods[0].id if methods else None)
    selected_method = next((m for m in methods if m.id == selected_method_id), methods[0] if methods else None)
    shipping_cost = _shipping_cost_for(selected_method, summary["subtotal"])

    return render(
        request,
        "checkout/shipping.html",
        {
            "form": form,
            "items": summary["items"],
            "subtotal": summary["subtotal"],
            "shipping_methods": methods,
            "selected_method_id": selected_method_id,
            "shipping_cost": shipping_cost,
            "grand_total": summary["subtotal"] + shipping_cost,
        },
    )


def payment(request):
    summary = get_cart_summary(request)
    if not summary["items"]:
        messages.info(request, "Twój koszyk jest pusty.")
        return redirect("cart:detail")

    checkout_data = request.session.get(CHECKOUT_SESSION_KEY)
    if not checkout_data:
        return redirect("checkout:shipping")

    method = ShippingMethod.objects.filter(id=checkout_data.get("shipping_method")).first()
    shipping_cost = _shipping_cost_for(method, summary["subtotal"])

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "blik")
        order = create_order(request, summary, checkout_data, method, shipping_cost, payment_method)
        clear_cart(request)
        request.session.pop(CHECKOUT_SESSION_KEY, None)
        request.session.modified = True
        track_event(request, "purchase", metadata={"order": order.order_number, "total": str(order.grand_total)})
        return redirect("checkout:confirmation", order_number=order.order_number)

    return render(
        request,
        "checkout/payment.html",
        {
            "items": summary["items"],
            "subtotal": summary["subtotal"],
            "shipping_method": method,
            "shipping_cost": shipping_cost,
            "grand_total": summary["subtotal"] + shipping_cost,
            "payment_methods": PAYMENT_METHODS,
        },
    )


@transaction.atomic
def create_order(request, summary, data, method, shipping_cost, payment_method):
    subtotal = summary["subtotal"]
    order = Order.objects.create(
        email=data["email"],
        phone=data.get("phone", ""),
        first_name=data["first_name"],
        last_name=data["last_name"],
        shipping_address_line_1=data["address_line_1"],
        shipping_address_line_2=data.get("address_line_2", ""),
        shipping_postal_code=data["postal_code"],
        shipping_city=data["city"],
        shipping_method=method,
        status=Order.STATUS_PLACED,
        subtotal=subtotal,
        discount_total=Decimal("0.00"),
        shipping_total=shipping_cost,
        grand_total=subtotal + shipping_cost,
        customer_note=f"Płatność: {PAYMENT_LABELS.get(payment_method, payment_method)}",
        source_session_key=request.session.session_key or "",
        placed_at=timezone.now(),
        user=request.user if request.user.is_authenticated else None,
    )
    order.order_number = f"SS-{10000 + order.pk}"
    order.save(update_fields=["order_number"])

    for item in summary["items"]:
        variant = item["variant"]
        variant_parts = [p.name for p in (variant.color, variant.size) if p]
        OrderItem.objects.create(
            order=order,
            product=item["product"],
            variant=variant,
            product_name=item["product"].name,
            variant_name=" / ".join(variant_parts),
            sku=variant.sku or "",
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
        )
    return order


def confirmation(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related("shipping_method").prefetch_related("items__product__images"),
        order_number=order_number,
    )
    return render(request, "checkout/confirmation.html", {"order": order})
