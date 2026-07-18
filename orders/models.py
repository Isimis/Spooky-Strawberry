import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.text import normalize_dashes


def generate_order_confirmation_token():
    return secrets.token_urlsafe(32)


class ShippingMethod(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    free_from_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    # Dostawa do punktu odbioru (np. Paczkomat) - wtedy w checkoutcie klient wybiera punkt
    # na mapie zamiast podawać adres.
    is_pickup_point = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_dashes(self.name)
        self.description = normalize_dashes(self.description)
        super().save(*args, **kwargs)


class DiscountCode(models.Model):
    TYPE_PERCENT = "percent"
    TYPE_FIXED = "fixed"

    TYPE_CHOICES = [
        (TYPE_PERCENT, "Percent"),
        (TYPE_FIXED, "Fixed amount"),
    ]

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    # Gdy True, każdy klient może wykorzystać ten kod tylko raz (sprawdzane po koncie i e-mailu).
    once_per_user = models.BooleanField(default=False)
    # Gdy True, kod działa wyłącznie przed pierwszym opłaconym zamówieniem klienta.
    first_order_only = models.BooleanField(default=False)
    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def already_used_by(self, *, user=None, email=""):
        """Czy dany klient już wykorzystał kod w opłaconym zamówieniu.

        Sprawdzamy po zalogowanym koncie i po adresie e-mail, żeby limit „raz na
        użytkownika" działał także dla zakupów bez logowania. Nie liczymy zamówień
        oczekujących na płatność, dzięki czemu klient może bez problemu ponowić płatność.
        """
        from django.db.models import Q

        conditions = Q()
        if user is not None and getattr(user, "is_authenticated", False):
            conditions |= Q(user=user)
        email = (email or "").strip()
        if email:
            conditions |= Q(email__iexact=email)
        if not conditions:
            return False
        return (
            self.orders.filter(conditions)
            .exclude(status__in=[Order.STATUS_DRAFT, Order.STATUS_AWAITING_PAYMENT, Order.STATUS_CANCELLED])
            .exists()
        )

    def customer_has_paid_order(self, *, user=None, email=""):
        """Czy klient ma wcześniejsze opłacone/zrealizowane zamówienie.

        Łączymy konto i e-mail, żeby zasada działała również dla zakupów bez konta.
        Pomijamy szkice, oczekujące płatności i anulowane zamówienia.
        """
        from django.db.models import Q

        conditions = Q()
        if user is not None and getattr(user, "is_authenticated", False):
            conditions |= Q(user=user)
        email = (email or "").strip()
        if email:
            conditions |= Q(email__iexact=email)
        if not conditions:
            return False
        return (
            Order.objects.filter(conditions)
            .exclude(status__in=[Order.STATUS_DRAFT, Order.STATUS_AWAITING_PAYMENT, Order.STATUS_CANCELLED])
            .exists()
        )


class Order(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_AWAITING_PAYMENT = "awaiting_payment"
    STATUS_PLACED = "placed"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PACKED = "packed"
    STATUS_SHIPPED = "shipped"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Szkic"),
        (STATUS_AWAITING_PAYMENT, "Oczekuje na płatność"),
        (STATUS_PLACED, "Złożone"),
        (STATUS_CONFIRMED, "Potwierdzone"),
        (STATUS_PACKED, "Spakowane"),
        (STATUS_SHIPPED, "Wysłane"),
        (STATUS_CANCELLED, "Anulowane"),
    ]

    order_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    confirmation_token = models.CharField(
        max_length=80,
        unique=True,
        blank=True,
        default=generate_order_confirmation_token,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    shipping_address_line_1 = models.CharField(max_length=180, blank=True)
    shipping_address_line_2 = models.CharField(max_length=180, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_country = models.CharField(max_length=80, default="Polska")
    # Wybrany punkt odbioru (Paczkomat) - wypełnione zamiast adresu przy dostawie do punktu.
    pickup_point_code = models.CharField(max_length=40, blank=True)
    pickup_point_name = models.CharField(max_length=180, blank=True)
    pickup_point_address = models.CharField(max_length=255, blank=True)
    customer_note = models.TextField(blank=True)
    # Wewnętrzny komentarz obsługi - widoczny tylko w panelu, nigdy dla klienta.
    admin_note = models.TextField(blank=True)
    # Śledzenie przesyłki - trafia do maila „wysłane", gdy uzupełnione.
    tracking_number = models.CharField(max_length=80, blank=True)
    tracking_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
    )
    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    source_session_key = models.CharField(max_length=80, blank=True)
    # Zamówienie złożone w trybie testowym (Sandbox) - nie wpływa na magazyn i jest
    # oznaczone w panelu, żeby nie mylić go z realną sprzedażą.
    is_test = models.BooleanField(default=False)
    placed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="order_status_created_idx"),
            models.Index(fields=["email"], name="order_email_idx"),
        ]

    def __str__(self):
        return self.order_number or f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=180)
    variant_name = models.CharField(max_length=180, blank=True)
    sku = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
