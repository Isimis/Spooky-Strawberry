from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from orders.models import Order
from orders.services import expire_stale_pending_orders
from payments.models import Payment


def _order(status=Order.STATUS_AWAITING_PAYMENT, minutes_ago=0):
    order = Order.objects.create(
        email="k@example.pl", first_name="A", last_name="B",
        shipping_address_line_1="Ul. 1", shipping_postal_code="00-001", shipping_city="Wwa",
        status=status, subtotal=Decimal("10"), grand_total=Decimal("10"),
    )
    if minutes_ago:
        # created_at ma auto_now_add, więc ustawiamy bezpośrednio przez update
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
    return order


class ExpirePendingOrdersTests(TestCase):
    def test_cancels_only_old_unpaid_pending_orders(self):
        old_pending = _order(minutes_ago=200)
        fresh_pending = _order(minutes_ago=5)
        old_placed = _order(status=Order.STATUS_PLACED, minutes_ago=200)

        count = expire_stale_pending_orders(older_than_minutes=120)
        self.assertEqual(count, 1)

        old_pending.refresh_from_db()
        fresh_pending.refresh_from_db()
        old_placed.refresh_from_db()
        self.assertEqual(old_pending.status, Order.STATUS_CANCELLED)
        self.assertEqual(fresh_pending.status, Order.STATUS_AWAITING_PAYMENT)  # świeże zostaje
        self.assertEqual(old_placed.status, Order.STATUS_PLACED)  # opłacone nietknięte

    def test_never_cancels_order_with_paid_payment(self):
        order = _order(minutes_ago=300)
        Payment.objects.create(order=order, session_id="s1", amount=Decimal("10"), status=Payment.STATUS_PAID)

        count = expire_stale_pending_orders(older_than_minutes=120)
        self.assertEqual(count, 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_AWAITING_PAYMENT)
