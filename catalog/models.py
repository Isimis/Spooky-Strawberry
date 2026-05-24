from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StyleTag(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        verbose_name = "Style tag"
        verbose_name_plural = "Style tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100, unique=True)
    hex_code = models.CharField(max_length=7, blank=True)

    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Size(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        verbose_name = "Size"
        verbose_name_plural = "Sizes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
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
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    style_tags = models.ManyToManyField(
        StyleTag,
        related_name="products",
        blank=True,
    )

    short_description = models.CharField(max_length=255, blank=True)
    mood_description = models.TextField(blank=True)
    details = models.TextField(blank=True)
    styling_tips = models.TextField(blank=True)

    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_featured = models.BooleanField(default=False)
    is_new_drop = models.BooleanField(default=False)

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
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


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
    sku = models.CharField(max_length=80, unique=True, blank=True)
    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__name"]

    def __str__(self):
        parts = [self.product.name]
        if self.color:
            parts.append(self.color.name)
        if self.size:
            parts.append(self.size.name)
        return " / ".join(parts)

    @property
    def price(self):
        return self.price_override or self.product.base_price


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
    sort_order = models.PositiveIntegerField(default=0)
    is_main = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"