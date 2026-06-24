from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Max, Min
from django.shortcuts import get_object_or_404, render

from analytics.services import track_event
from outfits.models import Outfit

from .models import Aesthetic, Category, Color, Product, Size


SORT_OPTIONS = {
    "featured": ("Polecane", ["sort_order", "-created_at"]),
    "newest": ("Najnowsze", ["-created_at"]),
    "price_asc": ("Cena rosnąco", ["regular_price", "name"]),
    "price_desc": ("Cena malejąco", ["-regular_price", "name"]),
    "name_asc": ("Alfabetycznie", ["name"]),
}

AVAILABILITY_OPTIONS = {
    "all": "Wszystkie",
    "in_stock": "W magazynie",
    "sold_out": "Wyprzedane",
}

PAGE_SIZE = 12


def product_list(request):
    selected_category = request.GET.get("category", "")
    selected_aesthetic = request.GET.get("aesthetic", "")
    selected_color = request.GET.get("color", "")
    selected_size = request.GET.get("size", "")
    selected_sort = request.GET.get("sort", "featured")
    availability = get_availability(request)
    min_price = parse_price(request.GET.get("min_price", ""))
    max_price = parse_price(request.GET.get("max_price", ""))

    products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE)
        .select_related("category")
        .prefetch_related("aesthetics", "images", "variants__color", "variants__size")
    )

    if selected_category:
        products = products.filter(category__slug=selected_category)
    if selected_aesthetic:
        products = products.filter(aesthetics__slug=selected_aesthetic)
    if selected_color:
        products = products.filter(variants__color__slug=selected_color)
    if selected_size:
        products = products.filter(variants__size__slug=selected_size)
    if availability == "in_stock":
        products = products.filter(variants__is_active=True, variants__stock_quantity__gt=0)
    elif availability == "sold_out":
        products = products.exclude(variants__is_active=True, variants__stock_quantity__gt=0)
    if min_price is not None:
        products = products.filter(regular_price__gte=min_price)
    if max_price is not None:
        products = products.filter(regular_price__lte=max_price)

    products = products.distinct().order_by(*SORT_OPTIONS.get(selected_sort, SORT_OPTIONS["featured"])[1])
    selected_filters = build_selected_filters(
        selected_category,
        selected_aesthetic,
        selected_color,
        selected_size,
        availability,
        min_price,
        max_price,
    )
    if selected_filters:
        track_event(
            request,
            "filter_applied",
            metadata={
                "category": selected_category,
                "aesthetic": selected_aesthetic,
                "color": selected_color,
                "size": selected_size,
                "availability": availability,
                "min_price": str(min_price or ""),
                "max_price": str(max_price or ""),
            },
        )

    paginator = Paginator(products, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    price_range = Product.objects.filter(status=Product.STATUS_ACTIVE).aggregate(
        min_price=Min("regular_price"),
        max_price=Max("regular_price"),
    )

    return render(
        request,
        "catalog/product_list.html",
        {
            "products": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "query_string": query_params.urlencode(),
            "product_count": paginator.count,
            "categories": Category.objects.filter(is_active=True).order_by("name"),
            "aesthetics": Aesthetic.objects.filter(is_active=True).order_by("sort_order", "name"),
            "colors": Color.objects.filter(is_active=True, variants__product__status=Product.STATUS_ACTIVE)
            .distinct()
            .order_by("name"),
            "sizes": Size.objects.filter(is_active=True, variants__product__status=Product.STATUS_ACTIVE)
            .distinct()
            .order_by("sort_order", "name"),
            "sort_options": SORT_OPTIONS,
            "availability_options": AVAILABILITY_OPTIONS,
            "selected_category": selected_category,
            "selected_aesthetic": selected_aesthetic,
            "selected_color": selected_color,
            "selected_size": selected_size,
            "selected_sort": selected_sort,
            "selected_sort_label": SORT_OPTIONS.get(selected_sort, SORT_OPTIONS["featured"])[0],
            "availability": availability,
            "min_price": request.GET.get("min_price", ""),
            "max_price": request.GET.get("max_price", ""),
            "price_range": price_range,
            "selected_filters": selected_filters,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "aesthetics",
            "images",
            "variants__color",
            "variants__size",
        ),
        slug=slug,
        status=Product.STATUS_ACTIVE,
    )
    selected_variant = get_selected_variant(product, request.GET.get("variant"))
    track_event(request, "product_view", product=product, variant=selected_variant)

    related_products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, category=product.category)
        .exclude(pk=product.pk)
        .prefetch_related("images", "aesthetics", "variants__color", "variants__size")
        .order_by("sort_order", "-created_at")[:4]
    )
    related_outfits = (
        Outfit.objects.filter(status=Outfit.STATUS_ACTIVE, products=product)
        .prefetch_related("images", "items__product")
        .order_by("sort_order", "-created_at")[:3]
    )

    color_options, size_options = build_variant_matrix(product, selected_variant)

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "selected_variant": selected_variant,
            "color_options": color_options,
            "size_options": size_options,
            "related_products": related_products,
            "related_outfits": related_outfits,
        },
    )


def build_variant_matrix(product, selected_variant):
    """Buduje listy opcji koloru i rozmiaru z docelowym wariantem dla każdej opcji."""
    variants = [v for v in product.variants.all() if v.is_active]
    selected_color_id = selected_variant.color_id if selected_variant else None
    selected_size_id = selected_variant.size_id if selected_variant else None

    color_options = []
    seen_colors = []
    for variant in variants:
        if variant.color and variant.color_id not in seen_colors:
            seen_colors.append(variant.color_id)
            # wariant tego koloru pasujący do wybranego rozmiaru, jeśli istnieje
            target = next(
                (v for v in variants if v.color_id == variant.color_id and v.size_id == selected_size_id),
                variant,
            )
            color_options.append(
                {
                    "color": variant.color,
                    "variant_id": target.id,
                    "selected": variant.color_id == selected_color_id,
                }
            )

    size_options = []
    seen_sizes = []
    for variant in variants:
        if variant.size and variant.size_id not in seen_sizes:
            seen_sizes.append(variant.size_id)
            match = next(
                (v for v in variants if v.size_id == variant.size_id and v.color_id == selected_color_id),
                None,
            )
            available = bool(match and match.is_in_stock)
            size_options.append(
                {
                    "size": variant.size,
                    "variant_id": match.id if match else None,
                    "selected": variant.size_id == selected_size_id,
                    "available": available,
                }
            )

    return color_options, size_options


def aesthetic_list(request):
    # Kolejność wg sort_order, by mozaika układała się jak w projekcie — wyróżnione
    # (is_featured = kafle „tall") rozkładają się w rytmie, a nie zbijają na początku.
    aesthetics = Aesthetic.objects.filter(is_active=True).order_by("sort_order", "name")
    return render(request, "catalog/aesthetic_list.html", {"aesthetics": aesthetics})


# Klucz odpowiedzi quizu -> (slug estetyki w bazie, nazwa wyniku, opis, gradient)
QUIZ_RESULTS = [
    ("soft", "goth", "Soft Goth", "Mrok, ale delikatny — koronki, krzyże i czerń przełamana różem.", "#2a1622,#7a3d5a"),
    ("coquette", "dark-coquette", "Dark Coquette", "Kokardy, koronki i romantyczny pazur. Słodko, ale z charakterem.", "#3a1d2c,#b4456f"),
    ("jirai", "jirai-kei", "Jirai Kei", "Słodko-gorzko i lalkowato. Pastel z mrocznym twistem.", "#2a1622,#d45d8a"),
    ("grunge", "grunge", "Grunge", "Surowo, buntowniczo i bez udawania. Podarte, czarne, szczere.", "#1c1018,#4a2236"),
    ("y2k", "y2k", "Y2K / Emo", "Nostalgia lat 2000, neony i emo-nuta. Trochę chaosu, dużo serca.", "#241a2e,#6e3b6a"),
    ("witchy", "goth", "Witchy", "Magia codzienna — świece, srebro i intuicja. Mroczna elegancja.", "#1a1322,#5e2b40"),
]


def style_quiz(request):
    """Interaktywny quiz stylu — dopasowuje estetykę z bazy i jej produkty."""
    from django.template.loader import render_to_string
    from django.urls import reverse

    fallback_url = reverse("catalog:aesthetic_list")

    def render_cards(products):
        return "".join(
            render_to_string("catalog/includes/product_card.html", {"product": p}, request=request)
            for p in products
        )

    bestsellers = list(
        Product.objects.filter(status=Product.STATUS_ACTIVE)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("-is_bestseller", "sort_order", "-created_at")[:3]
    )

    quiz_results = {}
    for key, slug, name, desc, gradient in QUIZ_RESULTS:
        aesthetic = Aesthetic.objects.filter(slug=slug, is_active=True).first()
        products = []
        if aesthetic is not None:
            products = list(
                Product.objects.filter(status=Product.STATUS_ACTIVE, aesthetics=aesthetic)
                .prefetch_related("images", "aesthetics", "variants__color")
                .order_by("sort_order", "-created_at")[:3]
            )
        if not products:
            products = bestsellers
        quiz_results[key] = {
            "name": name,
            "desc": desc,
            "gradient": gradient,
            "url": aesthetic.get_absolute_url() if aesthetic is not None else fallback_url,
            "cards": render_cards(products),
        }

    return render(request, "catalog/style_quiz.html", {"quiz_results": quiz_results})


def aesthetic_detail(request, slug):
    aesthetic = get_object_or_404(Aesthetic, slug=slug, is_active=True)
    products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, aesthetics=aesthetic)
        .prefetch_related("images", "aesthetics", "variants__color", "variants__size")
        .order_by("sort_order", "-created_at")[:8]
    )
    outfits = (
        Outfit.objects.filter(status=Outfit.STATUS_ACTIVE, aesthetics=aesthetic)
        .prefetch_related("images", "aesthetics", "items")
        .order_by("-is_featured", "sort_order", "-created_at")[:5]
    )
    from blog.models import Article

    articles = (
        Article.objects.filter(status=Article.STATUS_PUBLISHED, aesthetics=aesthetic)
        .select_related("category")
        .order_by("-published_at", "-created_at")[:3]
    )
    return render(
        request,
        "catalog/aesthetic_detail.html",
        {
            "aesthetic": aesthetic,
            "products": products,
            "outfits": outfits,
            "articles": articles,
            "product_count": Product.objects.filter(status=Product.STATUS_ACTIVE, aesthetics=aesthetic).count(),
        },
    )


def get_availability(request):
    if request.GET.get("in_stock") == "1":
        return "in_stock"
    availability = request.GET.get("availability", "all")
    if availability not in AVAILABILITY_OPTIONS:
        return "all"
    return availability


def parse_price(value):
    if not value:
        return None
    try:
        price = Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if price < 0:
        return None
    return price


def get_selected_variant(product, variant_id):
    variants = list(product.variants.all())
    if variant_id:
        for variant in variants:
            if str(variant.pk) == str(variant_id):
                return variant
    return product.default_variant


def build_selected_filters(category_slug, aesthetic_slug, color_slug, size_slug, availability, min_price, max_price):
    filters = []
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category:
            filters.append(category.name)
    if aesthetic_slug:
        aesthetic = Aesthetic.objects.filter(slug=aesthetic_slug).first()
        if aesthetic:
            filters.append(aesthetic.name)
    if color_slug:
        color = Color.objects.filter(slug=color_slug).first()
        if color:
            filters.append(color.name)
    if size_slug:
        size = Size.objects.filter(slug=size_slug).first()
        if size:
            filters.append(size.name)
    if availability != "all":
        filters.append(AVAILABILITY_OPTIONS[availability])
    if min_price is not None:
        filters.append(f"Od {min_price} zł")
    if max_price is not None:
        filters.append(f"Do {max_price} zł")
    return filters
