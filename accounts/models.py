from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField(max_length=40, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    preferred_aesthetics = models.ManyToManyField(
        "catalog.Aesthetic",
        related_name="customer_profiles",
        blank=True,
    )
    accepts_marketing = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return self.user.get_username()

    def default_shipping_address(self):
        """Domyślny adres dostawy klienta (jeden na konto) lub None."""
        return (
            self.addresses.filter(address_type=CustomerAddress.TYPE_SHIPPING)
            .order_by("-is_default", "id")
            .first()
        )


class SocialIdentity(models.Model):
    """Powiązanie konta z logowaniem Google/Apple.

    `subject` to stały identyfikator użytkownika u dostawcy (claim `sub`
    z id_tokenu) — nie zmienia się nawet, gdy użytkownik zmieni e-mail.
    """

    PROVIDER_GOOGLE = "google"
    PROVIDER_APPLE = "apple"

    PROVIDER_CHOICES = [
        (PROVIDER_GOOGLE, "Google"),
        (PROVIDER_APPLE, "Apple"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_identities",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    subject = models.CharField(max_length=191)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "subject"],
                name="unique_social_identity",
            ),
        ]

    def __str__(self):
        return f"{self.user.get_username()} ({self.provider})"


class CustomerAddress(models.Model):
    TYPE_SHIPPING = "shipping"
    TYPE_BILLING = "billing"

    TYPE_CHOICES = [
        (TYPE_SHIPPING, "Shipping"),
        (TYPE_BILLING, "Billing"),
    ]

    profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SHIPPING)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    company = models.CharField(max_length=120, blank=True)
    address_line_1 = models.CharField(max_length=180)
    address_line_2 = models.CharField(max_length=180, blank=True)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=80, default="Polska")
    phone = models.CharField(max_length=40, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "city", "address_line_1"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}, {self.city}"


class FavoriteProduct(models.Model):
    profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="favorite_products",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "product"],
                name="unique_favorite_product",
            ),
        ]

    def __str__(self):
        return f"{self.profile} -> {self.product}"
