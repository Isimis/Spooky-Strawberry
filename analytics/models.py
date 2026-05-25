from django.db import models


class AnalyticsSession(models.Model):
    session_key = models.CharField(max_length=80, unique=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    device_type = models.CharField(max_length=30, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self):
        return self.session_key


class AnalyticsEvent(models.Model):
    EVENT_PAGE_VIEW = "page_view"
    EVENT_PRODUCT_VIEW = "product_view"
    EVENT_SEARCH = "search"
    EVENT_FILTER_APPLIED = "filter_applied"
    EVENT_ADD_TO_CART = "add_to_cart"
    EVENT_CART_VIEW = "cart_view"

    EVENT_CHOICES = [
        (EVENT_PAGE_VIEW, "Page view"),
        (EVENT_PRODUCT_VIEW, "Product view"),
        (EVENT_SEARCH, "Search"),
        (EVENT_FILTER_APPLIED, "Filter applied"),
        (EVENT_ADD_TO_CART, "Add to cart"),
        (EVENT_CART_VIEW, "Cart view"),
    ]

    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    path = models.CharField(max_length=500)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        related_name="analytics_events",
        null=True,
        blank=True,
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        related_name="analytics_events",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"], name="analytics_event_type_idx"),
            models.Index(fields=["path"], name="analytics_event_path_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} {self.path}"
