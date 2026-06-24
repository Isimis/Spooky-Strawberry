from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
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
        .order_by("sort_order", "name")[:8]
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


def shipping_view(request):
    return render(request, "core/shipping.html")


def returns_view(request):
    return render(request, "core/returns.html")


def terms_view(request):
    return render(request, "core/terms.html")


def privacy_view(request):
    return render(request, "core/privacy.html")


def cookies_view(request):
    return render(request, "core/cookies.html")


def about_view(request):
    return render(request, "core/about.html")


def accessibility_view(request):
    return render(request, "core/accessibility.html")


def sitemap_view(request):
    return render(request, "core/sitemap.html")


def build_status_timeline(order):
    from orders.models import Order

    labels = [
        "Zamówienie złożone",
        "Płatność potwierdzona",
        "Spakowane z sercem",
        "W drodze",
        "Gotowe do odbioru",
    ]
    progress = {
        Order.STATUS_PLACED: 1,
        Order.STATUS_CONFIRMED: 2,
        Order.STATUS_PACKED: 3,
        Order.STATUS_SHIPPED: 4,
    }.get(order.status, 1)

    steps = []
    for index, label in enumerate(labels):
        state = "done" if index < progress else ("active" if index == progress else "")
        steps.append({"label": label, "state": state, "index": index + 1})
    return steps


def order_status_view(request):
    from orders.models import Order

    number = request.GET.get("number", "").strip()
    email = request.GET.get("email", "").strip().lower()
    order = None
    not_found = False
    timeline = None

    if number or email:
        order = (
            Order.objects.select_related("shipping_method")
            .prefetch_related("items__product__images")
            .filter(order_number__iexact=number, email__iexact=email)
            .exclude(status=Order.STATUS_DRAFT)
            .first()
        )
        if order:
            timeline = build_status_timeline(order)
        else:
            not_found = True

    return render(
        request,
        "core/order_status.html",
        {
            "order": order,
            "timeline": timeline,
            "not_found": not_found,
            "q_number": number,
            "q_email": email,
        },
    )


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


SEARCH_SUGGESTIONS = ["choker", "kabaretki", "mitenki", "soft goth", "y2k", "rajstopy"]


def search_view(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.none()
    bestsellers = []
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
        if not products:
            bestsellers = list(
                Product.objects.filter(status=Product.STATUS_ACTIVE)
                .prefetch_related("images", "aesthetics", "variants__color")
                .order_by("-is_bestseller", "sort_order", "-created_at")[:4]
            )

    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "products": products,
            "bestsellers": bestsellers,
            "suggestions": SEARCH_SUGGESTIONS,
        },
    )


def cart_view(request):
    return render(request, "core/cart.html")


def newsletter_thanks_view(request):
    return render(request, "core/newsletter_thanks.html")


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
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    email = request.POST.get("email", "").strip().lower()
    next_url = request.POST.get("next") or "core:home"
    if not email:
        if is_ajax:
            return JsonResponse({"ok": False, "message": "Podaj poprawny adres e-mail."}, status=400)
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

    # Zapamiętaj zapis na całą sesję — kafelek newslettera pokazuje wtedy
    # potwierdzenie zamiast formularza na każdej podstronie.
    request.session["newsletter_email"] = email

    if is_ajax:
        if created:
            heading = "Jesteś w klubie! 🍓"
            message = f"Wysłaliśmy kod rabatowy -10% na {email}. Sprawdź skrzynkę (i folder spam), żeby go odebrać."
        else:
            heading = "Już jesteś z nami 🖤"
            message = f"Adres {email} jest już zapisany — kod rabatowy znajdziesz w mailu powitalnym."
        return JsonResponse({"ok": True, "created": created, "heading": heading, "message": message})

    if created:
        return redirect("core:newsletter_thanks")

    messages.info(request, "Ten adres jest już zapisany do newslettera.")
    return redirect(next_url)
