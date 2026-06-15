from django.db import models
from django.utils.text import slugify


class SiteSettings(models.Model):
    """Pojedynczy rekord z globalnymi ustawieniami treści sterowanymi z panelu."""

    # Pasek zapowiedzi nad nagłówkiem
    announcement_is_active = models.BooleanField(default=True)
    announcement_text = models.CharField(
        max_length=255,
        default="🦇 Darmowa dostawa od 50 zł · 30 dni na zwrot",
        blank=True,
    )

    # Globalne zachowanie oznaczania "ostatnie sztuki"
    low_stock_default_enabled = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(default=3)

    # Sekcja "Najnowszy drop" na stronie głównej
    drop_is_active = models.BooleanField(default=True)
    drop_eyebrow = models.CharField(max_length=120, blank=True, default="Najnowszy drop")
    drop_heading = models.CharField(max_length=180, blank=True, default="Najnowszy drop")
    drop_date = models.DateTimeField(null=True, blank=True)
    drop_products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="drop_settings",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ustawienia strony"
        verbose_name_plural = "Ustawienia strony"

    def __str__(self):
        return "Ustawienia strony"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SitePage(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    intro = models.TextField(blank=True)
    body = models.TextField(blank=True)
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class HomepageSection(models.Model):
    TYPE_HERO = "hero"
    TYPE_PRODUCTS = "products"
    TYPE_OUTFITS = "outfits"
    TYPE_AESTHETICS = "aesthetics"
    TYPE_GUIDES = "guides"
    TYPE_NEWSLETTER = "newsletter"
    TYPE_CUSTOM = "custom"

    TYPE_CHOICES = [
        (TYPE_HERO, "Hero"),
        (TYPE_PRODUCTS, "Products"),
        (TYPE_OUTFITS, "Outfits"),
        (TYPE_AESTHETICS, "Aesthetics"),
        (TYPE_GUIDES, "Guides"),
        (TYPE_NEWSLETTER, "Newsletter"),
        (TYPE_CUSTOM, "Custom"),
    ]

    name = models.CharField(max_length=120)
    section_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_CUSTOM)
    eyebrow = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=180, blank=True)
    body = models.TextField(blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="homepage_sections")
    aesthetics = models.ManyToManyField("catalog.Aesthetic", blank=True, related_name="homepage_sections")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class NewsletterSubscriber(models.Model):
    SOURCE_FOOTER = "footer"
    SOURCE_HOME = "home"
    SOURCE_POPUP = "popup"
    SOURCE_OTHER = "other"

    SOURCE_CHOICES = [
        (SOURCE_FOOTER, "Footer"),
        (SOURCE_HOME, "Home"),
        (SOURCE_POPUP, "Popup"),
        (SOURCE_OTHER, "Other"),
    ]

    email = models.EmailField(unique=True)
    source = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_FOOTER)
    is_active = models.BooleanField(default=True)
    consent_text = models.TextField(blank=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email
