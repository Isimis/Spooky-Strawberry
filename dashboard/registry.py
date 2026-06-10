from dataclasses import dataclass

from analytics.models import AnalyticsEvent, AnalyticsSession
from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, Size
from core.models import NewsletterSubscriber
from orders.models import DiscountCode, Order, OrderItem, ShippingMethod
from outfits.models import Outfit


@dataclass(frozen=True)
class AdminModelConfig:
    slug: str
    label: str
    model: object
    section: str
    list_fields: tuple[str, ...]
    search_fields: tuple[str, ...] = ()
    readonly: bool = False


MODEL_REGISTRY = [
    AdminModelConfig(
        "products",
        "Produkty",
        Product,
        "Katalog",
        ("name", "category", "regular_price", "sale_price", "status", "is_featured"),
        ("name", "description"),
    ),
    AdminModelConfig("categories", "Kategorie", Category, "Katalog", ("name", "parent", "is_active"), ("name", "description")),
    AdminModelConfig("aesthetics", "Estetyki", Aesthetic, "Katalog", ("name", "is_active", "sort_order"), ("name", "description")),
    AdminModelConfig("colors", "Kolory", Color, "Katalog", ("name", "hex_code", "is_active"), ("name", "hex_code")),
    AdminModelConfig("sizes", "Rozmiary", Size, "Katalog", ("name", "sort_order", "is_active"), ("name",)),
    AdminModelConfig(
        "outfits",
        "Gotowe kreacje",
        Outfit,
        "Kreacje",
        ("name", "status", "is_featured", "bundle_price", "sort_order"),
        ("name", "short_description", "mood_description"),
    ),
    AdminModelConfig(
        "articles",
        "Poradniki",
        Article,
        "Poradniki SEO",
        ("title", "category", "status", "is_featured", "published_at"),
        ("title", "intro", "body"),
    ),
    AdminModelConfig(
        "blog-categories",
        "Kategorie poradników",
        BlogCategory,
        "Poradniki SEO",
        ("name", "is_active", "sort_order"),
        ("name", "description"),
    ),
    AdminModelConfig(
        "newsletter-subscribers",
        "Newsletter",
        NewsletterSubscriber,
        "Marketing",
        ("email", "source", "is_active", "subscribed_at"),
        ("email",),
    ),
    AdminModelConfig(
        "orders",
        "Zamówienia",
        Order,
        "Zamówienia",
        ("order_number", "email", "status", "grand_total", "created_at"),
        ("order_number", "email", "first_name", "last_name"),
    ),
    AdminModelConfig(
        "order-items",
        "Pozycje zamówień",
        OrderItem,
        "Zamówienia",
        ("order", "product_name", "variant_name", "quantity", "line_total"),
        ("product_name", "variant_name", "sku"),
    ),
    AdminModelConfig(
        "shipping-methods",
        "Metody dostawy",
        ShippingMethod,
        "Zamówienia",
        ("name", "code", "price", "free_from_amount", "is_active"),
        ("name", "code"),
    ),
    AdminModelConfig(
        "discount-codes",
        "Kody rabatowe",
        DiscountCode,
        "Zamówienia",
        ("code", "discount_type", "value", "is_active", "used_count"),
        ("code",),
    ),
    AdminModelConfig(
        "analytics-sessions",
        "Sesje analityczne",
        AnalyticsSession,
        "Analityka",
        ("session_key", "device_type", "referrer", "last_seen_at"),
        ("session_key", "visitor_id", "referrer", "utm_source", "utm_campaign"),
        readonly=True,
    ),
    AdminModelConfig(
        "analytics-events",
        "Zdarzenia analityczne",
        AnalyticsEvent,
        "Analityka",
        ("event_type", "path", "product", "variant", "created_at"),
        ("event_type", "path", "session__session_key", "product__name"),
        readonly=True,
    ),
]

REGISTRY_BY_SLUG = {config.slug: config for config in MODEL_REGISTRY}


def get_model_config(slug):
    return REGISTRY_BY_SLUG.get(slug)


def get_sections():
    sections = {}
    for config in MODEL_REGISTRY:
        sections.setdefault(config.section, []).append(config)
    return sections
