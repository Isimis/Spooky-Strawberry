from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductVariant


class CatalogViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chokery", slug="chokery")
        self.available_product = Product.objects.create(
            name="Available Choker",
            slug="available-choker",
            category=self.category,
            regular_price="29.00",
            status=Product.STATUS_ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.available_product,
            stock_quantity=4,
            is_active=True,
        )
        self.sold_out_product = Product.objects.create(
            name="Sold Out Choker",
            slug="sold-out-choker",
            category=self.category,
            regular_price="31.00",
            status=Product.STATUS_ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.sold_out_product,
            stock_quantity=0,
            is_active=True,
        )
        self.draft_product = Product.objects.create(
            name="Draft Choker",
            slug="draft-choker",
            category=self.category,
            regular_price="31.00",
            status=Product.STATUS_DRAFT,
        )

    def test_catalog_shows_only_active_products(self):
        response = self.client.get(reverse("catalog:product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.available_product.name)
        self.assertContains(response, self.sold_out_product.name)
        self.assertNotContains(response, self.draft_product.name)

    def test_catalog_filters_by_availability(self):
        response = self.client.get(reverse("catalog:product_list"), {"availability": "in_stock"})

        self.assertContains(response, self.available_product.name)
        self.assertNotContains(response, self.sold_out_product.name)

    def test_product_detail_exposes_cart_action(self):
        response = self.client.get(self.available_product.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dodaj do koszyka")

    def test_product_detail_renders_formatted_description(self):
        self.available_product.description = (
            "## Gotowy opis\n\n"
            "**Mocny detal**\n\n"
            "- Do czarnych butów\n\n"
            "1. Załóż do chokera\n"
            "2. Dodaj cięższe buty"
        )
        self.available_product.save(update_fields=["description"])

        response = self.client.get(self.available_product.get_absolute_url())

        self.assertContains(response, "<h2>Gotowy opis</h2>")
        self.assertContains(response, "<strong>Mocny detal</strong>")
        self.assertContains(response, "<li>Do czarnych butów</li>")
        self.assertContains(response, "<ol><li>Załóż do chokera</li><li>Dodaj cięższe buty</li></ol>")
