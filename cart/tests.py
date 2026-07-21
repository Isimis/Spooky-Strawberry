from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant
from orders.models import DiscountCode, ShippingMethod
from orders.shipping import FREE_SHIPPING_THRESHOLD

from .views import get_shipping_estimate


class SessionCartTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Chokery", slug="chokery")
        self.product = Product.objects.create(
            name="Test Choker",
            slug="test-choker",
            category=category,
            regular_price="29.00",
            status=Product.STATUS_ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            stock_quantity=5,
            is_active=True,
        )

    def test_add_update_and_remove_cart_item(self):
        add_response = self.client.post(
            reverse("cart:add"),
            {"variant_id": self.variant.id, "quantity": 2},
        )
        self.assertRedirects(add_response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"][str(self.variant.id)]["quantity"], 2)

        update_response = self.client.post(
            reverse("cart:update", args=[self.variant.id]),
            {"quantity": 3},
        )
        self.assertRedirects(update_response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"][str(self.variant.id)]["quantity"], 3)

        remove_response = self.client.post(reverse("cart:remove", args=[self.variant.id]))
        self.assertRedirects(remove_response, reverse("cart:detail"))
        self.assertNotIn(str(self.variant.id), self.client.session["cart"])

    def test_cart_limits_quantity_to_stock(self):
        response = self.client.post(
            reverse("cart:add"),
            {"variant_id": self.variant.id, "quantity": 99},
        )

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual(self.client.session["cart"][str(self.variant.id)]["quantity"], 5)

    def test_cart_removes_unavailable_variant_on_update(self):
        self.client.post(reverse("cart:add"), {"variant_id": self.variant.id, "quantity": 2})
        self.variant.stock_quantity = 0
        self.variant.save()

        response = self.client.post(
            reverse("cart:update", args=[self.variant.id]),
            {"quantity": 2},
        )

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertNotIn(str(self.variant.id), self.client.session["cart"])

    def test_cart_detail_renders_empty_state(self):
        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Twój koszyk jest pusty")

    def test_percent_discount_is_applied_to_cart_total(self):
        self.client.post(reverse("cart:add"), {"variant_id": self.variant.id, "quantity": 2})
        DiscountCode.objects.create(
            code="SPOOKY10",
            discount_type=DiscountCode.TYPE_PERCENT,
            value=Decimal("10.00"),
        )

        response = self.client.post(reverse("cart:discount_apply"), {"code": "spooky10"})
        self.assertRedirects(response, reverse("cart:detail"))
        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.context["discount_total"], Decimal("5.80"))
        self.assertEqual(response.context["grand_total"], Decimal("71.19"))
        self.assertContains(response, "Rabat")

    def test_shipping_discount_code_makes_cart_delivery_free(self):
        self.client.post(reverse("cart:add"), {"variant_id": self.variant.id, "quantity": 1})
        DiscountCode.objects.create(
            code="DOSTAWAGRATIS",
            discount_type=DiscountCode.TYPE_PERCENT,
            applies_to=DiscountCode.APPLIES_TO_SHIPPING,
            value=Decimal("100.00"),
        )

        self.client.post(reverse("cart:discount_apply"), {"code": "dostawagratis"})
        response = self.client.get(reverse("cart:detail"))

        self.assertEqual(response.context["discount_total"], Decimal("18.99"))
        self.assertEqual(response.context["shipping_cost"], Decimal("0.00"))
        self.assertEqual(response.context["grand_total"], Decimal("29.00"))
        self.assertContains(response, "Rabat na dostawa")

    def test_invalid_discount_is_not_saved_in_cart(self):
        self.client.post(reverse("cart:add"), {"variant_id": self.variant.id, "quantity": 1})
        DiscountCode.objects.create(code="MIN100", value=Decimal("10.00"), minimum_order_amount=Decimal("100.00"))

        self.client.post(reverse("cart:discount_apply"), {"code": "min100"})

        self.assertNotIn("cart_discount_code", self.client.session)


class CartShippingEstimateTests(TestCase):
    def setUp(self):
        ShippingMethod.objects.update_or_create(
            code="paczkomat",
            defaults={
                "name": "Paczkomat",
                "description": "Dostawa do paczkomatu InPost w 1-2 dni robocze.",
                "price": Decimal("18.99"),
                "free_from_amount": FREE_SHIPPING_THRESHOLD,
                "is_active": True,
                "sort_order": 10,
            },
        )

    def test_cart_below_free_shipping_threshold_uses_paczkomat_price(self):
        shipping_cost, free_from, remaining = get_shipping_estimate(Decimal("99.99"))

        self.assertEqual(shipping_cost, Decimal("18.99"))
        self.assertEqual(free_from, Decimal("100.00"))
        self.assertEqual(remaining, Decimal("0.01"))

    def test_cart_at_free_shipping_threshold_is_free(self):
        shipping_cost, free_from, remaining = get_shipping_estimate(Decimal("100.00"))

        self.assertEqual(shipping_cost, Decimal("0.00"))
        self.assertEqual(free_from, Decimal("100.00"))
        self.assertEqual(remaining, Decimal("0.00"))


class PersistentCartTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        category = Category.objects.create(name="Chokery", slug="chokery")
        self.product = Product.objects.create(
            name="Persist Choker",
            slug="persist-choker",
            category=category,
            regular_price="29.00",
            status=Product.STATUS_ACTIVE,
        )
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=5, is_active=True)
        User = get_user_model()
        User.objects.create_user(username="buy@example.pl", email="buy@example.pl", password="spookypass123")

    def _login(self):
        # Realny login wyzwala sygnał user_logged_in (scalanie koszyka).
        self.client.post(reverse("accounts:login_submit"), {"email": "buy@example.pl", "password": "spookypass123"})

    def test_cart_persists_across_sessions_for_same_user(self):
        from cart.models import SavedCart

        self._login()
        self.client.post(reverse("cart:add"), {"variant_id": self.variant.id, "quantity": 2})
        self.assertTrue(SavedCart.objects.filter(user__email="buy@example.pl").exists())

        # Nowa sesja: wyloguj (flush) i zaloguj ponownie - koszyk powinien wrócić.
        self.client.logout()
        self.assertNotIn("cart", self.client.session)
        self._login()

        self.assertEqual(self.client.session["cart"][str(self.variant.id)]["quantity"], 2)
        response = self.client.get(reverse("cart:detail"))
        self.assertContains(response, "Persist Choker")
