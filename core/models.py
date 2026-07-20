from django.db import models
from django.utils.text import slugify

from .storage import PrivateMessageAttachmentStorage
from .text import normalize_dashes


class SiteSettings(models.Model):
    """Pojedynczy rekord z globalnymi ustawieniami treści sterowanymi z panelu."""

    # Pasek zapowiedzi nad nagłówkiem
    announcement_is_active = models.BooleanField(default=True)
    announcement_text = models.CharField(
        max_length=255,
        default="Darmowa dostawa od 100 zł 🍓",
        blank=True,
    )

    # Globalne zachowanie oznaczania "ostatnie sztuki"
    low_stock_default_enabled = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(default=3)

    # Tryb płatności. True = Sandbox (płatności testowe, stany magazynowe NIE są ruszane).
    # False = "Prawdziwe płatności" - dopóki nie są gotowe, w procesie zakupowym pokazujemy
    # dymek "wersja testowa / wkrótce" i nie finalizujemy zakupu.
    payments_sandbox = models.BooleanField(default=True)

    # Sekcja "Nowości" na stronie głównej
    drop_is_active = models.BooleanField(default=True)
    drop_eyebrow = models.CharField(max_length=120, blank=True, default="Nowości")
    drop_heading = models.CharField(max_length=180, blank=True, default="Nowości")
    drop_date = models.DateTimeField(null=True, blank=True)
    drop_products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="drop_settings",
    )

    # Produkt prezentowany w głównej grafice na stronie startowej.
    hero_product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        related_name="hero_settings",
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ustawienia strony"
        verbose_name_plural = "Ustawienia strony"

    def __str__(self):
        return "Ustawienia strony"

    def save(self, *args, **kwargs):
        self.announcement_text = normalize_dashes(self.announcement_text)
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
        self.title = normalize_dashes(self.title)
        self.intro = normalize_dashes(self.intro)
        self.body = normalize_dashes(self.body)
        self.seo_title = normalize_dashes(self.seo_title)
        self.seo_description = normalize_dashes(self.seo_description)
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


class MessageTemplate(models.Model):
    """Szablon wiadomości HTML. Systemowe szablony to maile wysyłane automatycznie."""

    name = models.CharField(max_length=160)
    subject = models.CharField(max_length=200, blank=True)
    body_html = models.TextField(blank=True, help_text="Treść HTML wiadomości.")
    description = models.CharField(max_length=255, blank=True, help_text="Kiedy ten mail jest wysyłany.")
    system_key = models.SlugField(max_length=80, blank=True, unique=True, null=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_system", "name"]

    def save(self, *args, **kwargs):
        self.name = normalize_dashes(self.name)
        self.subject = normalize_dashes(self.subject)
        self.body_html = normalize_dashes(self.body_html)
        self.description = normalize_dashes(self.description)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Message(models.Model):
    """Wiadomość w hubie komunikacji (przychodząca/wychodząca)."""

    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"
    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Przychodząca"),
        (DIRECTION_OUTBOUND, "Wychodząca"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_RECEIVED = "received"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Szkic"),
        (STATUS_SENT, "Wysłana"),
        (STATUS_RECEIVED, "Odebrana"),
    ]

    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default=DIRECTION_OUTBOUND)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    subject = models.CharField(max_length=200, blank=True)
    body_html = models.TextField(blank=True)
    from_email = models.EmailField(blank=True)
    to_email = models.EmailField(blank=True)
    external_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        related_name="messages",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["direction", "created_at"], name="message_dir_created_idx"),
            models.Index(fields=["direction", "read_at"], name="message_dir_read_idx"),
        ]

    def __str__(self):
        return self.subject or f"Wiadomość #{self.pk}"


class MessageAttachment(models.Model):
    """Plik dołączony do wiadomości zsynchronizowanej lub wysłanej z panelu."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(storage=PrivateMessageAttachmentStorage(), upload_to="message_attachments/%Y/%m/%d/")
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["message", "checksum"], name="message_attachment_checksum_unique"),
        ]

    def __str__(self):
        return self.filename
