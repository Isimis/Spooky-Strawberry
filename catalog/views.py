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
    "price_asc": ("Cena rosnąco", ["base_price", "name"]),
    "price_desc": ("Cena malejąco", ["-base_price", "name"]),
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
        products = products.filter(base_price__gte=min_price)
    if max_price is not None:
        products = products.filter(base_price__lte=max_price)

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
        min_price=Min("base_price"),
        max_price=Max("base_price"),
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

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "selected_variant": selected_variant,
            "related_products": related_products,
            "related_outfits": related_outfits,
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
