from decimal import Decimal

from django.db import models


class Payment(models.Model):
    """Pojedyncza próba płatności za zamówienie (Przelewy24).

    Webhook P24 jest źródłem prawdy: dopiero potwierdzona transakcja (``verify``)
    ustawia status ``paid`` i przenosi zamówienie dalej.
    """

    PROVIDER_P24 = "przelewy24"
    PROVIDER_CHOICES = [
        (PROVIDER_P24, "Przelewy24"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Oczekuje"),
        (STATUS_PAID, "Opłacona"),
        (STATUS_FAILED, "Nieudana"),
        (STATUS_CANCELLED, "Anulowana"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default=PROVIDER_P24)
    session_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="PLN")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    method = models.CharField(max_length=60, blank=True)

    p24_token = models.CharField(max_length=120, blank=True)
    p24_order_id = models.CharField(max_length=40, blank=True)

    raw_register = models.JSONField(default=dict, blank=True)
    raw_notification = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="payment_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} · {self.session_id} · {self.get_status_display()}"

    @property
    def amount_grosze(self):
        """Kwota w groszach (P24 operuje na liczbach całkowitych)."""
        return int((self.amount * 100).quantize(Decimal("1")))

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID
