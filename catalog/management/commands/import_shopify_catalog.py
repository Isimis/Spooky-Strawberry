import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size


SHOPIFY_PRODUCTS_URL = "https://www.spookystrawberry.pl/products.json?limit=250"
SHOPIFY_PRODUCT_BASE_URL = "https://www.spookystrawberry.pl/products/"

AESTHETIC_TAGS = {
    "dark coquette": ("Dark coquette", 10),
    "jirai kei": ("Jirai kei", 20),
    "goth": ("Goth", 30),
    "grunge": ("Grunge", 40),
    "y2k": ("Y2K", 50),
    "punk": ("Punk", 60),
    "lolita": ("Lolita", 70),
    "e-girl": ("E-girl", 80),
    "alt fashion": ("Alt fashion", 90),
}

CATEGORY_RULES = [
    ("Podkolanówki", ["podkolanówki"]),
    ("Pończochy", ["pończochy"]),
    ("Rajstopy", ["rajstopy", "kabaretki"]),
    ("Skarpetki", ["skarpetki"]),
    ("Mitenki", ["mitenki", "rękawiczki", "ocieplacze"]),
    ("Mankiety", ["mankiety"]),
    ("Chokery", ["choker", "naszyjnik", "obroża"]),
    ("Podwiązki", ["podwiązki", "harness"]),
    ("Spinki do włosów", ["spinki", "włosy", "kokardy"]),
]

COLOR_RULES = [
    ("Midnight Black", "#111111", ["midnight black", "czarne", "czerń", "black"]),
    ("Pure White", "#fffafc", ["pure white", "czysta biel"]),
    ("Porcelain White", "#f8f1ea", ["porcelain white", "niewinna biel", "białe", "biel"]),
    ("Blood Wine", "#7b1832", ["blood wine", "czerwone wino", "bordowe"]),
]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "li", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self):
        text = " ".join(self.parts)
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


class Command(BaseCommand):
    help = "Import the current public Shopify catalog into local Django models."

    def handle(self, *args, **options):
        payload = self.fetch_json(SHOPIFY_PRODUCTS_URL)
        products = payload.get("products", [])
        one_size = self.get_one_size()

        for index, item in enumerate(products):
            self.import_product(item, index, one_size)

        self.stdout.write(self.style.SUCCESS(f"Imported {len(products)} products from Shopify."))

    def fetch_json(self, url):
        request = Request(url, headers={"User-Agent": "SpookyStrawberryDjangoImporter/1.0"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_bytes(self, url):
        request = Request(url, headers={"User-Agent": "SpookyStrawberryDjangoImporter/1.0"})
        with urlopen(request, timeout=30) as response:
            return response.read()

    def import_product(self, item, index, one_size):
        tags = [tag.strip() for tag in item.get("tags", []) if tag.strip()]
        title = item["title"].strip()
        handle = item["handle"].strip()
        variants = item.get("variants", [])
        regular_price = Decimal(variants[0]["price"]) if variants else Decimal("0.00")
        body_text = html_to_text(item.get("body_html") or "")
        category = self.get_category(title, tags)

        product, _ = Product.objects.update_or_create(
            slug=handle,
            defaults={
                "name": title,
                "category": category,
                "description": make_description(body_text),
                "styling_tips": make_styling_tips(title, tags),
                "regular_price": regular_price,
                "sale_price": None,
                "is_featured": index < 4,
                "sort_order": index,
                "seo_title": title,
                "seo_description": make_seo_description(body_text),
                "status": Product.STATUS_ACTIVE if any(variant.get("available") for variant in variants) else Product.STATUS_DRAFT,
            },
        )
        product.aesthetics.set(self.get_aesthetics(tags))

        ProductVariant.objects.filter(product=product).delete()
        for variant_index, variant in enumerate(variants):
            color = self.get_variant_color(variant, title, tags)
            price = Decimal(variant["price"])
            ProductVariant.objects.create(
                product=product,
                color=color,
                size=one_size,
                sku=variant.get("sku") or None,
                price_override=price if price != regular_price else None,
                stock_quantity=25 if variant.get("available") else 0,
                is_active=bool(variant.get("available")),
                sort_order=variant_index,
            )

        self.import_images(product, item.get("images", []))

    def get_category(self, title, tags):
        search_text = " ".join([title, *tags]).lower()
        for name, keywords in CATEGORY_RULES:
            if any(keyword in search_text for keyword in keywords):
                return Category.objects.get_or_create(
                    name=name,
                    defaults={"slug": slugify(name), "is_active": True},
                )[0]
        return Category.objects.get_or_create(
            name="Akcesoria",
            defaults={"slug": "akcesoria", "is_active": True},
        )[0]

    def get_aesthetics(self, tags):
        found = []
        lower_tags = {tag.lower() for tag in tags}
        for tag, (name, sort_order) in AESTHETIC_TAGS.items():
            if tag in lower_tags:
                aesthetic = Aesthetic.objects.get_or_create(
                    name=name,
                    defaults={
                        "slug": slugify(name),
                        "sort_order": sort_order,
                        "is_active": True,
                    },
                )[0]
                found.append(aesthetic)
        return found

    def get_one_size(self):
        return Size.objects.get_or_create(
            name="One Size",
            defaults={"slug": "one-size", "sort_order": 10, "is_active": True},
        )[0]

    def get_variant_color(self, variant, title, tags):
        variant_text = " ".join(
            [
                str(variant.get("title") or ""),
                str(variant.get("option1") or ""),
            ]
        ).lower()

        for name, hex_code, keywords in COLOR_RULES:
            if any(keyword in variant_text for keyword in keywords):
                return Color.objects.get_or_create(
                    name=name,
                    defaults={
                        "slug": slugify(name),
                        "hex_code": hex_code,
                        "is_active": True,
                    },
                )[0]

        search_text = " ".join([title, *tags]).lower()
        for name, hex_code, keywords in COLOR_RULES:
            if any(keyword in search_text for keyword in keywords):
                return Color.objects.get_or_create(
                    name=name,
                    defaults={
                        "slug": slugify(name),
                        "hex_code": hex_code,
                        "is_active": True,
                    },
                )[0]

        if "skóra" in search_text or "goth" in search_text:
            return Color.objects.get_or_create(
                name="Midnight Black",
                defaults={"slug": "midnight-black", "hex_code": "#111111", "is_active": True},
            )[0]

        return None

    def import_images(self, product, images):
        product.images.all().delete()

        for index, image_data in enumerate(images):
            source = image_data.get("src")
            if not source:
                continue

            extension = Path(urlparse(source).path).suffix.lower() or ".jpg"
            field_name = f"{product.slug}/{index + 1:02d}{extension}"
            storage_name = f"products/{field_name}"
            if default_storage.exists(storage_name):
                default_storage.delete(storage_name)

            image = ProductImage(
                product=product,
                alt_text=product.name,
                sort_order=index,
                is_main=index == 0,
            )
            image.image.save(field_name, ContentFile(self.fetch_bytes(source)), save=True)


def html_to_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def make_seo_description(text):
    if not text:
        return ""
    first_sentence = re.split(r"(?<=[.!?])\s+", text)[0]
    return first_sentence[:255]


def make_description(text):
    if "Szczegóły produktu:" in text:
        return text.split("Szczegóły produktu:", 1)[0].strip()
    return text


def make_styling_tips(title, tags):
    selected_tags = [tag for tag in tags if tag.lower() in AESTHETIC_TAGS]
    if selected_tags:
        styles = ", ".join(selected_tags[:4])
        return f"Najlepiej gra w stylizacjach: {styles}. Łącz z warstwami, cięższymi butami albo delikatną koronką, zależnie od klimatu outfitu."
    return f"{title} pasuje do codziennych alt stylizacji i jako mocniejszy detal do prostszej bazy."
