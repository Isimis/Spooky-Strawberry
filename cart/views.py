from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from analytics.services import track_event
from catalog.models import Product, ProductVariant
from orders.shipping import get_shipping_estimate as get_default_shipping_estimate

from .services import (
    add_to_cart,
    apply_discount_code,
    clear_cart,
    get_cart_quantity,
    get_cart_summary,
    remove_discount_code,
    remove_cart_item,
    save_cart_for_user,
    update_cart_item,
)


def get_shipping_estimate(subtotal):
    return get_default_shipping_estimate(subtotal)


def cart_detail(request):
    summary = get_cart_summary(request, user=request.user, email=getattr(request.user, "email", ""))
    track_event(
        request,
        "cart_view",
        metadata={
            "quantity": summary["quantity"],
            "subtotal": str(summary["subtotal"]),
        },
    )
    shipping_cost, free_from, remaining = get_shipping_estimate(summary["discounted_subtotal"])

    in_cart_ids = [item["product"].id for item in summary["items"] if item.get("product")]
    recommendations = list(
        Product.objects.filter(status=Product.STATUS_ACTIVE)
        .exclude(id__in=in_cart_ids)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("-is_bestseller", "sort_order", "-created_at")[:4]
    )

    summary.update(
        {
            "shipping_cost": shipping_cost,
            "free_from": free_from,
            "free_remaining": remaining,
            "grand_total": summary["discounted_subtotal"] + shipping_cost,
            "recommendations": recommendations,
        }
    )
    return render(request, "cart/detail.html", summary)


@require_POST
def apply_discount(request):
    result = apply_discount_code(
        request,
        request.POST.get("code", ""),
        user=request.user,
        email=getattr(request.user, "email", ""),
    )
    if result.is_valid:
        messages.success(request, f"Kod {result.discount_code.code} został dodany do koszyka.")
    else:
        messages.error(request, result.error)
    return redirect("cart:detail")


@require_POST
def remove_discount(request):
    remove_discount_code(request)
    messages.info(request, "Kod rabatowy został usunięty.")
    return redirect("cart:detail")


@require_POST
def add_item(request):
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        pk=request.POST.get("variant_id"),
        is_active=True,
        product__status=Product.STATUS_ACTIVE,
    )
    quantity = request.POST.get("quantity", 1)
    result = add_to_cart(request, variant, quantity)
    save_cart_for_user(request)
    track_event(
        request,
        "add_to_cart",
        product=variant.product,
        variant=variant,
        metadata={"quantity": result.get("requested", 1), "limited": result.get("limited", False)},
    )

    if result["reason"] == "unavailable":
        text, level = "Ten wariant jest chwilowo niedostępny.", "error"
    elif result.get("limited"):
        text, level = (
            f"Dodano maksymalną dostępną ilość. W magazynie jest {result['available']} szt.",
            "warning",
        )
    else:
        text, level = "Dodano do koszyka 🍓", "success"

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": result["reason"] != "unavailable",
                "message": text,
                "cart_count": get_cart_quantity(request),
            }
        )

    getattr(messages, level)(request, text)
    return redirect(request.POST.get("next") or reverse("cart:detail"))


@require_POST
def add_outfit(request, slug):
    from outfits.models import Outfit

    outfit = get_object_or_404(
        Outfit.objects.prefetch_related("items__variant", "items__product__variants"),
        slug=slug,
        status=Outfit.STATUS_ACTIVE,
    )
    added = 0
    for item in outfit.items.all():
        variant = item.variant or item.product.default_variant
        if variant:
            result = add_to_cart(request, variant, item.quantity or 1)
            if result.get("added"):
                added += 1
    save_cart_for_user(request)

    text = "Dodano zestaw do koszyka 🍓" if added else "Nie udało się dodać zestawu - brak dostępnych wariantów."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": added > 0, "message": text, "cart_count": get_cart_quantity(request)})

    (messages.success if added else messages.warning)(request, text)
    return redirect(request.POST.get("next") or reverse("cart:detail"))


@require_POST
def update_item(request, variant_id):
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=variant_id)
    result = update_cart_item(request, variant, request.POST.get("quantity", 1))
    save_cart_for_user(request)

    if result.get("removed") and result.get("reason") == "unavailable":
        messages.warning(request, "Usunięto produkt, bo nie jest już dostępny.")
    elif result.get("removed"):
        messages.success(request, "Produkt usunięty z koszyka.")
    elif result.get("limited"):
        messages.warning(request, f"Ilość ograniczona do stanu magazynowego: {result['available']} szt.")
    else:
        messages.success(request, "Koszyk zaktualizowany.")
    return redirect("cart:detail")


@require_POST
def remove_item(request, variant_id):
    remove_cart_item(request, variant_id)
    save_cart_for_user(request)
    messages.success(request, "Produkt usunięty z koszyka.")
    return redirect("cart:detail")


@require_POST
def clear_items(request):
    clear_cart(request)
    save_cart_for_user(request)
    messages.success(request, "Koszyk wyczyszczony.")
    return redirect("cart:detail")
