from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Product
from outfits.models import Outfit, OutfitImage, OutfitItem


OUTFIT_DEFINITIONS = [
    {
        "name": "Dark Coquette Starter Pack",
        "aesthetics": ["Dark coquette", "Jirai kei"],
        "keywords": ["choker", "podwiązki", "mankiety", "skarpetki"],
        "description": "Delikatny mrok, koronka i małe detale, które robią cały outfit.",
    },
    {
        "name": "Grunge Core Layers",
        "aesthetics": ["Grunge", "Y2K", "Punk"],
        "keywords": ["rajstopy", "mitenki", "kabaretki"],
        "description": "Warstwowa baza pod cięższe buty, paski i swetry oversize.",
    },
    {
        "name": "Jirai Kei Soft Details",
        "aesthetics": ["Jirai kei", "Dark coquette", "Lolita"],
        "keywords": ["spinki", "skarpetki", "podkolanówki", "mankiety"],
        "description": "Cute, romantycznie i lekko dramatycznie, ale nadal do noszenia na co dzień.",
    },
]

ARTICLE_DEFINITIONS = [
    {
        "title": "Jak zacząć styl dark coquette dodatkami",
        "category": "Stylizacje",
        "aesthetics": ["Dark coquette"],
        "query": ["choker", "podwiązki", "koronka", "skarpetki"],
        "intro": "Dark coquette nie musi zaczynać się od całej szafy. Czasem wystarczy kilka dodatków.",
    },
    {
        "title": "Rajstopy i kabaretki w alt stylizacjach",
        "category": "Poradniki produktowe",
        "aesthetics": ["Grunge", "Y2K", "Goth"],
        "query": ["rajstopy", "kabaretki", "podarte"],
        "intro": "Rajstopy potrafią zmienić prosty outfit w pełną stylizację.",
    },
    {
        "title": "Jirai kei: małe detale, które robią klimat",
        "category": "Estetyki",
        "aesthetics": ["Jirai kei", "Lolita"],
        "query": ["spinki", "mankiety", "podkolanówki", "falbanka"],
        "intro": "W jirai kei liczą się kokardy, koronka, kontrast i trochę teatralnego nastroju.",
    },
]


class Command(BaseCommand):
    help = "Create starter outfits and SEO articles based on imported catalog products."

    def handle(self, *args, **options):
        products = list(
            Product.objects.filter(status=Product.STATUS_ACTIVE)
            .prefetch_related("images", "aesthetics", "variants")
            .order_by("sort_order", "-created_at")
        )
        if not products:
            self.stdout.write(self.style.WARNING("No active products found. Import catalog first."))
            return

        outfits_created = self.create_outfits(products)
        articles_created = self.create_articles(products)
        self.stdout.write(
            self.style.SUCCESS(
                f"Starter content ready. Outfits touched: {outfits_created}. Articles touched: {articles_created}."
            )
        )

    def create_outfits(self, products):
        touched = 0
        for index, definition in enumerate(OUTFIT_DEFINITIONS):
            selected_products = select_products(products, definition["keywords"], limit=4)
            if not selected_products:
                continue

            outfit, _ = Outfit.objects.update_or_create(
                slug=slugify(definition["name"]),
                defaults={
                    "name": definition["name"],
                    "short_description": definition["description"],
                    "mood_description": definition["description"],
                    "styling_tips": "Połącz produkty z prostą bazą i mocniejszymi butami albo delikatną koronką.",
                    "bundle_price": calculate_bundle_price(selected_products),
                    "status": Outfit.STATUS_ACTIVE,
                    "is_featured": index == 0,
                    "sort_order": index,
                    "seo_title": definition["name"],
                    "seo_description": definition["description"],
                },
            )
            outfit.aesthetics.set(get_aesthetics(definition["aesthetics"]))
            OutfitItem.objects.filter(outfit=outfit).delete()
            for item_index, product in enumerate(selected_products):
                OutfitItem.objects.create(
                    outfit=outfit,
                    product=product,
                    variant=product.default_variant,
                    quantity=1,
                    sort_order=item_index,
                )
            sync_outfit_main_image(outfit, selected_products[0])
            touched += 1
        return touched

    def create_articles(self, products):
        touched = 0
        for index, definition in enumerate(ARTICLE_DEFINITIONS):
            category, _ = BlogCategory.objects.get_or_create(
                name=definition["category"],
                defaults={"slug": slugify(definition["category"]), "sort_order": index},
            )
            selected_products = select_products(products, definition["query"], limit=4)
            article, _ = Article.objects.update_or_create(
                slug=slugify(definition["title"]),
                defaults={
                    "title": definition["title"],
                    "category": category,
                    "intro": definition["intro"],
                    "body": build_article_body(definition["intro"], selected_products),
                    "status": Article.STATUS_PUBLISHED,
                    "is_featured": index == 0,
                    "seo_title": definition["title"],
                    "seo_description": definition["intro"],
                },
            )
            article.aesthetics.set(get_aesthetics(definition["aesthetics"]))
            article.products.set(selected_products)
            touched += 1
        return touched


def select_products(products, keywords, limit):
    selected = []
    for product in products:
        search = " ".join(
            [
                product.name,
                product.short_description,
                product.mood_description,
                product.category.name,
                " ".join(aesthetic.name for aesthetic in product.aesthetics.all()),
            ]
        ).lower()
        if any(keyword.lower() in search for keyword in keywords):
            selected.append(product)
        if len(selected) == limit:
            return selected
    return selected or products[:limit]


def get_aesthetics(names):
    return list(Aesthetic.objects.filter(name__in=names))


def calculate_bundle_price(products):
    total = sum((product.base_price for product in products), Decimal("0.00"))
    if total <= 0:
        return None
    return (total * Decimal("0.90")).quantize(Decimal("0.01"))


def sync_outfit_main_image(outfit, product):
    image = product.main_image
    if not image:
        return
    OutfitImage.objects.update_or_create(
        outfit=outfit,
        is_main=True,
        defaults={
            "image": image.image.name,
            "alt_text": outfit.name,
            "caption": f"Inspiracja z produktu: {product.name}",
            "sort_order": 0,
        },
    )


def build_article_body(intro, products):
    product_lines = "\n".join(f"- {product.name}" for product in products)
    return (
        f"{intro}\n\n"
        "To roboczy szkic poradnika SEO. Później dopiszemy tu pełną treść, przykłady stylizacji, "
        "linkowanie wewnętrzne i konkretne porady zakupowe.\n\n"
        "Produkty powiązane z tematem:\n"
        f"{product_lines}"
    )
