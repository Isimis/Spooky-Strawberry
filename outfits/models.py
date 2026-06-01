from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Outfit(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    mood_description = models.TextField(blank=True)
    styling_tips = models.TextField(blank=True)
    aesthetics = models.ManyToManyField("catalog.Aesthetic", related_name="outfits", blank=True)
    products = models.ManyToManyField(
        "catalog.Product",
        through="OutfitItem",
        related_name="outfits",
        blank=True,
    )
    bundle_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        indexes = [
            models.Index(fields=["status", "is_featured"], name="outfit_status_featured_idx"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("outfits:detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def products_total(self):
        total = 0
        for item in self.items.select_related("product", "variant"):
            total += item.unit_price * item.quantity
        return total


class OutfitItem(models.Model):
    outfit = models.ForeignKey(
        Outfit,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="outfit_items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="outfit_items",
        null=True,
        blank=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["outfit", "product", "variant"],
                condition=models.Q(variant__isnull=False),
                name="unique_outfit_product_variant",
            ),
            models.UniqueConstraint(
                fields=["outfit", "product"],
                condition=models.Q(variant__isnull=True),
                name="unique_outfit_product_default",
            ),
        ]

    def __str__(self):
        return f"{self.outfit} / {self.product}"

    @property
    def unit_price(self):
        if self.variant:
            return self.variant.price
        return self.product.current_price


class OutfitImage(models.Model):
    outfit = models.ForeignKey(
        Outfit,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="outfits/")
    alt_text = models.CharField(max_length=180, blank=True)
    caption = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_main = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["outfit"],
                condition=models.Q(is_main=True),
                name="unique_main_image_per_outfit",
            ),
        ]

    def __str__(self):
        return f"Image for {self.outfit.name}"
