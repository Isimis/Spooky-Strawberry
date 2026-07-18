"""Orkiestracja płatności: start, obsługa webhooka, uzgadnianie statusu.

Webhook (``handle_notification``) jest źródłem prawdy. Cała finalizacja
(opłacenie → zejście ze stanu magazynowego → mail) jest **idempotentna**:
powtórny webhook dla już opłaconej płatności niczego nie zmienia.
"""

import uuid

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from inventory.models import StockEntry
from inventory.services import ensure_opening_balance, recalculate_variant_stock
from orders.models import Order

from . import przelewy24
from .models import Payment


def start_payment(request, order, *, method=""):
    """Tworzy Payment i rejestruje transakcję w P24. Zwraca URL bramki."""
    payment = Payment.objects.create(
        order=order,
        provider=Payment.PROVIDER_P24,
        session_id=uuid.uuid4().hex,
        amount=order.grand_total,
        currency="PLN",
        status=Payment.STATUS_PENDING,
        method=method,
    )

    url_return = request.build_absolute_uri(reverse("checkout:payment_return"))
    url_status = request.build_absolute_uri(reverse("payments:p24_webhook"))

    token, raw = przelewy24.register(
        session_id=payment.session_id,
        amount_grosze=payment.amount_grosze,
        email=order.email,
        description=f"Zamówienie {order.order_number}",
        url_return=url_return,
        url_status=url_status,
    )
    payment.p24_token = token
    payment.raw_register = raw if isinstance(raw, dict) else {}
    payment.save(update_fields=["p24_token", "raw_register", "updated_at"])
    return przelewy24.gateway_url(token)


def handle_notification(data):
    """Obsługuje webhook P24. Zwraca True, gdy płatność została potwierdzona."""
    if not przelewy24.verify_notification_sign(data):
        return False

    session_id = data.get("sessionId")
    payment = Payment.objects.filter(session_id=session_id).select_related("order").first()
    if payment is None:
        return False

    # Kwota z webhooka musi zgadzać się z naszą (ochrona przed manipulacją).
    if int(data.get("amount", -1)) != payment.amount_grosze:
        return False

    order_id = data.get("orderId")
    ok, verify_raw = przelewy24.verify(
        session_id=session_id,
        amount_grosze=payment.amount_grosze,
        order_id=order_id,
    )
    if not ok:
        return False

    _finalize_paid(payment.pk, p24_order_id=str(order_id), notification=data, verify_raw=verify_raw)
    return True


def reconcile_payment(payment):
    """Dopina weryfikację na stronie powrotu, gdy webhook się spóźnia lub nie dotarł.

    Jeśli nie znamy jeszcze ``p24_order_id`` (webhook nie przyszedł), pytamy P24 o status
    po naszym ``sessionId`` — dzięki temu strona powrotu jest samowystarczalna.
    """
    if payment.is_paid:
        return payment

    order_id = payment.p24_order_id
    if not order_id:
        try:
            info = przelewy24.by_session_id(payment.session_id)
        except przelewy24.Przelewy24Error:
            info = None
        order_id = str(info.get("orderId")) if info and info.get("orderId") else ""
        if order_id:
            payment.p24_order_id = order_id
            payment.save(update_fields=["p24_order_id", "updated_at"])

    if not order_id:
        return payment

    try:
        ok, verify_raw = przelewy24.verify(
            session_id=payment.session_id,
            amount_grosze=payment.amount_grosze,
            order_id=order_id,
        )
    except przelewy24.Przelewy24Error:
        return payment

    if ok:
        _finalize_paid(payment.pk, p24_order_id=order_id, verify_raw=verify_raw)
        payment.refresh_from_db()
    return payment


@transaction.atomic
def _finalize_paid(payment_pk, *, p24_order_id="", notification=None, verify_raw=None):
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_pk)
    if payment.is_paid:
        return payment  # idempotencja — drugi webhook nic nie robi

    now = timezone.now()
    payment.status = Payment.STATUS_PAID
    payment.paid_at = now
    if p24_order_id:
        payment.p24_order_id = p24_order_id
    if notification:
        payment.raw_notification = notification
    payment.save()

    order = payment.order
    # Spóźniona płatność „odzyskuje" zamówienie, nawet jeśli zdążyło wygasnąć (CANCELLED)
    # albo było szkicem — nie może być tak, że pieniądze wpłynęły, a zamówienie przepadło.
    if order.status in {Order.STATUS_AWAITING_PAYMENT, Order.STATUS_CANCELLED, Order.STATUS_DRAFT}:
        order.status = Order.STATUS_PLACED
    if not order.placed_at:
        order.placed_at = now
    order.save(update_fields=["status", "placed_at", "updated_at"])

    # W trybie Sandbox (testowym) nie ruszamy stanów magazynowych.
    from core.models import SiteSettings

    if not SiteSettings.load().payments_sandbox:
        _create_sale_stock_entries(order)
    _send_confirmation_email(order, payment)
    return payment


def _create_sale_stock_entries(order):
    """Tworzy ruchy magazynowe 'sprzedaż' (OUT) i przelicza stany wariantów."""
    items = order.items.select_related("variant").all()
    for item in items:
        if not item.variant_id:
            continue
        already = StockEntry.objects.filter(order_item=item, source=StockEntry.SOURCE_SALE).exists()
        if already:
            continue
        ensure_opening_balance(item.variant)
        StockEntry.objects.create(
            variant=item.variant,
            direction=StockEntry.DIRECTION_OUT,
            source=StockEntry.SOURCE_SALE,
            quantity=item.quantity,
            order_item=item,
            note=f"Sprzedaż – {order.order_number}",
        )
        recalculate_variant_stock(item.variant)


def _order_status_url(order):
    """Bezwzględny link do statusu zamówienia (otwiera je od razu, po sekretnym tokenie)."""
    from urllib.parse import urlencode

    from django.conf import settings
    from django.urls import reverse

    query = urlencode({"number": order.order_number or "", "token": order.confirmation_token})
    path = f"{reverse('core:order_status')}?{query}"
    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    return f"{base}{path}" if base else path


def _send_confirmation_email(order, payment):
    from core.mailer import send_message

    lines = "".join(
        f"<li>{item.product_name}"
        + (f" ({item.variant_name})" if item.variant_name else "")
        + f" × {item.quantity} — {item.line_total} zł</li>"
        for item in order.items.all()
    )
    if order.pickup_point_code:
        delivery = f"Odbiór w paczkomacie {order.pickup_point_name or order.pickup_point_code}"
        if order.pickup_point_address:
            delivery += f" ({order.pickup_point_address})"
    else:
        delivery = (
            f"{order.shipping_address_line_1}, {order.shipping_postal_code} {order.shipping_city}"
        )
    status_url = _order_status_url(order)
    body_html = (
        f"<p>Cześć {order.first_name},</p>"
        f"<p>dziękujemy! Twoja płatność za zamówienie <strong>{order.order_number}</strong> "
        f"została zaksięgowana.</p>"
        f"<ul>{lines}</ul>"
        f"<p>Do zapłaty: <strong>{order.grand_total} zł</strong> (opłacone).</p>"
        f"<p>Dostawa: {delivery}</p>"
        f'<p style="margin:24px 0">'
        f'<a href="{status_url}" '
        f'style="display:inline-block;background:#c2185b;color:#fff;text-decoration:none;'
        f'padding:12px 22px;border-radius:999px;font-weight:600">Sprawdź status zamówienia →</a>'
        f"</p>"
        f'<p style="font-size:12px;color:#777">Gdyby przycisk nie działał, skopiuj ten link do przeglądarki:<br>'
        f'<a href="{status_url}" style="color:#c2185b">{status_url}</a></p>'
    )
    try:
        send_message(
            subject=f"Potwierdzenie płatności – {order.order_number}",
            body_html=body_html,
            to_email=order.email,
            fail_silently=True,
        )
    except Exception:
        # Mail nie może wywrócić finalizacji płatności.
        pass
