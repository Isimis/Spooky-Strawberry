from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from orders.models import DiscountCode, Order
from orders.discounts import evaluate_discount
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


class DiscountOncePerUserTests(TestCase):
    def _code(self):
        return DiscountCode.objects.create(code="SPOOKY10", value=Decimal("10"), once_per_user=True)

    def _paid_order(self, code, email):
        return Order.objects.create(
            email=email, first_name="A", last_name="B", discount_code=code,
            status=Order.STATUS_PLACED, subtotal=Decimal("50"), grand_total=Decimal("45"),
        )

    def test_not_used_yet(self):
        code = self._code()
        self.assertFalse(code.already_used_by(email="nowa@example.pl"))

    def test_used_by_email_blocks_reuse(self):
        code = self._code()
        self._paid_order(code, "ala@example.pl")
        self.assertTrue(code.already_used_by(email="ala@example.pl"))
        self.assertTrue(code.already_used_by(email="ALA@example.pl"))  # case-insensitive
        self.assertFalse(code.already_used_by(email="inna@example.pl"))

    def test_cancelled_order_does_not_count(self):
        code = self._code()
        o = self._paid_order(code, "ala@example.pl")
        o.status = Order.STATUS_CANCELLED
        o.save(update_fields=["status"])
        self.assertFalse(code.already_used_by(email="ala@example.pl"))


class DiscountFirstOrderTests(TestCase):
    def _order(self, email, status=Order.STATUS_PLACED):
        return Order.objects.create(
            email=email,
            first_name="A",
            last_name="B",
            status=status,
            subtotal=Decimal("50"),
            grand_total=Decimal("50"),
        )

    def test_first_order_code_works_for_new_email(self):
        code = DiscountCode.objects.create(code="FIRST10", value=Decimal("10"), first_order_only=True)
        result = evaluate_discount(code, subtotal=Decimal("50"), email="nowa@example.pl")
        self.assertTrue(result.is_valid)

    def test_first_order_code_blocks_customer_with_previous_paid_order(self):
        code = DiscountCode.objects.create(code="FIRST10", value=Decimal("10"), first_order_only=True)
        self._order("ala@example.pl")
        result = evaluate_discount(code, subtotal=Decimal("50"), email="ALA@example.pl")
        self.assertFalse(result.is_valid)
        self.assertIn("pierwszym", result.error)

    def test_first_order_code_ignores_cancelled_and_unpaid_orders(self):
        code = DiscountCode.objects.create(code="FIRST10", value=Decimal("10"), first_order_only=True)
        self._order("ala@example.pl", status=Order.STATUS_CANCELLED)
        self._order("ala@example.pl", status=Order.STATUS_AWAITING_PAYMENT)
        result = evaluate_discount(code, subtotal=Decimal("50"), email="ala@example.pl")
        self.assertTrue(result.is_valid)
