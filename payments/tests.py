from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from catalog.models import Category, Product, ProductVariant
from core.models import SiteSettings
from inventory.models import StockEntry
from orders.models import Order, OrderItem
from payments import przelewy24
from payments.models import Payment
from payments.services import handle_notification

P24_SETTINGS = dict(
    P24_MERCHANT_ID="123456",
    P24_POS_ID="123456",
    P24_CRC="crc-secret",
    P24_API_KEY="api-secret",
    P24_SANDBOX=True,
)


@override_settings(**P24_SETTINGS)
class SignatureTests(TestCase):
    def test_sign_is_deterministic_sha384(self):
        fields = {"sessionId": "abc", "merchantId": 123456, "amount": 1000, "currency": "PLN", "crc": "crc-secret"}
        first = przelewy24._sign(fields)
        second = przelewy24._sign(fields)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 96)  # SHA-384 hex

    def test_notification_sign_roundtrip(self):
        data = {
            "merchantId": 123456, "posId": 123456, "sessionId": "s1", "amount": 5000,
            "originAmount": 5000, "currency": "PLN", "orderId": 999, "methodId": 25,
            "statement": "stmt",
        }
        cfg = przelewy24._config()
        data["sign"] = przelewy24._sign({
            "merchantId": 123456, "posId": 123456, "sessionId": "s1", "amount": 5000,
            "originAmount": 5000, "currency": "PLN", "orderId": 999, "methodId": 25,
            "statement": "stmt", "crc": cfg["crc"],
        })
        self.assertTrue(przelewy24.verify_notification_sign(data))
        data["sign"] = "zły-podpis"
        self.assertFalse(przelewy24.verify_notification_sign(data))


@override_settings(**P24_SETTINGS)
class HandleNotificationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Płatności")
        self.product = Product.objects.create(name="Choker", category=self.category, regular_price=Decimal("50.00"))
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=10, is_active=True)
        self.order = Order.objects.create(
            email="klient@example.pl", first_name="Ala", last_name="Kot",
            shipping_address_line_1="Ul. 1", shipping_postal_code="00-001", shipping_city="Warszawa",
            status=Order.STATUS_AWAITING_PAYMENT, subtotal=Decimal("50.00"),
            shipping_total=Decimal("0.00"), grand_total=Decimal("50.00"),
        )
        self.order.order_number = f"SS-{10000 + self.order.pk}"
        self.order.save(update_fields=["order_number"])
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, variant=self.variant,
            product_name="Choker", quantity=3, unit_price=Decimal("50.00"), line_total=Decimal("150.00"),
        )
        self.payment = Payment.objects.create(
            order=self.order, session_id="sess-1", amount=Decimal("50.00"), status=Payment.STATUS_PENDING,
        )
        # Domyślnie tryb sandbox pomija magazyn — testy stanów robimy w trybie realnym.
        settings_obj = SiteSettings.load()
        settings_obj.payments_sandbox = False
        settings_obj.save(update_fields=["payments_sandbox"])

    def _notification(self, amount=5000):
        return {"sessionId": "sess-1", "amount": amount, "orderId": 4242, "currency": "PLN"}

    @patch("payments.services.przelewy24.verify", return_value=(True, {"data": {"status": "success"}}))
    @patch("payments.services.przelewy24.verify_notification_sign", return_value=True)
    def test_paid_flow_marks_order_and_decrements_stock(self, mock_sign, mock_verify):
        result = handle_notification(self._notification())
        self.assertTrue(result)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_PAID)
        self.assertEqual(self.payment.p24_order_id, "4242")
        self.assertEqual(self.order.status, Order.STATUS_PLACED)
        self.assertIsNotNone(self.order.placed_at)
        # sprzedaż zeszła ze stanu (10 - 3)
        entry = StockEntry.objects.get(order_item=self.item, source=StockEntry.SOURCE_SALE)
        self.assertEqual(entry.direction, StockEntry.DIRECTION_OUT)
        self.assertEqual(self.variant.stock_quantity, 7)

    @patch("payments.services.przelewy24.verify", return_value=(True, {"data": {"status": "success"}}))
    @patch("payments.services.przelewy24.verify_notification_sign", return_value=True)
    def test_second_notification_is_idempotent(self, mock_sign, mock_verify):
        self.assertTrue(handle_notification(self._notification()))
        self.assertTrue(handle_notification(self._notification()))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 7)  # nie zeszło drugi raz
        self.assertEqual(StockEntry.objects.filter(order_item=self.item, source=StockEntry.SOURCE_SALE).count(), 1)

    @patch("payments.services.przelewy24.verify", return_value=(True, {"data": {"status": "success"}}))
    @patch("payments.services.przelewy24.verify_notification_sign", return_value=True)
    def test_sandbox_mode_does_not_touch_stock(self, mock_sign, mock_verify):
        settings_obj = SiteSettings.load()
        settings_obj.payments_sandbox = True
        settings_obj.save(update_fields=["payments_sandbox"])

        self.assertTrue(handle_notification(self._notification()))
        self.order.refresh_from_db()
        self.variant.refresh_from_db()
        # zamówienie opłacone, ale stany magazynowe nietknięte w trybie testowym
        self.assertEqual(self.order.status, Order.STATUS_PLACED)
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertFalse(StockEntry.objects.filter(order_item=self.item, source=StockEntry.SOURCE_SALE).exists())

    @patch("payments.services.przelewy24.verify_notification_sign", return_value=False)
    def test_bad_signature_rejected(self, mock_sign):
        self.assertFalse(handle_notification(self._notification()))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_PENDING)

    @patch("payments.services.przelewy24.verify_notification_sign", return_value=True)
    def test_amount_mismatch_rejected(self, mock_sign):
        # webhook twierdzi 40 zł, a płatność jest na 50 zł
        self.assertFalse(handle_notification(self._notification(amount=4000)))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_PENDING)
