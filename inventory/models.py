from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class StockEntry(models.Model):
    """Pojedynczy ruch magazynowy (przyjęcie lub wydanie) przypięty do wariantu.

    Magazyn jest źródłem prawdy dla stanu: ``ProductVariant.stock_quantity`` liczymy
    z sumy wpisów (patrz ``inventory.services.recalculate_variant_stock``).
    """

    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"
    DIRECTION_CHOICES = [
        (DIRECTION_IN, "Przyjęcie"),
        (DIRECTION_OUT, "Wydanie"),
    ]

    SOURCE_OPENING = "opening"
    SOURCE_PURCHASE = "purchase"
    SOURCE_COMPLAINT = "complaint"
    SOURCE_SALE = "sale"
    SOURCE_ADJUSTMENT = "adjustment"
    SOURCE_CHOICES = [
        (SOURCE_OPENING, "Stan początkowy"),
        (SOURCE_PURCHASE, "Zakup"),
        (SOURCE_COMPLAINT, "Reklamacja"),
        (SOURCE_SALE, "Sprzedaż"),
        (SOURCE_ADJUSTMENT, "Korekta"),
    ]

    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="stock_entries",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default=DIRECTION_IN)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_PURCHASE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    occurred_at = models.DateField(default=timezone.localdate)

    unit_price_net = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True
    )
    vat_rate = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True,
        help_text="Stawka VAT w procentach, np. 23.",
    )
    unit_price_gross = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True
    )
    customs_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True,
        help_text="Kwota cła (opcjonalnie).",
    )

    invoice = models.FileField(upload_to="invoices/%Y/%m/", blank=True)
    supplier_url = models.URLField(blank=True)
    note = models.CharField(max_length=255, blank=True)

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.SET_NULL,
        related_name="stock_entries",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="stock_entries",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        indexes = [
            models.Index(fields=["variant", "occurred_at"], name="stock_variant_date_idx"),
        ]

    def __str__(self):
        return f"{self.get_source_display()} · {self.variant} × {self.quantity}"

    @property
    def signed_quantity(self):
        return self.quantity if self.direction == self.DIRECTION_IN else -self.quantity
