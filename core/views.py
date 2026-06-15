from django.db.models import Q
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from analytics.services import track_event
from blog.models import Article
from catalog.models import Aesthetic, Product
from outfits.models import Outfit
from .models import NewsletterSubscriber, SiteSettings


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
    settings_obj = SiteSettings.load()

    drop_products = list(
        settings_obj.drop_products.filter(status=Product.STATUS_ACTIVE)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("sort_order", "-created_at")[:8]
    )
    if not drop_products:
        drop_products = list(
            Product.objects.filter(status=Product.STATUS_ACTIVE)
            .prefetch_related("images", "aesthetics", "variants__color")
            .order_by("sort_order", "-created_at")[:4]
        )

    hero_product = drop_products[0] if drop_products else None
    hero_mini_product = (
        Product.objects.filter(status=Product.STATUS_ACTIVE, is_featured=True)
        .prefetch_related("images")
        .order_by("sort_order", "-created_at")
        .first()
    )
    if hero_mini_product is None and len(drop_products) > 1:
        hero_mini_product = drop_products[1]

    outfits = (
        Outfit.objects.filter(status=Outfit.STATUS_ACTIVE)
        .prefetch_related("images", "aesthetics", "items")
        .order_by("-is_featured", "sort_order", "-created_at")[:5]
    )
    aesthetics = (
        Aesthetic.objects.filter(is_active=True)
        .order_by("-is_featured", "sort_order", "name")[:8]
    )
    articles = (
        Article.objects.filter(status=Article.STATUS_PUBLISHED)
        .select_related("category")
        .order_by("-published_at", "-created_at")[:3]
    )

    return render(
        request,
        "core/home.html",
        {
            "drop_products": drop_products,
            "hero_product": hero_product,
            "hero_mini_product": hero_mini_product,
            "outfits": outfits,
            "aesthetics": aesthetics,
            "articles": articles,
        },
    )


def contact_view(request):
    return render(request, "core/contact.html")


def design_system_view(request):
    demo_product = (
        Product.objects.filter(status=Product.STATUS_ACTIVE)
        .prefetch_related("images", "aesthetics", "variants__color")
        .order_by("sort_order", "-created_at")
        .first()
    )
    demo_aesthetic = Aesthetic.objects.filter(is_active=True).order_by("sort_order", "name").first()
    return render(
        request,
        "core/design_system.html",
        {"demo_product": demo_product, "demo_aesthetic": demo_aesthetic},
    )


def search_view(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.none()
    if query:
        track_event(request, "search", metadata={"query": query})
        products = (
            Product.objects.filter(status=Product.STATUS_ACTIVE)
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
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
