from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.text import normalize_dashes


def unique_slug_for(instance, value):
    base_slug = slugify(value) or "item"
    slug = base_slug
    counter = 2
    model = instance.__class__

    queryset = model.objects.filter(slug=slug)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        queryset = model.objects.filter(slug=slug)
        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        counter += 1

    return slug


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        self.name = normalize_dashes(self.name)
        self.description = normalize_dashes(self.description)
        if not self.slug:
            self.slug = unique_slug_for(self, self.name)
        super().save(*args, **kwargs)


class Aesthetic(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tagline = models.CharField(
        max_length=160,
        blank=True,
        help_text="Krótki podtytuł na kafelku estetyki, np. „Mrok, ale delikatny”.",
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="aesthetics/", blank=True)
    featured_image = models.ImageField(
        upload_to="aesthetics/",
        blank=True,
        help_text="Zdjęcie używane tylko, gdy kafelek jest wyróżniony (duży) w mozaice.",
    )
    card_gradient = models.CharField(
        max_length=80,
        blank=True,
        help_text="Opcjonalny gradient tła kafelka, np. „#2a1622,#7a3d5a”.",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Większy kafelek w mozaice estetyk.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Aesthetic"
        verbose_name_plural = "Aesthetics"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:aesthetic_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        self.name = normalize_dashes(self.name)
        self.tagline = normalize_dashes(self.tagline)
        self.description = normalize_dashes(self.description)
        if not self.slug:
            self.slug = unique_slug_for(self, self.name)
        super().save(*args, **kwargs)


class Color(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    hex_code = models.CharField(max_length=7, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colors"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = normalize_dashes(self.name)
        self.description = normalize_dashes(self.description)
        self.styling_tips = normalize_dashes(self.styling_tips)
        self.seo_title = normalize_dashes(self.seo_title)
        self.seo_description = normalize_dashes(self.seo_description)
        if not self.slug:
            self.slug = unique_slug_for(self, self.name)
        super().save(*args, **kwargs)


class Size(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Size"
        verbose_name_plural = "Sizes"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug_for(self, self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Szkic"),
        (STATUS_ACTIVE, "Aktywny"),
        (STATUS_ARCHIVED, "Archiwalny"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    aesthetics = models.ManyToManyField(
        Aesthetic,
        related_name="products",
        blank=True,
    )

    description = models.TextField(blank=True)
    styling_tips = models.TextField(blank=True)

    regular_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    disable_low_stock_badge = models.BooleanField(
        default=False,
        help_text="Zaznacz, aby NIE pokazywać oznaczenia „ostatnie sztuki” dla tego produktu.",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=3,
        help_text="Etykieta „ostatnie sztuki” pojawia się, gdy łączny stan spadnie do tej liczby lub niżej.",
    )
    sort_order = models.PositiveIntegerField(default=0)

    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="cat_product_status_idx"),
            models.Index(fields=["is_featured"], name="cat_product_featured_idx"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug_for(self, self.name)
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        if self.status != self.STATUS_ACTIVE:
            return False
        return self.variants.filter(is_active=True, stock_quantity__gt=0).exists()

    @property
    def main_image(self):
        images = list(self.images.all())
        for image in images:
            if image.is_main:
                return image
        return images[0] if images else None

    @property
    def default_variant(self):
        variants = list(self.variants.all())
        for variant in variants:
            if variant.is_in_stock:
                return variant
        for variant in variants:
            if variant.is_active:
                return variant
        return variants[0] if variants else None

    @property
    def has_sale_price(self):
        return self.sale_price is not None and self.sale_price < self.regular_price

    @property
    def current_price(self):
        if self.has_sale_price:
            return self.sale_price
        return self.regular_price

    @property
    def total_stock(self):
        """Łączny stan magazynowy z aktywnych wariantów (korzysta z prefetcha)."""
        return sum(v.stock_quantity for v in self.variants.all() if v.is_active)

    @property
    def is_low_stock(self):
        """Czy produkt powinien dostać oznaczenie „ostatnie sztuki” (na bazie własnego progu)."""
        if self.disable_low_stock_badge:
            return False
        stock = self.total_stock
        return 0 < stock <= (self.low_stock_threshold or 0)


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
        related_name="variants",
        null=True,
        blank=True,
    )
    size = models.ForeignKey(
        Size,
        on_delete=models.PROTECT,
        related_name="variants",
        null=True,
        blank=True,
    )
    sku = models.CharField(max_length=80, unique=True, null=True, blank=True)
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["product__name", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "color", "size"],
                condition=models.Q(color__isnull=False, size__isnull=False),
                name="uniq_variant_color_size",
            ),
            models.UniqueConstraint(
                fields=["product", "color"],
                condition=models.Q(color__isnull=False, size__isnull=True),
                name="uniq_variant_color_only",
            ),
            models.UniqueConstraint(
                fields=["product", "size"],
                condition=models.Q(color__isnull=True, size__isnull=False),
                name="uniq_variant_size_only",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(color__isnull=True, size__isnull=True),
                name="uniq_variant_default",
            ),
        ]

    def __str__(self):
        parts = [self.product.name]
        if self.color:
            parts.append(self.color.name)
        if self.size:
            parts.append(self.size.name)
        return " / ".join(parts)

    @property
    def price(self):
        return self.price_override or self.product.current_price

    @property
    def is_in_stock(self):
        return self.is_active and self.stock_quantity > 0


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="images",
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=180, blank=True)
    caption = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_main = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_main=True),
                name="unique_main_image_per_product",
            ),
        ]

    def __str__(self):
        return f"Image for {self.product.name}"

    def clean(self):
        if self.variant and self.variant.product_id != self.product_id:
            raise ValidationError("Variant must belong to the selected product.")
