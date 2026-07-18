"""Orkiestracja płatności: start, obsługa webhooka, uzgadnianie statusu.

Webhook (``handle_notification``) jest źródłem prawdy. Cała finalizacja
(opłacenie → zejście ze stanu magazynowego → mail) jest **idempotentna**:
powtórny webhook dla już opłaconej płatności niczego nie zmienia.
"""

import uuid

from django.db import transaction
from django.db.models import F
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
    po naszym ``sessionId`` - dzięki temu strona powrotu jest samowystarczalna.
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
        return payment  # idempotencja - drugi webhook nic nie robi

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
    # albo było szkicem - nie może być tak, że pieniądze wpłynęły, a zamówienie przepadło.
    if order.status in {Order.STATUS_AWAITING_PAYMENT, Order.STATUS_CANCELLED, Order.STATUS_DRAFT}:
        order.status = Order.STATUS_PLACED
    if not order.placed_at:
        order.placed_at = now
    order.save(update_fields=["status", "placed_at", "updated_at"])

    # Licznik kodu zwiększamy dopiero po potwierdzonej płatności. Cała funkcja
    # jest idempotentna, więc powtórzony webhook nie naliczy użycia drugi raz.
    if order.discount_code_id and order.discount_total > 0:
        from orders.models import DiscountCode

        DiscountCode.objects.filter(pk=order.discount_code_id).update(used_count=F("used_count") + 1)

    # W trybie Sandbox (testowym) nie ruszamy stanów magazynowych.
    from core.models import SiteSettings

    if not SiteSettings.load().payments_sandbox:
        _create_sale_stock_entries(order)
    _send_order_emails(order)
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
            note=f"Sprzedaż - {order.order_number}",
        )
        recalculate_variant_stock(item.variant)


def _send_order_emails(order):
    """Po opłaceniu: potwierdzenie dla klienta + powiadomienie dla obsługi.
    Best-effort - żaden mail nie może wywrócić finalizacji płatności."""
    from core.emails import send_admin_order_notification, send_order_confirmation

    try:
        send_order_confirmation(order)
    except Exception:
        pass
    try:
        send_admin_order_notification(order)
    except Exception:
        pass
