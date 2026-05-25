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
            base_price="29.00",
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
            base_price="31.00",
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
            base_price="31.00",
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
