from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from .models import Outfit, OutfitItem


class OutfitViewTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Akcesoria", slug="akcesoria")
        product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            category=category,
            regular_price="20.00",
            status=Product.STATUS_ACTIVE,
        )
        self.outfit = Outfit.objects.create(
            name="Test Outfit",
            slug="test-outfit",
            status=Outfit.STATUS_ACTIVE,
            short_description="Test description",
        )
        OutfitItem.objects.create(outfit=self.outfit, product=product)

    def test_outfit_list_and_detail_render(self):
        list_response = self.client.get(reverse("outfits:list"))
        detail_response = self.client.get(self.outfit.get_absolute_url())

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Test Outfit")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Produkty w zestawie")
