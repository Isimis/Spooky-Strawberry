from django.db.models import Q
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from analytics.services import track_event
from catalog.models import Product
from .models import NewsletterSubscriber


POLICIES = {
    "polityka-prywatnosci": {
        "title": "Polityka prywatności",
        "intro": "Miejsce na docelową politykę prywatności sklepu Spooky Strawberry.",
    },
    "polityka-zwrotow": {
        "title": "Polityka zwrotów",
        "intro": "Miejsce na zasady zwrotów, reklamacji i kontaktu po zakupie.",
    },
    "regulamin": {
        "title": "Regulamin",
        "intro": "Miejsce na regulamin sklepu przed uruchomieniem sprzedaży.",
    },
    "polityka-wysylki": {
        "title": "Polityka wysyłki",
        "intro": "Miejsce na docelowe informacje o dostawie, kosztach i czasie realizacji.",
    },
    "dane-kontaktowe": {
        "title": "Dane kontaktowe",
        "intro": "Miejsce na dane firmy, gdy sklep będzie gotowy do sprzedaży.",
    },
    "nota-prawna": {
        "title": "Nota prawna",
        "intro": "Miejsce na informacje prawne wymagane przed publikacją sklepu.",
    },
    "preferencje-cookie": {
        "title": "Preferencje dotyczące plików cookie",
        "intro": "Miejsce na ustawienia i opis plików cookie.",
    },
}


def home_view(request):
    new_drop_products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, is_new_drop=True)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("sort_order", "-created_at")[:8]
    )
    featured_products = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, is_featured=True)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("sort_order", "-created_at")[:4]
    )

    return render(
        request,
        "core/home.html",
        {
            "new_drop_products": new_drop_products,
            "featured_products": featured_products,
        },
    )


def contact_view(request):
    return render(request, "core/contact.html")


def search_view(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.none()
    if query:
        track_event(request, "search", metadata={"query": query})
        products = (
            Product.objects.filter(status=Product.STATUS_ACTIVE)
            .filter(
                Q(name__icontains=query)
                | Q(short_description__icontains=query)
                | Q(mood_description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(aesthetics__name__icontains=query)
            )
            .prefetch_related("images", "aesthetics", "variants__color")
            .distinct()
            .order_by("sort_order", "-created_at")
        )

    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "products": products,
        },
    )


def cart_view(request):
    return render(request, "core/cart.html")


def account_view(request):
    return render(request, "core/account.html")


def policy_view(request, slug):
    policy = POLICIES.get(slug)
    if policy is None:
        policy = {
            "title": slugify(slug).replace("-", " ").capitalize(),
            "intro": "Ta strona zostanie uzupełniona przed publikacją sklepu.",
        }
    return render(request, "core/policy.html", {"policy": policy})


@require_POST
def newsletter_subscribe(request):
    email = request.POST.get("email", "").strip().lower()
    next_url = request.POST.get("next") or "core:home"
    if not email:
        messages.error(request, "Podaj adres e-mail.")
        return redirect(next_url)

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "source": request.POST.get("source") or NewsletterSubscriber.SOURCE_FOOTER,
            "consent_text": "Zapis do newslettera Spooky Strawberry.",
        },
    )
    if not created and not subscriber.is_active:
        subscriber.is_active = True
        subscriber.save(update_fields=["is_active"])

    if created:
        messages.success(request, "Jesteś zapisana do newslettera.")
    else:
        messages.info(request, "Ten adres jest już zapisany do newslettera.")
    return redirect(next_url)
