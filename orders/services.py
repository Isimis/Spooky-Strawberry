"""Usługi domenowe zamówień."""

from datetime import timedelta

from django.utils import timezone

from .models import Order

# Po tylu minutach nieopłacone zamówienie „Oczekuje na płatność" uznajemy za porzucone.
# Wartość jest z zapasem - realna płatność (BLIK/karta) potwierdza się w minuty, a webhook
# i tak sfinalizuje ją niezależnie od przeglądarki klienta.
DEFAULT_PENDING_TTL_MINUTES = 120


def expire_stale_pending_orders(older_than_minutes=DEFAULT_PENDING_TTL_MINUTES, limit=200):
    """Anuluje porzucone, nieopłacone zamówienia (status „Oczekuje na płatność").

    Nie rezerwujemy stanu magazynowego, więc to wyłącznie higiena danych - takie zamówienia
    i tak nie blokują produktów. Nigdy nie ruszamy zamówienia, które ma już opłaconą płatność.
    Zwraca liczbę wygaszonych zamówień.
    """
    from payments.models import Payment

    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
    stale = (
        Order.objects.filter(status=Order.STATUS_AWAITING_PAYMENT, created_at__lt=cutoff)
        .exclude(payments__status=Payment.STATUS_PAID)
        .order_by("created_at")
    )
    ids = list(stale.values_list("pk", flat=True)[:limit])
    if not ids:
        return 0

    now = timezone.now()
    Order.objects.filter(pk__in=ids).update(status=Order.STATUS_CANCELLED, updated_at=now)
    Payment.objects.filter(order_id__in=ids, status=Payment.STATUS_PENDING).update(
        status=Payment.STATUS_CANCELLED, updated_at=now
    )
    return len(ids)
