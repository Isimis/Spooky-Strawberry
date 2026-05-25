from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant


class SessionCartTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Chokery", slug="chokery")
        self.product = Product.objects.create(
            name="Test Choker",
            slug="test-choker",
            category=category,
            base_price="29.00",
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
