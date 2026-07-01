from decimal import Decimal

from django.test import TestCase

from catalog.models import Category, Product, ProductVariant
from inventory.models import StockEntry
from inventory.services import recalculate_variant_stock


class RecalculateVariantStockTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Test")
        self.product = Product.objects.create(name="Test produkt", category=self.category, regular_price=Decimal("10.00"))
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=0)

    def _entry(self, direction, quantity, source=StockEntry.SOURCE_PURCHASE):
        return StockEntry.objects.create(
            variant=self.variant, direction=direction, source=source, quantity=quantity
        )

    def test_in_entries_increase_stock(self):
        self._entry(StockEntry.DIRECTION_IN, 5)
        self._entry(StockEntry.DIRECTION_IN, 3)
        self.assertEqual(recalculate_variant_stock(self.variant), 8)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 8)

    def test_out_entries_decrease_stock(self):
        self._entry(StockEntry.DIRECTION_IN, 10)
        self._entry(StockEntry.DIRECTION_OUT, 4, source=StockEntry.SOURCE_SALE)
        self.assertEqual(recalculate_variant_stock(self.variant), 6)

    def test_stock_never_negative(self):
        self._entry(StockEntry.DIRECTION_OUT, 4, source=StockEntry.SOURCE_SALE)
        self.assertEqual(recalculate_variant_stock(self.variant), 0)

    def test_no_entries_zero(self):
        self.assertEqual(recalculate_variant_stock(self.variant), 0)
