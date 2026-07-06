from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant
from orders.models import Order, ShippingMethod
from orders.shipping import FREE_SHIPPING_THRESHOLD
from payments.models import Payment


class CheckoutConfirmationTests(TestCase):
    def setUp(self):
        self.shipping_method, _ = ShippingMethod.objects.update_or_create(
            code="paczkomat",
            defaults={
                "name": "Paczkomat",
                "description": "Dostawa do paczkomatu InPost w 1-2 dni robocze.",
                "price": Decimal("10.99"),
                "free_from_amount": FREE_SHIPPING_THRESHOLD,
                "is_active": True,
                "sort_order": 10,
            },
        )
        ShippingMethod.objects.update_or_create(
            code="kurier",
            defaults={
                "name": "Kurier",
                "description": "Dostawa kurierem pod wskazany adres w 1-2 dni robocze.",
                "price": Decimal("13.99"),
                "free_from_amount": FREE_SHIPPING_THRESHOLD,
                "is_active": True,
                "sort_order": 20,
            },
        )
        category = Category.objects.create(name="Chokery", slug="checkout-chokery")
        self.product = Product.objects.create(
            name="Checkout Choker",
            slug="checkout-choker",
            category=category,
            regular_price=Decimal("29.00"),
            status=Product.STATUS_ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            stock_quantity=5,
            is_active=True,
        )

    def _create_order(self):
        order = Order.objects.create(
            order_number="SS-12345",
            email="kupujaca@example.pl",
            first_name="Maja",
            last_name="Nowak",
            phone="500600700",
            shipping_address_line_1="Ciemna 13",
            shipping_postal_code="00-001",
            shipping_city="Warszawa",
            shipping_method=self.shipping_method,
            subtotal=Decimal("29.00"),
            shipping_total=Decimal("10.99"),
            grand_total=Decimal("39.99"),
        )
        return order

    def _put_product_in_cart(self, quantity=1):
        session = self.client.session
        session["cart"] = {str(self.variant.id): {"quantity": quantity}}
        session.save()

    def _put_checkout_data_in_session(self):
        session = self.client.session
        session["checkout"] = {
            "first_name": "Maja",
            "last_name": "Nowak",
            "email": "kupujaca@example.pl",
            "phone": "500600700",
            "shipping_method": self.shipping_method.id,
            "address_line_1": "Ciemna 13",
            "address_line_2": "",
            "postal_code": "00-001",
            "city": "Warszawa",
        }
        session.save()

    def test_confirmation_with_token_shows_private_details(self):
        order = self._create_order()

        response = self.client.get(
            reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "kupujaca@example.pl")
        self.assertContains(response, "Ciemna 13")

    def test_confirmation_by_order_number_only_is_not_available(self):
        order = self._create_order()

        response = self.client.get(f"/zamowienie/potwierdzenie/{order.order_number}/")

        self.assertEqual(response.status_code, 404)

    def test_confirmation_rejects_wrong_token(self):
        order = self._create_order()

        response = self.client.get(reverse("checkout:confirmation", args=[order.order_number, "wrong-token"]))

        self.assertEqual(response.status_code, 404)

    def test_shipping_step_shows_configured_methods(self):
        self._put_product_in_cart()

        response = self.client.get(reverse("checkout:shipping"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paczkomat")
        self.assertContains(response, "10,99")
        self.assertContains(response, "Kurier")
        self.assertContains(response, "13,99")

    @patch("checkout.views.start_payment", return_value="https://sandbox.przelewy24.pl/trnRequest/tok123")
    def test_payment_creates_awaiting_order_and_redirects_to_gateway(self, mock_start):
        self._put_product_in_cart()
        self._put_checkout_data_in_session()

        response = self.client.post(reverse("checkout:payment"), {"payment_method": "blik", "accept_terms": "1"})
        order = Order.objects.get()

        # zamówienie czeka na płatność, koszyk NIE jest jeszcze czyszczony
        self.assertEqual(order.status, Order.STATUS_AWAITING_PAYMENT)
        # data złożenia uzupełnia się automatycznie już przy utworzeniu zamówienia
        self.assertIsNotNone(order.placed_at)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://sandbox.przelewy24.pl/trnRequest/tok123")
        self.assertIn("cart", self.client.session)
        mock_start.assert_called_once()

    @patch("checkout.views.start_payment")
    def test_payment_requires_terms_acceptance(self, mock_start):
        self._put_product_in_cart()
        self._put_checkout_data_in_session()

        response = self.client.post(reverse("checkout:payment"), {"payment_method": "blik"})

        # bez zaznaczonego checkboxa: brak zamówienia, brak wywołania bramki, strona się przeładowuje
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        mock_start.assert_not_called()

    def test_payment_return_pending_when_not_paid(self):
        order = self._create_order()
        order.status = Order.STATUS_AWAITING_PAYMENT
        order.save(update_fields=["status"])
        payment = Payment.objects.create(
            order=order, session_id="sess-pending", amount=order.grand_total, status=Payment.STATUS_PENDING,
        )
        session = self.client.session
        session["payment_session_id"] = payment.session_id
        session.save()

        response = self.client.get(reverse("checkout:payment_return"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "checkout/payment_pending.html")

    def test_payment_return_redirects_to_confirmation_when_paid(self):
        order = self._create_order()
        payment = Payment.objects.create(
            order=order, session_id="sess-paid", amount=order.grand_total, status=Payment.STATUS_PAID,
        )
        session = self.client.session
        session["payment_session_id"] = payment.session_id
        session.save()

        response = self.client.get(reverse("checkout:payment_return"))
        self.assertRedirects(
            response,
            reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token]),
            fetch_redirect_response=False,
        )
