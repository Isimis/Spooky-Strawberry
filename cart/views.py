from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from analytics.services import track_event
from catalog.models import Product, ProductVariant

from .services import add_to_cart, clear_cart, get_cart_summary, remove_cart_item, update_cart_item


def cart_detail(request):
    summary = get_cart_summary(request)
    track_event(
        request,
        "cart_view",
        metadata={
            "quantity": summary["quantity"],
            "subtotal": str(summary["subtotal"]),
        },
    )
    return render(request, "cart/detail.html", summary)


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
    track_event(
        request,
        "add_to_cart",
        product=variant.product,
        variant=variant,
        metadata={"quantity": result.get("requested", 1), "limited": result.get("limited", False)},
    )

    if result["reason"] == "unavailable":
        messages.error(request, "Ten wariant jest chwilowo niedostępny.")
    elif result.get("limited"):
        messages.warning(
            request,
            f"Dodano maksymalną dostępną ilość. W magazynie jest {result['available']} szt.",
        )
    else:
        messages.success(request, "Produkt dodany do koszyka.")
    return redirect(request.POST.get("next") or reverse("cart:detail"))


@require_POST
def update_item(request, variant_id):
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=variant_id)
    result = update_cart_item(request, variant, request.POST.get("quantity", 1))

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
    messages.success(request, "Produkt usunięty z koszyka.")
    return redirect("cart:detail")


@require_POST
def clear_items(request):
    clear_cart(request)
    messages.success(request, "Koszyk wyczyszczony.")
    return redirect("cart:detail")
