from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerAddress, CustomerProfile
from catalog.models import Category, Product, ProductVariant
from orders.models import DiscountCode, Order, ShippingMethod
from orders.shipping import FREE_SHIPPING_THRESHOLD
from payments.models import Payment

User = get_user_model()


class CheckoutSaveAddressTests(TestCase):
    def setUp(self):
        self.kurier = ShippingMethod.objects.create(
            code="kurier-addr",
            name="Kurier",
            price=Decimal("13.99"),
            is_active=True,
            sort_order=20,
        )
        category = Category.objects.create(name="Chokery", slug="save-addr-chokery")
        self.product = Product.objects.create(
            name="Choker",
            slug="save-addr-choker",
            category=category,
            regular_price=Decimal("29.00"),
            status=Product.STATUS_ACTIVE,
        )
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=5, is_active=True)
        self.user = User.objects.create_user(
            username="klientka@example.pl", email="klientka@example.pl", password="spookypass123"
        )

    def _cart(self):
        session = self.client.session
        session["cart"] = {str(self.variant.id): {"quantity": 1}}
        session.save()

    def _post_data(self, **extra):
        data = {
            "first_name": "Maja",
            "last_name": "Nowak",
            "email": "klientka@example.pl",
            "phone": "500600700",
            "shipping_method": self.kurier.id,
            "address_line_1": "Ciemna 13",
            "address_line_2": "",
            "postal_code": "00-001",
            "city": "Warszawa",
        }
        data.update(extra)
        return data

    def test_checkbox_saves_default_address(self):
        self.client.force_login(self.user)
        self._cart()
        response = self.client.post(reverse("checkout:shipping"), self._post_data(save_address="on"))
        self.assertRedirects(response, reverse("checkout:payment"))
        address = CustomerProfile.objects.get(user=self.user).default_shipping_address()
        self.assertIsNotNone(address)
        self.assertEqual(address.address_line_1, "Ciemna 13")
        self.assertTrue(address.is_default)

    def test_without_checkbox_address_is_not_saved(self):
        self.client.force_login(self.user)
        self._cart()
        response = self.client.post(reverse("checkout:shipping"), self._post_data())
        self.assertRedirects(response, reverse("checkout:payment"))
        profile = CustomerProfile.objects.filter(user=self.user).first()
        self.assertTrue(profile is None or profile.default_shipping_address() is None)

    def test_personal_data_syncs_to_account(self):
        self.client.force_login(self.user)
        self._cart()
        response = self.client.post(
            reverse("checkout:shipping"), self._post_data(phone="501502503")
        )
        self.assertRedirects(response, reverse("checkout:payment"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Maja")
        self.assertEqual(self.user.last_name, "Nowak")
        self.assertEqual(CustomerProfile.objects.get(user=self.user).phone, "501502503")

    def test_checkout_email_updates_order_email_not_login(self):
        self.client.force_login(self.user)
        self._cart()
        response = self.client.post(
            reverse("checkout:shipping"), self._post_data(email="inny@example.pl")
        )
        self.assertRedirects(response, reverse("checkout:payment"))
        self.user.refresh_from_db()
        # Adres logowania konta zostaje bez zmian...
        self.assertEqual(self.user.email, "klientka@example.pl")
        self.assertEqual(self.user.username, "klientka@example.pl")
        # ...ale e-mail do zamówień zapisuje się na profilu.
        self.assertEqual(CustomerProfile.objects.get(user=self.user).order_email, "inny@example.pl")

    def test_checkout_prefills_saved_address(self):
        profile, _ = CustomerProfile.objects.get_or_create(user=self.user)
        CustomerAddress.objects.create(
            profile=profile,
            address_type=CustomerAddress.TYPE_SHIPPING,
            first_name="Maja",
            last_name="Nowak",
            address_line_1="Ciemna 13",
            postal_code="00-001",
            city="Warszawa",
            is_default=True,
        )
        self.client.force_login(self.user)
        self._cart()
        response = self.client.get(reverse("checkout:shipping"))
        self.assertContains(response, "Ciemna 13")


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
            status=Order.STATUS_PLACED,
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

    @patch("checkout.views.start_payment", return_value="https://sandbox.przelewy24.pl/trnRequest/discount")
    def test_payment_saves_discount_on_order_and_recalculates_shipping_threshold(self, mock_start):
        self._put_product_in_cart(quantity=2)  # 58,00 zł produktów
        self._put_checkout_data_in_session()
        code = DiscountCode.objects.create(
            code="SPOOKY10",
            discount_type=DiscountCode.TYPE_PERCENT,
            value=Decimal("10.00"),
        )
        session = self.client.session
        session["cart_discount_code"] = code.code
        session.save()

        self.client.post(reverse("checkout:payment"), {"payment_method": "blik", "accept_terms": "1"})
        order = Order.objects.get()

        self.assertEqual(order.discount_code, code)
        self.assertEqual(order.discount_total, Decimal("5.80"))
        self.assertEqual(order.shipping_total, Decimal("10.99"))
        self.assertEqual(order.grand_total, Decimal("63.19"))

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

    @patch("checkout.views.start_payment", return_value="https://sandbox.przelewy24.pl/trnRequest/tok")
    def test_repeated_payment_reuses_pending_order(self, mock_start):
        self._put_product_in_cart()
        self._put_checkout_data_in_session()
        url = reverse("checkout:payment")
        self.client.post(url, {"payment_method": "blik", "accept_terms": "1"})
        self.client.post(url, {"payment_method": "blik", "accept_terms": "1"})
        self.assertEqual(Order.objects.count(), 1)  # ponowna próba nie tworzy duplikatu

    def test_payment_redirects_to_cart_when_stock_dropped(self):
        self._put_product_in_cart(quantity=3)
        self._put_checkout_data_in_session()
        self.variant.stock_quantity = 1
        self.variant.save(update_fields=["stock_quantity"])
        response = self.client.post(reverse("checkout:payment"), {"payment_method": "blik", "accept_terms": "1"})
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(Order.objects.exists())

    def test_payment_return_shows_failure_after_max_attempts(self):
        order = self._create_order()
        order.status = Order.STATUS_AWAITING_PAYMENT
        order.save(update_fields=["status"])
        payment = Payment.objects.create(order=order, session_id="sess-fail", amount=order.grand_total, status=Payment.STATUS_PENDING)
        session = self.client.session
        session["payment_session_id"] = payment.session_id
        session.save()
        response = self.client.get(reverse("checkout:payment_return") + "?try=5")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nie potwierdziliśmy płatności")

    def test_confirmation_unpaid_shows_awaiting_state(self):
        order = self._create_order()
        order.status = Order.STATUS_AWAITING_PAYMENT
        order.save(update_fields=["status"])
        response = self.client.get(reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token]))
        self.assertContains(response, "czeka na płatność")
        self.assertNotContains(response, "Dziękujemy za zamówienie")

    @patch("checkout.views.start_payment", return_value="https://x/tok")
    def test_sandbox_order_is_marked_test(self, mock_start):
        self._put_product_in_cart()
        self._put_checkout_data_in_session()
        self.client.post(reverse("checkout:payment"), {"payment_method": "blik", "accept_terms": "1"})
        self.assertTrue(Order.objects.get().is_test)


class ShippingFormTests(TestCase):
    def setUp(self):
        from decimal import Decimal as D
        self.paczkomat, _ = ShippingMethod.objects.update_or_create(
            code="paczkomat", defaults={"name": "Paczkomat", "price": D("10.99"), "is_active": True, "is_pickup_point": True}
        )
        self.kurier, _ = ShippingMethod.objects.update_or_create(
            code="kurier", defaults={"name": "Kurier", "price": D("13.99"), "is_active": True, "is_pickup_point": False}
        )

    def _base(self, method):
        return {"first_name": "A", "last_name": "B", "email": "a@b.pl", "phone": "", "shipping_method": method.id}

    def test_paczkomat_requires_point(self):
        from checkout.forms import CheckoutForm
        self.assertFalse(CheckoutForm(self._base(self.paczkomat)).is_valid())
        data = self._base(self.paczkomat)
        data["pickup_point_code"] = "KRA010"
        self.assertTrue(CheckoutForm(data).is_valid())

    def test_kurier_requires_address(self):
        from checkout.forms import CheckoutForm
        self.assertFalse(CheckoutForm(self._base(self.kurier)).is_valid())
        data = self._base(self.kurier)
        data.update({"address_line_1": "Ul. 1", "postal_code": "00-001", "city": "Wwa"})
        self.assertTrue(CheckoutForm(data).is_valid())

    def test_paczkomat_clears_address(self):
        from checkout.forms import CheckoutForm
        data = self._base(self.paczkomat)
        data.update({"pickup_point_code": "KRA010", "address_line_1": "Zbędna 9"})
        form = CheckoutForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["address_line_1"], "")  # adres czyszczony przy paczkomacie


class FullPurchaseFlowTests(TestCase):
    """Pełne ścieżki zakupowe przez realne widoki: dostawa → płatność → webhook → potwierdzenie."""

    def setUp(self):
        from decimal import Decimal as D
        from core.models import SiteSettings
        self.paczkomat, _ = ShippingMethod.objects.update_or_create(
            code="paczkomat", defaults={"name": "Paczkomat", "price": D("10.99"), "is_active": True, "is_pickup_point": True, "sort_order": 10}
        )
        self.kurier, _ = ShippingMethod.objects.update_or_create(
            code="kurier", defaults={"name": "Kurier", "price": D("13.99"), "is_active": True, "is_pickup_point": False, "sort_order": 20}
        )
        cat = Category.objects.create(name="Test", slug="flow-test")
        self.product = Product.objects.create(name="Choker Flow", slug="choker-flow", category=cat, regular_price=D("29.00"), status=Product.STATUS_ACTIVE)
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=5, is_active=True)
        self.settings = SiteSettings.load()

    def _cart(self, qty=1):
        s = self.client.session
        s["cart"] = {str(self.variant.id): {"quantity": qty}}
        s.save()

    def _sandbox(self, on):
        self.settings.payments_sandbox = on
        self.settings.save(update_fields=["payments_sandbox"])

    def _pay_and_confirm(self, order):
        """Symuluje bramkę: znajduje płatność, odpala webhook, przechodzi payment_return."""
        from payments.services import handle_notification
        payment = order.payments.order_by("-created_at").first()
        with patch("payments.services.przelewy24.verify_notification_sign", return_value=True), \
             patch("payments.services.przelewy24.verify", return_value=(True, {"data": {"status": "success"}})):
            ok = handle_notification({
                "sessionId": payment.session_id, "amount": payment.amount_grosze,
                "orderId": 12345, "currency": "PLN",
            })
        self.assertTrue(ok, "webhook powinien potwierdzić płatność")
        return self.client.get(reverse("checkout:payment_return"))

    @patch("payments.services.przelewy24.register", return_value=("tok-pk", {}))
    def test_paczkomat_full_flow_sandbox(self, mock_reg):
        self._sandbox(True)
        self._cart()
        # 1) krok dostawy - paczkomat
        r = self.client.post(reverse("checkout:shipping"), {
            "first_name": "Ala", "last_name": "Kot", "email": "ala@example.pl", "phone": "500600700",
            "shipping_method": self.paczkomat.id,
            "pickup_point_code": "WAW104M", "pickup_point_name": "WAW104M",
            "pickup_point_address": "Trakt Brzeski 55, 05-077 Warszawa",
        })
        self.assertRedirects(r, reverse("checkout:payment"))
        self.assertEqual(self.client.session["checkout"]["pickup_point_code"], "WAW104M")
        # 2) płatność
        r = self.client.post(reverse("checkout:payment"), {"payment_method": "blik", "accept_terms": "1"})
        order = Order.objects.get()
        self.assertEqual(order.status, Order.STATUS_AWAITING_PAYMENT)
        self.assertEqual(order.pickup_point_code, "WAW104M")
        self.assertEqual(order.pickup_point_address, "Trakt Brzeski 55, 05-077 Warszawa")
        self.assertEqual(order.shipping_address_line_1, "")   # brak adresu przy paczkomacie
        self.assertTrue(order.is_test)                        # sandbox → test
        self.assertIn("trnRequest/tok-pk", r.url)
        # 3) webhook + powrót
        r = self._pay_and_confirm(order)
        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PLACED)
        self.assertEqual(self.variant.stock_quantity, 5)      # sandbox nie rusza magazynu
        self.assertRedirects(r, reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token]), fetch_redirect_response=False)
        # 4) potwierdzenie dla klienta
        c = self.client.get(reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token]))
        self.assertContains(c, "WAW104M")
        self.assertContains(c, "Dziękujemy")
        # 5) widok admina
        from dashboard.views import get_order_address_lines, build_order_row
        self.assertTrue(any("WAW104M" in l for l in get_order_address_lines(order)))
        self.assertTrue(build_order_row(order)["is_test"])

    @patch("payments.services.przelewy24.register", return_value=("tok-kur", {}))
    def test_kurier_full_flow_real_mode_decrements_stock(self, mock_reg):
        self._sandbox(False)   # tryb realny
        self._cart(qty=2)
        r = self.client.post(reverse("checkout:shipping"), {
            "first_name": "Ola", "last_name": "Nowak", "email": "ola@example.pl", "phone": "600",
            "shipping_method": self.kurier.id,
            "address_line_1": "Ciemna 13", "postal_code": "00-001", "city": "Warszawa",
        })
        self.assertRedirects(r, reverse("checkout:payment"))
        r = self.client.post(reverse("checkout:payment"), {"payment_method": "card", "accept_terms": "1"})
        order = Order.objects.get()
        self.assertEqual(order.shipping_address_line_1, "Ciemna 13")
        self.assertEqual(order.pickup_point_code, "")         # brak paczkomatu przy kurierze
        self.assertFalse(order.is_test)                       # tryb realny
        self._pay_and_confirm(order)
        order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PLACED)
        self.assertEqual(self.variant.stock_quantity, 3)      # 5 - 2 = 3 (tryb realny schodzi ze stanu)
        c = self.client.get(reverse("checkout:confirmation", args=[order.order_number, order.confirmation_token]))
        self.assertContains(c, "Ciemna 13")

    def test_paczkomat_without_point_blocked(self):
        self._cart()
        r = self.client.post(reverse("checkout:shipping"), {
            "first_name": "Ala", "last_name": "Kot", "email": "ala@example.pl", "phone": "500",
            "shipping_method": self.paczkomat.id,
        })
        self.assertEqual(r.status_code, 200)   # nie przechodzi dalej
        self.assertContains(r, "Wybierz paczkomat na mapie")
        self.assertNotIn("checkout", self.client.session)

    def test_kurier_without_address_blocked(self):
        self._cart()
        r = self.client.post(reverse("checkout:shipping"), {
            "first_name": "Ala", "last_name": "Kot", "email": "ala@example.pl", "phone": "500",
            "shipping_method": self.kurier.id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Podaj adres dostawy")
