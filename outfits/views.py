from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from catalog.models import Aesthetic, Product
from core.seo import breadcrumb_schema, collection_page_schema, organization_schema, plain_text, title_with_store_name
from .models import Outfit


def outfit_list(request):
    selected_aesthetic = request.GET.get("aesthetic", "")
    outfits = (
        Outfit.objects.filter(status=Outfit.STATUS_ACTIVE)
        .prefetch_related("aesthetics", "images", "items__product__images")
        .order_by("-is_featured", "sort_order", "-created_at")
    )
    if selected_aesthetic:
        outfits = outfits.filter(aesthetics__slug=selected_aesthetic)

    aesthetics = (
        Aesthetic.objects.filter(is_active=True, outfits__status=Outfit.STATUS_ACTIVE)
        .distinct()
        .order_by("sort_order", "name")
    )
    return render(
        request,
        "outfits/list.html",
        {
            "outfits": outfits,
            "aesthetics": aesthetics,
            "selected_aesthetic": selected_aesthetic,
            "seo_title": "Stylizacje alternatywne, gotowe looki | Spooky Strawberry",
            "seo_description": "Zobacz gotowe stylizacje alternatywne i odkryj produkty, z których możesz zbudować swój własny look.",
            "seo_structured_data": [
                organization_schema(request),
                collection_page_schema(request, "Stylizacje Spooky Strawberry", reverse("outfits:list")),
            ],
        },
    )


def outfit_detail(request, slug):
    outfit = get_object_or_404(
        Outfit.objects.prefetch_related(
            "aesthetics",
            "images",
            "items__product__images",
            "items__variant__color",
            "items__variant__size",
            "hotspots__product__images",
            "hotspots__product__category",
        ),
        slug=slug,
        status=Outfit.STATUS_ACTIVE,
    )
    related_outfits = (
        Outfit.objects.filter(status=Outfit.STATUS_ACTIVE, aesthetics__in=outfit.aesthetics.all())
        .exclude(pk=outfit.pk)
        .prefetch_related("images", "aesthetics", "items")
        .distinct()
        .order_by("sort_order", "-created_at")[:4]
    )
    item_product_ids = list(outfit.items.values_list("product_id", flat=True))
    similar_products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, aesthetics__in=outfit.aesthetics.all())
        .exclude(pk__in=item_product_ids)
        .prefetch_related("images", "aesthetics", "variants__color")
        .distinct()
        .order_by("sort_order", "-created_at")[:4]
    )
    return render(
        request,
        "outfits/detail.html",
        {
            "outfit": outfit,
            "related_outfits": related_outfits,
            "similar_products": similar_products,
            "seo_title": title_with_store_name(outfit.seo_title or outfit.name),
            "seo_description": plain_text(outfit.seo_description or outfit.short_description or outfit.mood_description),
            "seo_image_url": outfit.main_image and outfit.main_image.image.url,
            "seo_structured_data": [
                organization_schema(request),
                collection_page_schema(request, outfit.name, outfit.get_absolute_url(), outfit.short_description or outfit.mood_description),
                breadcrumb_schema(
                    request,
                    [("Start", reverse("core:home")), ("Stylizacje", reverse("outfits:list")), (outfit.name, outfit.get_absolute_url())],
                ),
            ],
        },
    )
