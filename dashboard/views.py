from pathlib import Path
import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models import Max
from django.db.models.functions import Coalesce, TruncDate
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods

from analytics.models import AnalyticsEvent, AnalyticsSession
from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size
from core.models import Message, MessageTemplate, NewsletterSubscriber, SiteSettings
from core.mailbox import MailboxConfigurationError, sync_mailbox
from core.mailer import BASE_LAYOUT_KEY, send_message
from dashboard.models import DataQualityIssue
from inventory.models import StockEntry
from inventory.services import recalculate_variant_stock
from orders.models import DiscountCode, Order, OrderItem, ShippingMethod
from orders.services import expire_stale_pending_orders
from outfits.models import Outfit, OutfitHotspot, OutfitImage, OutfitItem

from .forms import (
    OutfitDashboardForm,
    OutfitHotspotFormSet,
    OutfitImageFormSet,
    OutfitItemFormSet,
    ArticleDashboardForm,
    OrderDashboardForm,
    OrderItemFormSet,
    ProductDashboardForm,
    ProductImageFormSet,
    ProductVariantFormSet,
    SiteSettingsDashboardForm,
    StockEntryForm,
    UserAccountCreateForm,
    UserAccountForm,
    build_model_form,
)
from .registry import MODEL_REGISTRY, get_model_config, get_sections
from .services import count_unique_visitors, get_dashboard_analytics, refresh_all_product_quality_issues, refresh_product_quality_issues

User = get_user_model()


PRODUCT_SORT_HEADERS = {
    "product": "Produkt",
    "category": "Kategoria",
    "regular_price": "Cena regularna",
    "sale_price": "Cena promocyjna",
    "stock": "Ilość",
    "status": "Status",
    "featured": "Polecany",
}

ALLOWED_PRODUCT_IMAGE_EXTENSIONS = {".webp", ".jpg", ".jpeg", ".png"}
ALLOWED_PRODUCT_IMAGE_CONTENT_TYPES = {"image/webp", "image/jpeg", "image/png"}
PRODUCT_IMAGE_ACCEPT = ".webp,.jpg,.jpeg,.png,image/webp,image/jpeg,image/png"


def staff_required(view_func):
    return user_passes_test(
        lambda user: user.is_active and user.is_staff,
        login_url="dashboard:login",
    )(view_func)


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("dashboard:home")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(request.GET.get("next") or "dashboard:home")

    return render(request, "dashboard/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("dashboard:login")


@staff_required
def home(request):
    open_quality_issues = DataQualityIssue.objects.filter(status=DataQualityIssue.STATUS_OPEN).count()
    return render(
        request,
        "dashboard/home.html",
        {
            "sections": get_sections(),
            "analytics": get_dashboard_analytics(),
            "open_quality_issues": open_quality_issues,
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def site_settings(request):
    settings_obj = SiteSettings.load()
    form = SiteSettingsDashboardForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ustawienia strony zapisane.")
        return redirect("dashboard:site_settings")

    selected_ids = set(settings_obj.drop_products.values_list("id", flat=True))
    drop_products = []
    for product in (
        Product.objects.filter(status=Product.STATUS_ACTIVE)
        .prefetch_related("images")
        .order_by("-created_at", "name")
    ):
        image = product.main_image
        drop_products.append(
            {
                "product": product,
                "thumb": image.image.url if image else "",
                "selected": product.id in selected_ids,
            }
        )

    return render(
        request,
        "dashboard/site_settings.html",
        {
            "form": form,
            "drop_products": drop_products,
            "drop_selected_count": len(selected_ids),
            "sections": get_sections(),
        },
    )


def user_account_type(user):
    """Zwraca (etykieta, klasa pigułki) dla rodzaju konta."""
    if user.is_superuser:
        return "Administrator", "best"
    if user.is_staff:
        return "Zespół", "draft"
    return "Klient", "active"


def _user_paid_orders(user):
    return [
        order
        for order in user.orders.all()
        if order.status not in {Order.STATUS_DRAFT, Order.STATUS_CANCELLED}
    ]


def build_user_account_row(user):
    type_label, type_class = user_account_type(user)
    paid_orders = _user_paid_orders(user)
    spent = sum((order.grand_total for order in paid_orders), Decimal("0.00"))
    profile = getattr(user, "customer_profile", None)
    return {
        "object": user,
        "email": user.email or user.get_username(),
        "name": user.get_full_name() or "—",
        "type_label": type_label,
        "type_class": type_class,
        "is_active": user.is_active,
        "orders_count": user.orders.count(),
        "paid_count": len(paid_orders),
        "spent": spent,
        "accepts_marketing": bool(profile and profile.accepts_marketing),
        "date_joined": user.date_joined,
        "last_login": user.last_login,
        "admin_url": reverse("dashboard:user_account_detail", args=[user.pk]),
    }


def build_user_account_summary():
    queryset = User.objects.all()
    now = timezone.now()
    return {
        "total_count": queryset.count(),
        "customer_count": queryset.filter(is_staff=False).count(),
        "staff_count": queryset.filter(is_staff=True).count(),
        "new_30_count": queryset.filter(date_joined__gte=now - timedelta(days=30)).count(),
    }


def get_user_account_type_choices():
    return [
        ("customer", "Klienci"),
        ("staff", "Zespół"),
        ("admin", "Administratorzy"),
    ]


def apply_user_admin_filters(request, queryset, active_filters):
    account_type = request.GET.get("account_type", "")
    if account_type == "customer":
        queryset = queryset.filter(is_staff=False)
        active_filters.append("Typ: Klienci")
    elif account_type == "staff":
        queryset = queryset.filter(is_staff=True, is_superuser=False)
        active_filters.append("Typ: Zespół")
    elif account_type == "admin":
        queryset = queryset.filter(is_superuser=True)
        active_filters.append("Typ: Administratorzy")

    state = request.GET.get("state", "")
    if state == "active":
        queryset = queryset.filter(is_active=True)
        active_filters.append("Aktywne")
    elif state == "inactive":
        queryset = queryset.filter(is_active=False)
        active_filters.append("Nieaktywne")
    return queryset


def build_user_consents(user_obj, profile):
    """Wszystkie zgody dostępne w serwisie — z ich statusem dla danego konta."""
    newsletter_active = bool(
        user_obj.email
        and NewsletterSubscriber.objects.filter(email__iexact=user_obj.email, is_active=True).exists()
    )
    accepts_marketing = bool(profile and profile.accepts_marketing)
    email_verified = bool(profile and profile.email_verified)
    return [
        {
            "label": "Potwierdzenie e-mail",
            "help": "Czy adres e-mail został potwierdzony linkiem weryfikacyjnym.",
            "granted": email_verified,
            "value": "Potwierdzony" if email_verified else "Niepotwierdzony",
        },
        {
            "label": "Zgoda marketingowa",
            "help": "Zgoda na newsletter, dropy i kody rabatowe (profil klienta).",
            "granted": accepts_marketing,
            "value": "Udzielona" if accepts_marketing else "Brak",
        },
        {
            "label": "Newsletter (zapis e-mail)",
            "help": "Aktywny zapis adresu w bazie newslettera.",
            "granted": newsletter_active,
            "value": "Aktywny" if newsletter_active else "Brak zapisu",
        },
    ]


@staff_required
@require_http_methods(["GET", "POST"])
def user_account_detail(request, pk):
    user_obj = get_object_or_404(
        User.objects.select_related("customer_profile").prefetch_related("orders__shipping_method"),
        pk=pk,
    )
    profile = getattr(user_obj, "customer_profile", None)
    form = UserAccountForm(instance=user_obj)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_active":
            if user_obj == request.user:
                messages.error(request, "Nie możesz dezaktywować własnego konta.")
            else:
                user_obj.is_active = not user_obj.is_active
                user_obj.save(update_fields=["is_active"])
                messages.success(request, "Zaktualizowano status konta.")
            return redirect("dashboard:user_account_detail", pk=pk)
        elif action == "toggle_staff":
            if user_obj.is_superuser:
                messages.error(request, "Konta administratora nie zmieniamy z tego widoku.")
            elif user_obj == request.user:
                messages.error(request, "Nie odbieraj dostępu samemu sobie.")
            else:
                user_obj.is_staff = not user_obj.is_staff
                user_obj.save(update_fields=["is_staff"])
                messages.success(request, "Zmieniono dostęp do panelu.")
            return redirect("dashboard:user_account_detail", pk=pk)
        elif action == "delete":
            if user_obj == request.user:
                messages.error(request, "Nie możesz usunąć własnego konta.")
                return redirect("dashboard:user_account_detail", pk=pk)
            user_obj.delete()
            messages.success(request, "Konto zostało usunięte.")
            return redirect("dashboard:model_list", model_slug="user-accounts")
        elif action == "save":
            form = UserAccountForm(request.POST, instance=user_obj)
            if form.is_valid():
                if user_obj == request.user and not form.cleaned_data.get("is_active", True):
                    messages.error(request, "Nie możesz dezaktywować własnego konta.")
                else:
                    form.save()
                    messages.success(request, "Zapisano zmiany w koncie.")
                    return redirect("dashboard:user_account_detail", pk=pk)

    type_label, type_class = user_account_type(user_obj)
    paid_orders = _user_paid_orders(user_obj)
    orders = list(user_obj.orders.all().order_by("-created_at"))

    return render(
        request,
        "dashboard/user_account_detail.html",
        {
            "config": get_required_config("user-accounts"),
            "account": user_obj,
            "form": form,
            "type_label": type_label,
            "type_class": type_class,
            "profile": profile,
            "consents": build_user_consents(user_obj, profile),
            "orders": orders,
            "orders_count": len(orders),
            "paid_count": len(paid_orders),
            "spent_total": sum((order.grand_total for order in paid_orders), Decimal("0.00")),
            "is_self": user_obj == request.user,
            "sections": get_sections(),
        },
    )


def build_message_row(message):
    counterpart = message.from_email if message.direction == Message.DIRECTION_INBOUND else message.to_email
    display_date = message.received_at if message.direction == Message.DIRECTION_INBOUND else message.sent_at
    is_unread = message.direction == Message.DIRECTION_INBOUND and message.read_at is None
    return {
        "object": message,
        "subject": message.subject or "(bez tematu)",
        "counterpart": counterpart or "—",
        "direction": message.direction,
        "direction_label": message.get_direction_display(),
        "status": message.status,
        "status_label": message.get_status_display(),
        "is_unread": is_unread,
        "created_at": display_date or message.created_at,
        "admin_url": reverse("dashboard:message_detail", args=[message.pk]),
    }


def build_message_summary():
    queryset = Message.objects.all()
    return {
        "total_count": queryset.count(),
        "inbound_count": queryset.filter(direction=Message.DIRECTION_INBOUND).count(),
        "outbound_count": queryset.filter(direction=Message.DIRECTION_OUTBOUND).count(),
        "unread_count": queryset.filter(
            direction=Message.DIRECTION_INBOUND,
            read_at__isnull=True,
        ).count(),
        "draft_count": queryset.filter(status=Message.STATUS_DRAFT).count(),
    }


@staff_required
@require_http_methods(["GET", "POST"])
def message_compose(request):
    templates = list(
        MessageTemplate.objects.filter(is_active=True)
        .exclude(system_key=BASE_LAYOUT_KEY)
        .order_by("-is_system", "name")
    )
    recipients = request.session.get("compose_recipients") or []

    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        body_html = request.POST.get("body_html", "")
        template_id = request.POST.get("template") or None
        template = MessageTemplate.objects.filter(pk=template_id).first() if template_id else None

        single = request.POST.get("to_email", "").strip()
        targets = recipients if recipients else ([single] if single else [])
        if not targets:
            messages.error(request, "Podaj odbiorcę wiadomości.")
            return redirect("dashboard:message_compose")

        sent, failed = [], []
        for email in targets:
            user = User.objects.filter(email__iexact=email).first()
            context = {"first_name": user.first_name if user else "", "email": email}
            try:
                # Nadawcą jest uwierzytelniona skrzynka (DEFAULT_FROM_EMAIL), żeby
                # serwer SMTP nie odrzucił maila przy niezgodnym adresie „od”.
                send_message(
                    subject=subject,
                    body_html=body_html,
                    to_email=email,
                    context=context,
                    template=template,
                )
                sent.append(email)
            except Exception:
                failed.append(email)

        request.session.pop("compose_recipients", None)

        if sent and not failed:
            label = "odbiorcy" if len(sent) == 1 else "odbiorców"
            messages.success(request, f"Wysłano wiadomość do {len(sent)} {label}.")
        elif sent and failed:
            messages.warning(
                request,
                f"Wysłano do {len(sent)} odbiorców. Nie udało się: {', '.join(failed)}.",
            )
        else:
            messages.error(request, "Nie udało się wysłać wiadomości. Sprawdź konfigurację skrzynki.")
            return redirect("dashboard:message_compose")

        if len(sent) == 1:
            last = Message.objects.filter(to_email=sent[0]).order_by("-created_at").first()
            if last:
                return redirect("dashboard:message_detail", pk=last.pk)
        return redirect("dashboard:model_list", model_slug="messages")

    templates_json = json.dumps(
        {str(t.pk): {"subject": t.subject, "body_html": t.body_html} for t in templates}
    )
    return render(
        request,
        "dashboard/message_compose.html",
        {
            "config": get_required_config("messages"),
            "templates": templates,
            "templates_json": templates_json,
            "recipients": recipients,
            "sections": get_sections(),
        },
    )


@staff_required
@require_POST
def sync_messages(request):
    try:
        imported = sync_mailbox()
    except MailboxConfigurationError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Nie udało się połączyć ze skrzynką. Sprawdź dane IMAP i hasło.")
    else:
        if imported:
            messages.success(request, f"Pobrano {len(imported)} nowych wiadomości.")
        else:
            messages.info(request, "Skrzynka jest aktualna. Nie ma nowych wiadomości.")
    return redirect("dashboard:model_list", model_slug="messages")


@staff_required
@require_POST
def bulk_compose(request):
    """Zbiera zaznaczone adresy z listy i przerzuca do edytora wiadomości."""
    raw_emails = request.POST.getlist("emails")
    cleaned, seen = [], set()
    for email in raw_emails:
        email = (email or "").strip()
        key = email.lower()
        if email and key not in seen:
            seen.add(key)
            cleaned.append(email)

    back = request.POST.get("back", "")
    # Tylko ścieżki względne — nie pozwalamy przekierować poza panel.
    fallback = back if back.startswith("/") and not back.startswith("//") else reverse("dashboard:home")
    if not cleaned:
        messages.error(request, "Zaznacz przynajmniej jednego odbiorcę.")
        return redirect(fallback)

    request.session["compose_recipients"] = cleaned
    return redirect("dashboard:message_compose")


@staff_required
@require_POST
def bulk_message_action(request):
    """Akcja masowa w skrzynce: oznacz zaznaczone wiadomości jako (nie)przeczytane."""
    ids = request.POST.getlist("message_ids")
    action = request.POST.get("bulk_action", "")
    back = request.POST.get("back", "")
    fallback = back if back.startswith("/") and not back.startswith("//") else reverse(
        "dashboard:model_list", args=["messages"]
    )

    if not ids:
        messages.error(request, "Zaznacz przynajmniej jedną wiadomość.")
        return redirect(fallback)

    # Przeczytane/nieprzeczytane dotyczy tylko wiadomości przychodzących.
    queryset = Message.objects.filter(pk__in=ids, direction=Message.DIRECTION_INBOUND)
    if action == "read":
        updated = queryset.filter(read_at__isnull=True).update(read_at=timezone.now())
        messages.success(request, f"Oznaczono jako przeczytane: {updated}.")
    elif action == "unread":
        updated = queryset.filter(read_at__isnull=False).update(read_at=None)
        messages.success(request, f"Oznaczono jako nieprzeczytane: {updated}.")
    else:
        messages.error(request, "Wybierz akcję z listy.")
    return redirect(fallback)


@staff_required
@require_http_methods(["GET", "POST"])
def base_layout_edit(request):
    """Edycja szablonu bazowego (wzorka), w który owijamy każdego maila."""
    template = MessageTemplate.objects.filter(system_key=BASE_LAYOUT_KEY).first()
    if template is None:
        raise Http404("Brak szablonu bazowego.")
    if request.method == "POST":
        template.body_html = request.POST.get("body_html", "")
        template.save(update_fields=["body_html", "updated_at"])
        messages.success(request, "Szablon bazowy zapisany.")
        return redirect("dashboard:base_layout_edit")
    return render(
        request,
        "dashboard/base_layout_form.html",
        {
            "template": template,
            "sections": get_sections(),
        },
    )


@staff_required
def message_detail(request, pk):
    message = get_object_or_404(Message.objects.select_related("template"), pk=pk)
    if message.direction == Message.DIRECTION_INBOUND and message.read_at is None:
        message.read_at = timezone.now()
        message.save(update_fields=["read_at"])
    return render(
        request,
        "dashboard/message_detail.html",
        {
            "config": get_required_config("messages"),
            "message": message,
            "sections": get_sections(),
        },
    )


def build_email_template_row(template):
    return {
        "object": template,
        "name": template.name,
        "subject": template.subject or "—",
        "description": template.description,
        "is_active": template.is_active,
        "is_system": template.is_system,
        "admin_url": reverse("dashboard:email_template_edit", args=[template.pk]),
    }


@staff_required
@require_http_methods(["GET", "POST"])
def email_template_edit(request, pk):
    template = get_object_or_404(MessageTemplate, pk=pk)
    if template.system_key == BASE_LAYOUT_KEY:
        return redirect("dashboard:base_layout_edit")
    if request.method == "POST":
        template.subject = request.POST.get("subject", "").strip()
        template.body_html = request.POST.get("body_html", "")
        template.is_active = request.POST.get("is_active") == "on"
        if not template.is_system:
            template.name = request.POST.get("name", template.name).strip() or template.name
            template.description = request.POST.get("description", template.description).strip()
        template.save()
        messages.success(request, "Szablon zapisany.")
        return redirect("dashboard:email_template_edit", pk=pk)
    return render(
        request,
        "dashboard/email_template_form.html",
        {
            "config": get_required_config("email-templates"),
            "template": template,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def user_account_create(request):
    form = UserAccountCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user_obj = form.save()
        messages.success(request, "Konto zostało utworzone.")
        return redirect("dashboard:user_account_detail", pk=user_obj.pk)
    return render(
        request,
        "dashboard/user_account_form.html",
        {
            "config": get_required_config("user-accounts"),
            "form": form,
            "sections": get_sections(),
        },
    )


@staff_required
def model_list(request, model_slug):
    config = get_required_config(model_slug)
    queryset = config.model._default_manager.all()
    query = request.GET.get("q", "").strip()
    active_filters = []

    if config.model is Product:
        queryset = queryset.select_related("category").prefetch_related("images", "variants", "aesthetics")
        queryset = apply_product_admin_filters(request, queryset, active_filters)
    elif config.model is Outfit:
        queryset = queryset.prefetch_related("images", "items__product", "items__variant", "aesthetics")
        queryset = apply_outfit_admin_filters(request, queryset, active_filters)
    elif config.model is Article:
        queryset = queryset.select_related("category").prefetch_related("aesthetics", "products", "outfits")
        queryset = apply_article_admin_filters(request, queryset, active_filters)
    elif config.model is NewsletterSubscriber:
        queryset = apply_newsletter_admin_filters(request, queryset, active_filters)
    elif config.model is Order:
        # Samoczyszczenie: przy każdym wejściu na listę wygaszamy porzucone, nieopłacone
        # zamówienia (nie blokują stanu — to tylko higiena panelu).
        expire_stale_pending_orders()
        queryset = queryset.select_related("user", "shipping_method", "discount_code").prefetch_related("items")
        queryset = apply_order_admin_filters(request, queryset, active_filters)
    elif config.model is OrderItem:
        queryset = queryset.select_related("order", "product", "variant").prefetch_related("product__images")
    elif config.model is ShippingMethod:
        queryset = queryset.annotate(order_count=Count("orders"))
        queryset = apply_shipping_method_admin_filters(request, queryset, active_filters)
        queryset = queryset.order_by("sort_order", "name")
    elif config.model is DiscountCode:
        queryset = queryset.annotate(order_count=Count("orders"))
        queryset = apply_discount_code_admin_filters(request, queryset, active_filters)
        queryset = queryset.order_by("code")
    elif config.model is AnalyticsSession:
        queryset = queryset.prefetch_related("events__product", "events__variant").annotate(
            event_count=Count("events"),
            page_view_count=Count("events", filter=Q(events__event_type=AnalyticsEvent.EVENT_PAGE_VIEW)),
            product_view_count=Count("events", filter=Q(events__event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW)),
            add_to_cart_count=Count("events", filter=Q(events__event_type=AnalyticsEvent.EVENT_ADD_TO_CART)),
        )
        queryset = apply_analytics_session_filters(request, queryset, active_filters)
        queryset = queryset.order_by("-last_seen_at")
    elif config.model is AnalyticsEvent:
        queryset = queryset.select_related("session", "product", "variant")
        queryset = apply_analytics_event_filters(request, queryset, active_filters)
        queryset = queryset.order_by("-created_at")
    elif config.model is User:
        queryset = queryset.select_related("customer_profile").prefetch_related("orders")
        queryset = apply_user_admin_filters(request, queryset, active_filters)
        queryset = queryset.order_by("-date_joined")
    elif config.model is MessageTemplate:
        queryset = queryset.exclude(system_key=BASE_LAYOUT_KEY).order_by("-is_system", "name")
    elif config.model is Message:
        box = request.GET.get("box", "")
        if box == "inbound":
            queryset = queryset.filter(direction=Message.DIRECTION_INBOUND)
            active_filters.append("Skrzynka: odebrane")
        elif box == "outbound":
            queryset = queryset.filter(direction=Message.DIRECTION_OUTBOUND)
            active_filters.append("Skrzynka: wysłane")
        # Zawsze sortuj po faktycznej dacie wiadomości: odebrania (inbound) lub wysłania
        # (outbound), a w ostateczności po dacie utworzenia.
        queryset = queryset.annotate(
            effective_date=Coalesce("received_at", "sent_at", "created_at")
        ).order_by("-effective_date")
    elif is_taxonomy_model(config.model):
        queryset = prepare_taxonomy_queryset(config.model, queryset)
        queryset = apply_taxonomy_filters(request, queryset, active_filters)

    if query and config.search_fields:
        filters = Q()
        for field in config.search_fields:
            filters |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(filters)
        active_filters.append(f"Szukaj: {query}")

    if config.model is Product:
        queryset = apply_product_sorting(queryset, request)

    paginator = Paginator(queryset.distinct(), 25)
    page = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    if config.model is Product:
        rows = [build_product_row(obj) for obj in page.object_list]
    elif config.model is Outfit:
        rows = [build_outfit_row(obj) for obj in page.object_list]
    elif config.model is Article:
        rows = [build_article_row(obj) for obj in page.object_list]
    elif config.model is NewsletterSubscriber:
        rows = [build_newsletter_row(obj) for obj in page.object_list]
    elif config.model is Order:
        rows = [build_order_row(obj) for obj in page.object_list]
    elif config.model is OrderItem:
        rows = [build_order_item_list_row(obj) for obj in page.object_list]
    elif config.model is ShippingMethod:
        rows = [build_shipping_method_row(obj) for obj in page.object_list]
    elif config.model is DiscountCode:
        rows = [build_discount_code_row(obj) for obj in page.object_list]
    elif config.model is AnalyticsSession:
        rows = [build_analytics_session_row(obj) for obj in page.object_list]
    elif config.model is AnalyticsEvent:
        rows = [build_analytics_event_row(obj) for obj in page.object_list]
    elif config.model is User:
        rows = [build_user_account_row(obj) for obj in page.object_list]
    elif config.model is MessageTemplate:
        rows = [build_email_template_row(obj) for obj in page.object_list]
    elif config.model is Message:
        rows = [build_message_row(obj) for obj in page.object_list]
    elif is_taxonomy_model(config.model):
        rows = [build_taxonomy_row(config, obj) for obj in page.object_list]
    else:
        rows = [build_row(config, obj) for obj in page.object_list]
    if config.model is Outfit:
        template_name = "dashboard/outfit_list.html"
    elif config.model is Article:
        template_name = "dashboard/article_list.html"
    elif config.model is NewsletterSubscriber:
        template_name = "dashboard/newsletter_list.html"
    elif config.model is Order:
        template_name = "dashboard/order_list.html"
    elif config.model is OrderItem:
        template_name = "dashboard/order_item_list.html"
    elif config.model is ShippingMethod:
        template_name = "dashboard/shipping_method_list.html"
    elif config.model is DiscountCode:
        template_name = "dashboard/discount_code_list.html"
    elif config.model is AnalyticsSession:
        template_name = "dashboard/analytics_session_list.html"
    elif config.model is AnalyticsEvent:
        template_name = "dashboard/analytics_event_list.html"
    elif config.model is User:
        template_name = "dashboard/user_account_list.html"
    elif config.model is MessageTemplate:
        template_name = "dashboard/email_template_list.html"
    elif config.model is Message:
        template_name = "dashboard/message_list.html"
    elif is_taxonomy_model(config.model):
        template_name = "dashboard/taxonomy_list.html"
    else:
        template_name = "dashboard/model_list.html"
    return render(
        request,
        template_name,
        {
            "config": config,
            "rows": rows,
            "page": page,
            "query": query,
            "query_string": query_params.urlencode(),
            "active_filters": active_filters,
            "product_statuses": Product.STATUS_CHOICES if config.model is Product else None,
            "outfit_statuses": Outfit.STATUS_CHOICES if config.model is Outfit else None,
            "article_statuses": Article.STATUS_CHOICES if config.model is Article else None,
            "selected_status": request.GET.get("status", ""),
            "selected_featured": request.GET.get("featured", ""),
            "selected_category": request.GET.get("category", ""),
            "selected_stock": request.GET.get("stock", ""),
            "selected_quality": request.GET.get("quality", ""),
            "selected_visibility": request.GET.get("visibility", ""),
            "selected_source": request.GET.get("source", ""),
            "selected_period": request.GET.get("period", ""),
            "selected_state": request.GET.get("state", ""),
            "selected_device": request.GET.get("device", ""),
            "selected_event_type": request.GET.get("event_type", ""),
            "product_sort_headers": build_product_sort_headers(request) if config.model is Product else None,
            "outfit_summary": build_outfit_list_summary() if config.model is Outfit else None,
            "article_summary": build_article_list_summary() if config.model is Article else None,
            "article_categories": BlogCategory.objects.filter(is_active=True).order_by("sort_order", "name") if config.model is Article else None,
            "newsletter_summary": build_newsletter_summary() if config.model is NewsletterSubscriber else None,
            "newsletter_sources": get_newsletter_source_choices() if config.model is NewsletterSubscriber else None,
            "newsletter_periods": get_newsletter_period_choices() if config.model is NewsletterSubscriber else None,
            "newsletter_source_rows": build_newsletter_source_rows() if config.model is NewsletterSubscriber else None,
            "newsletter_active_emails": build_newsletter_active_email_list() if config.model is NewsletterSubscriber else "",
            "order_summary": build_order_summary() if config.model is Order else None,
            "order_statuses": get_order_status_choices() if config.model is Order else None,
            "order_periods": get_order_period_choices() if config.model is Order else None,
            "order_status_rows": build_order_status_rows() if config.model is Order else None,
            "order_item_summary": build_order_item_summary() if config.model is OrderItem else None,
            "shipping_summary": build_shipping_method_summary() if config.model is ShippingMethod else None,
            "shipping_state_choices": get_shipping_method_state_choices() if config.model is ShippingMethod else None,
            "discount_summary": build_discount_code_summary() if config.model is DiscountCode else None,
            "discount_state_choices": get_discount_code_state_choices() if config.model is DiscountCode else None,
            "analytics_session_summary": build_analytics_session_summary() if config.model is AnalyticsSession else None,
            "analytics_event_summary": build_analytics_event_summary() if config.model is AnalyticsEvent else None,
            "analytics_device_choices": get_analytics_device_choices() if config.model in {AnalyticsSession, AnalyticsEvent} else None,
            "analytics_period_choices": get_analytics_period_choices() if config.model in {AnalyticsSession, AnalyticsEvent} else None,
            "analytics_source_choices": get_analytics_source_choices() if config.model is AnalyticsSession else None,
            "analytics_event_type_choices": get_analytics_event_type_choices() if config.model is AnalyticsEvent else None,
            "taxonomy": build_taxonomy_list_context(config) if is_taxonomy_model(config.model) else None,
            "user_summary": build_user_account_summary() if config.model is User else None,
            "message_summary": build_message_summary() if config.model is Message else None,
            "selected_box": request.GET.get("box", ""),
            "user_type_choices": get_user_account_type_choices() if config.model is User else None,
            "selected_account_type": request.GET.get("account_type", ""),
            "sections": get_sections(),
        },
    )


def seed_variant_opening_balances(variant_formset, user):
    """Dla nowo utworzonych wariantów zapisuje początkowy stan jako wpis magazynowy.

    Pierwsze wprowadzenie ilości w zakładce Produkty jest bilansem otwarcia; dalsze zmiany
    stanu robi się już przez przyjęcia w Magazynie.
    """
    for variant in variant_formset.new_objects:
        if variant.stock_quantity:
            StockEntry.objects.create(
                variant=variant,
                direction=StockEntry.DIRECTION_IN,
                source=StockEntry.SOURCE_OPENING,
                quantity=variant.stock_quantity,
                created_by=user if getattr(user, "pk", None) else None,
            )


def seed_product_low_stock_defaults(form):
    """Ustawia początkowe wartości „ostatnich sztuk” dla nowego produktu na bazie Ustawień strony."""
    settings_obj = SiteSettings.load()
    if "disable_low_stock_badge" in form.fields:
        form.initial.setdefault("disable_low_stock_badge", not settings_obj.low_stock_default_enabled)
    if "low_stock_threshold" in form.fields:
        form.initial.setdefault("low_stock_threshold", settings_obj.low_stock_threshold)


@staff_required
@require_http_methods(["GET", "POST"])
def model_create(request, model_slug):
    config = get_required_config(model_slug)
    if config.readonly:
        messages.info(request, "Dane analityczne są zapisywane automatycznie i nie można dodawać ich ręcznie.")
        return redirect("dashboard:model_list", model_slug=config.slug)
    if config.model is Product:
        return redirect("dashboard:product_create_workspace")
    if config.model is Outfit:
        return redirect("dashboard:outfit_create_workspace")
    if config.model is Article:
        return redirect("dashboard:article_create_workspace")
    if config.model is Order:
        return redirect("dashboard:order_create_workspace")
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None)
    if config.model is Product and request.method != "POST":
        seed_product_low_stock_defaults(form)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    if config.model is NewsletterSubscriber:
        template_name = "dashboard/newsletter_form.html"
    elif config.model is ShippingMethod:
        template_name = "dashboard/shipping_method_form.html"
    elif config.model is DiscountCode:
        template_name = "dashboard/discount_code_form.html"
    else:
        template_name = "dashboard/taxonomy_form.html" if is_taxonomy_model(config.model) else "dashboard/model_form.html"
    return render(
        request,
        template_name,
        {
            "config": config,
            "form": form,
            "object": None,
            "mode": "create",
            "newsletter_detail": build_newsletter_detail_context(None) if config.model is NewsletterSubscriber else None,
            "shipping_detail": build_shipping_method_detail_context(None) if config.model is ShippingMethod else None,
            "discount_detail": build_discount_code_detail_context(None) if config.model is DiscountCode else None,
            "taxonomy": build_taxonomy_detail_context(config, None) if is_taxonomy_model(config.model) else None,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_edit(request, model_slug, pk):
    config = get_required_config(model_slug)
    if config.model is Outfit:
        return redirect("dashboard:outfit_workspace", pk=pk)
    if config.model is Article:
        return redirect("dashboard:article_workspace", pk=pk)
    if config.model is Order:
        return redirect("dashboard:order_workspace", pk=pk)
    if config.model is OrderItem:
        return redirect("dashboard:order_item_detail", pk=pk)
    if config.model is AnalyticsSession:
        session = get_object_or_404(
            AnalyticsSession.objects.prefetch_related("events__product", "events__variant"),
            pk=pk,
        )
        return render(
            request,
            "dashboard/analytics_session_detail.html",
            {
                "config": config,
                "session_detail": build_analytics_session_detail(session),
                "sections": get_sections(),
            },
        )
    if config.model is AnalyticsEvent:
        event = get_object_or_404(
            AnalyticsEvent.objects.select_related("session", "product", "variant"),
            pk=pk,
        )
        return render(
            request,
            "dashboard/analytics_event_detail.html",
            {
                "config": config,
                "event_detail": build_analytics_event_detail(event),
                "sections": get_sections(),
            },
        )
    obj = get_object_or_404(config.model, pk=pk)
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    if config.model is NewsletterSubscriber:
        template_name = "dashboard/newsletter_form.html"
    elif config.model is ShippingMethod:
        template_name = "dashboard/shipping_method_form.html"
    elif config.model is DiscountCode:
        template_name = "dashboard/discount_code_form.html"
    else:
        template_name = "dashboard/taxonomy_form.html" if is_taxonomy_model(config.model) else "dashboard/model_form.html"
    return render(
        request,
        template_name,
        {
            "config": config,
            "form": form,
            "object": obj,
            "mode": "edit",
            "newsletter_detail": build_newsletter_detail_context(obj) if config.model is NewsletterSubscriber else None,
            "shipping_detail": build_shipping_method_detail_context(obj) if config.model is ShippingMethod else None,
            "discount_detail": build_discount_code_detail_context(obj) if config.model is DiscountCode else None,
            "taxonomy": build_taxonomy_detail_context(config, obj) if is_taxonomy_model(config.model) else None,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_delete(request, model_slug, pk):
    config = get_required_config(model_slug)
    if config.readonly:
        messages.info(request, "Dane analityczne są tylko do odczytu i nie można usuwać ich pojedynczo z panelu.")
        return redirect("dashboard:model_list", model_slug=config.slug)
    obj = get_object_or_404(config.model, pk=pk)
    if request.method == "POST":
        label = str(obj)
        try:
            obj.delete()
            messages.success(request, f"Usunięto: {label}")
        except ProtectedError:
            messages.error(request, "Nie można usunąć tego obiektu, bo jest powiązany z innymi danymi.")
        return redirect("dashboard:model_list", model_slug=config.slug)

    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "config": config,
            "object": obj,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def product_create_workspace(request):
    product = Product()
    product_form = ProductDashboardForm(request.POST or None, request.FILES or None, instance=product, prefix="product")

    if request.method == "POST":
        if product_form.is_valid():
            product = product_form.save()
            messages.success(request, "Produkt utworzony. Teraz dodaj warianty i zdjęcia.")
            return redirect("dashboard:product_workspace", pk=product.pk)
        messages.error(request, "Nie udało się utworzyć produktu. Sprawdź błędy w formularzu.")
    else:
        seed_product_low_stock_defaults(product_form)

    return render(
        request,
        "dashboard/product_workspace.html",
        {
            "product": None,
            "product_form": product_form,
            "variant_formset": None,
            "image_formset": None,
            "quality_issues": None,
            "fieldsets": build_product_fieldsets(product_form),
            "featured_field": product_form["is_featured"],
            "image_accept": PRODUCT_IMAGE_ACCEPT,
            "product_stats": None,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def product_workspace(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "aesthetics",
            "images__variant",
            "variants__color",
            "variants__size",
            "data_quality_issues",
        ),
        pk=pk,
    )
    product_form = ProductDashboardForm(request.POST or None, instance=product, prefix="product")
    variant_formset = ProductVariantFormSet(
        request.POST or None,
        instance=product,
        prefix="variants",
        queryset=ProductVariant.objects.filter(product=product).select_related("color", "size"),
    )
    image_formset = ProductImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=product,
        prefix="images",
        queryset=ProductImage.objects.filter(product=product).select_related("variant"),
    )
    limit_image_variants(image_formset, product)

    if request.method == "POST":
        new_image_files, rejected_image_names = filter_product_image_files(request.FILES.getlist("new_images"))
        if product_form.is_valid() and variant_formset.is_valid() and image_formset.is_valid():
            if rejected_image_names:
                messages.error(
                    request,
                    "Nie dodano części zdjęć. Dozwolone formaty: WEBP, JPG, JPEG i PNG. "
                    f"Sprawdź pliki: {', '.join(rejected_image_names)}.",
                )
            else:
                with transaction.atomic():
                    product = product_form.save()
                    variant_formset.instance = product
                    variant_formset.save()
                    image_formset.instance = product
                    image_formset.save()
                    delete_workspace_images(product, request.POST.get("deleted_image_ids", ""))
                    delete_workspace_variants(product, request.POST.get("deleted_variant_ids", ""))
                    create_product_images(product, new_image_files)
                    sync_product_main_image(product)
                    seed_variant_opening_balances(variant_formset, request.user)
                    for variant in ProductVariant.objects.filter(product=product):
                        recalculate_variant_stock(variant)
                    refresh_product_quality_issues(product)
                messages.success(request, "Produkt zapisany razem z wariantami i zdjęciami.")
                return redirect("dashboard:product_workspace", pk=product.pk)
        messages.error(request, "Nie udało się zapisać produktu. Sprawdź błędy w formularzu.")

    quality_issues = refresh_product_quality_issues(product)
    return render(
        request,
        "dashboard/product_workspace.html",
        {
            "product": product,
            "product_form": product_form,
            "variant_formset": variant_formset,
            "image_formset": image_formset,
            "quality_issues": quality_issues,
            "fieldsets": build_product_fieldsets(product_form),
            "featured_field": product_form["is_featured"],
            "image_accept": PRODUCT_IMAGE_ACCEPT,
            "product_stats": build_product_workspace_stats(product),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def outfit_create_workspace(request):
    outfit = Outfit()
    outfit_form = OutfitDashboardForm(request.POST or None, instance=outfit, prefix="outfit")

    if request.method == "POST":
        if outfit_form.is_valid():
            outfit = outfit_form.save()
            messages.success(request, "Stylizacja utworzona. Teraz możesz dodać produkty i zdjęcia.")
            return redirect("dashboard:outfit_workspace", pk=outfit.pk)
        messages.error(request, "Nie udało się utworzyć stylizacji. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/outfit_workspace.html",
        {
            "outfit": None,
            "outfit_form": outfit_form,
            "item_formset": None,
            "image_formset": None,
            "fieldsets": build_outfit_fieldsets(outfit_form),
            "featured_field": outfit_form["is_featured"],
            "image_accept": PRODUCT_IMAGE_ACCEPT,
            "outfit_summary": build_outfit_workspace_summary(outfit),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def outfit_workspace(request, pk):
    outfit = get_object_or_404(
        Outfit.objects.prefetch_related(
            "aesthetics",
            "images",
            "items__product",
            "items__variant",
        ),
        pk=pk,
    )
    outfit_form = OutfitDashboardForm(request.POST or None, instance=outfit, prefix="outfit")
    item_formset = OutfitItemFormSet(
        request.POST or None,
        instance=outfit,
        prefix="items",
        queryset=OutfitItem.objects.filter(outfit=outfit).select_related("product", "variant"),
    )
    image_formset = OutfitImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=outfit,
        prefix="images",
        queryset=OutfitImage.objects.filter(outfit=outfit),
    )
    hotspot_formset = OutfitHotspotFormSet(
        request.POST or None,
        instance=outfit,
        prefix="hotspots",
        queryset=OutfitHotspot.objects.filter(outfit=outfit).select_related("product"),
    )

    if request.method == "POST":
        new_image_files, rejected_image_names = filter_product_image_files(request.FILES.getlist("new_images"))
        if (
            outfit_form.is_valid()
            and item_formset.is_valid()
            and image_formset.is_valid()
            and hotspot_formset.is_valid()
        ):
            if rejected_image_names:
                messages.error(
                    request,
                    "Nie dodano części zdjęć. Dozwolone formaty: WEBP, JPG, JPEG i PNG. "
                    f"Sprawdź pliki: {', '.join(rejected_image_names)}.",
                )
            else:
                with transaction.atomic():
                    outfit = outfit_form.save()
                    item_formset.instance = outfit
                    item_formset.save()
                    image_formset.instance = outfit
                    image_formset.save()
                    hotspot_formset.instance = outfit
                    hotspot_formset.save()
                    delete_workspace_outfit_images(outfit, request.POST.get("deleted_image_ids", ""))
                    delete_workspace_outfit_items(outfit, request.POST.get("deleted_item_ids", ""))
                    delete_workspace_outfit_hotspots(outfit, request.POST.get("deleted_hotspot_ids", ""))
                    create_outfit_images(outfit, new_image_files)
                    sync_outfit_main_image(outfit)
                messages.success(request, "Stylizacja zapisana razem z produktami i zdjęciami.")
                return redirect("dashboard:outfit_workspace", pk=outfit.pk)
        messages.error(request, "Nie udało się zapisać stylizacji. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/outfit_workspace.html",
        {
            "outfit": outfit,
            "outfit_form": outfit_form,
            "item_formset": item_formset,
            "image_formset": image_formset,
            "hotspot_formset": hotspot_formset,
            "hotspot_product_catalog": build_order_product_catalog_data(),
            "fieldsets": build_outfit_fieldsets(outfit_form),
            "featured_field": outfit_form["is_featured"],
            "image_accept": PRODUCT_IMAGE_ACCEPT,
            "outfit_summary": build_outfit_workspace_summary(outfit),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def article_create_workspace(request):
    article = Article()
    article_form = ArticleDashboardForm(request.POST or None, request.FILES or None, instance=article, prefix="article")

    if request.method == "POST":
        if article_form.is_valid():
            article = article_form.save()
            messages.success(request, "Poradnik utworzony. Możesz teraz dopracować treść, SEO i powiązania.")
            return redirect("dashboard:article_workspace", pk=article.pk)
        messages.error(request, "Nie udało się utworzyć poradnika. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/article_workspace.html",
        {
            "article": None,
            "article_form": article_form,
            "fieldsets": build_article_fieldsets(article_form),
            "publication_fields": build_article_publication_fields(article_form),
            "cover_fields": build_article_cover_fields(article_form),
            "seo_fields": build_article_seo_fields(article_form),
            "article_summary": build_article_workspace_summary(article),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def article_workspace(request, pk):
    article = get_object_or_404(
        Article.objects.select_related("category").prefetch_related("aesthetics", "products", "outfits"),
        pk=pk,
    )
    article_form = ArticleDashboardForm(request.POST or None, request.FILES or None, instance=article, prefix="article")

    if request.method == "POST":
        if article_form.is_valid():
            article = article_form.save()
            messages.success(request, "Poradnik zapisany.")
            return redirect("dashboard:article_workspace", pk=article.pk)
        messages.error(request, "Nie udało się zapisać poradnika. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/article_workspace.html",
        {
            "article": article,
            "article_form": article_form,
            "fieldsets": build_article_fieldsets(article_form),
            "publication_fields": build_article_publication_fields(article_form),
            "cover_fields": build_article_cover_fields(article_form),
            "seo_fields": build_article_seo_fields(article_form),
            "article_summary": build_article_workspace_summary(article),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def order_create_workspace(request):
    order = Order()
    order_form = OrderDashboardForm(request.POST or None, instance=order, prefix="order")

    if request.method == "POST":
        if order_form.is_valid():
            order = order_form.save()
            messages.success(request, "Zamówienie utworzone. Możesz teraz uzupełnić pozycje innymi narzędziami panelu.")
            return redirect("dashboard:order_workspace", pk=order.pk)
        messages.error(request, "Nie udało się utworzyć zamówienia. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/order_workspace.html",
        {
            "order": None,
            "order_form": order_form,
            "item_formset": None,
            "fieldsets": build_order_fieldsets(order_form),
            "order_detail": build_order_detail_context(order),
            "order_product_catalog": {},
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def order_workspace(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("user", "shipping_method", "discount_code").prefetch_related(
            "items__product",
            "items__variant",
            "items__product__images",
        ),
        pk=pk,
    )
    order_form = OrderDashboardForm(request.POST or None, instance=order, prefix="order")
    item_formset = OrderItemFormSet(
        request.POST or None,
        instance=order,
        prefix="items",
        queryset=OrderItem.objects.filter(order=order).select_related("product", "variant").prefetch_related("product__images"),
    )

    if request.method == "POST":
        if order_form.is_valid() and item_formset.is_valid():
            with transaction.atomic():
                order = order_form.save()
                item_formset.instance = order
                item_formset.save()
                sync_order_totals_from_items(order)
            messages.success(request, "Zamówienie zapisane razem z pozycjami.")
            return redirect("dashboard:order_workspace", pk=order.pk)
        messages.error(request, "Nie udało się zapisać zamówienia. Sprawdź błędy w formularzu.")

    order_detail = build_order_detail_context(order)
    return render(
        request,
        "dashboard/order_workspace.html",
        {
            "order": order,
            "order_form": order_form,
            "item_formset": item_formset,
            "fieldsets": build_order_fieldsets(order_form),
            "order_detail": order_detail,
            "order_product_catalog": build_order_product_catalog_data(),
            "sections": get_sections(),
        },
    )


@staff_required
def order_item_detail(request, pk):
    item = get_object_or_404(
        OrderItem.objects.select_related("order", "product", "variant").prefetch_related("product__images"),
        pk=pk,
    )
    return render(
        request,
        "dashboard/order_item_detail.html",
        {
            "item": item,
            "item_detail": build_order_item_detail_context(item),
            "sections": get_sections(),
        },
    )


def build_stock_entry_row(entry):
    invoice_url = ""
    if entry.invoice:
        try:
            invoice_url = entry.invoice.url
        except ValueError:
            invoice_url = ""
    return {
        "object": entry,
        "occurred_at": entry.occurred_at,
        "direction": entry.direction,
        "is_in": entry.direction == StockEntry.DIRECTION_IN,
        "source_label": entry.get_source_display(),
        "signed_quantity": entry.signed_quantity,
        "quantity": entry.quantity,
        "unit_price_net": entry.unit_price_net,
        "vat_rate": entry.vat_rate,
        "unit_price_gross": entry.unit_price_gross,
        "customs_amount": entry.customs_amount,
        "invoice_url": invoice_url,
        "supplier_url": entry.supplier_url,
        "note": entry.note,
        "created_by": entry.created_by,
        "delete_url": reverse("dashboard:warehouse_delete_entry", args=[entry.pk]),
    }


def build_warehouse_variant(variant):
    entries = list(variant.stock_entries.all())
    return {
        "object": variant,
        "label": str(variant),
        "color": variant.color.name if variant.color else "",
        "size": variant.size.name if variant.size else "",
        "sku": variant.sku or "",
        "is_active": variant.is_active,
        "stock_quantity": variant.stock_quantity,
        "entries": [build_stock_entry_row(entry) for entry in entries],
        "entry_count": len(entries),
        "add_entry_url": reverse("dashboard:warehouse_add_entry", args=[variant.pk]),
    }


def build_warehouse_row(product):
    image = product.main_image
    image_url = ""
    if image and image.image:
        try:
            image_url = image.image.url
        except ValueError:
            image_url = ""
    variants = [build_warehouse_variant(v) for v in product.variants.all()]
    return {
        "object": product,
        "name": product.name,
        "category": product.category,
        "admin_url": reverse("dashboard:product_workspace", args=[product.pk]),
        "image_url": image_url,
        "image_alt": (image.alt_text or product.name) if image else product.name,
        "variants": variants,
        "variant_count": len(variants),
        "total_stock": sum(v["stock_quantity"] for v in variants),
    }


@staff_required
def warehouse(request):
    queryset = (
        Product.objects.select_related("category")
        .prefetch_related(
            "images",
            "variants__color",
            "variants__size",
            "variants__stock_entries__created_by",
        )
        .order_by("name")
    )
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(name__icontains=query)

    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    rows = [build_warehouse_row(product) for product in page.object_list]
    return render(
        request,
        "dashboard/warehouse.html",
        {
            "rows": rows,
            "page": page,
            "query": query,
            "query_string": query_params.urlencode(),
            "stock_entry_form": StockEntryForm(),
            "sections": get_sections(),
        },
    )


@staff_required
@require_POST
def warehouse_add_entry(request, pk):
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=pk)
    form = StockEntryForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            entry = form.save(commit=False)
            entry.variant = variant
            entry.direction = StockEntry.DIRECTION_IN
            entry.created_by = request.user
            entry.save()
            recalculate_variant_stock(variant)
        messages.success(request, f"Dodano przyjęcie: {variant} × {entry.quantity}.")
    else:
        error_summary = "; ".join(
            f"{form.fields[field].label or field}: {', '.join(errors)}"
            for field, errors in form.errors.items()
        )
        messages.error(request, f"Nie udało się dodać przyjęcia. {error_summary}")
    return redirect(request.POST.get("next") or "dashboard:warehouse")


@staff_required
@require_POST
def warehouse_delete_entry(request, pk):
    entry = get_object_or_404(StockEntry.objects.select_related("variant"), pk=pk)
    variant = entry.variant
    entry.delete()
    recalculate_variant_stock(variant)
    messages.success(request, "Usunięto wpis magazynowy.")
    return redirect(request.POST.get("next") or "dashboard:warehouse")


@staff_required
@require_POST
def refresh_quality(request):
    total_open = refresh_all_product_quality_issues()
    messages.success(request, f"Odświeżono jakość danych. Otwarte problemy: {total_open}.")
    next_url = request.POST.get("next") or reverse("dashboard:model_list", args=["data-quality-issues"])
    return redirect(next_url)


def get_required_config(model_slug):
    config = get_model_config(model_slug)
    if config is None:
        raise Http404(f"Unknown dashboard model: {model_slug}")
    return config


def apply_product_admin_filters(request, queryset, active_filters):
    selected_status = request.GET.get("status", "").strip()
    selected_stock = request.GET.get("stock", "").strip()
    selected_quality = request.GET.get("quality", "").strip()

    if selected_status:
        queryset = queryset.filter(status=selected_status)
        active_filters.append(f"Status: {get_product_status_label(selected_status)}")
    if selected_stock == "available":
        queryset = queryset.filter(variants__is_active=True, variants__stock_quantity__gt=0)
        active_filters.append("Dostępne")
    elif selected_stock == "sold_out":
        queryset = queryset.exclude(variants__is_active=True, variants__stock_quantity__gt=0)
        active_filters.append("Wyprzedane")
    if selected_quality == "issues":
        queryset = queryset.filter(data_quality_issues__status=DataQualityIssue.STATUS_OPEN)
        active_filters.append("Z problemami danych")

    return queryset


def apply_outfit_admin_filters(request, queryset, active_filters):
    selected_status = request.GET.get("status", "").strip()
    selected_featured = request.GET.get("featured", "").strip()

    if selected_status:
        queryset = queryset.filter(status=selected_status)
        active_filters.append(f"Status: {get_outfit_status_label(selected_status)}")
    if selected_featured == "yes":
        queryset = queryset.filter(is_featured=True)
        active_filters.append("Polecane")
    elif selected_featured == "no":
        queryset = queryset.filter(is_featured=False)
        active_filters.append("Niepolecane")

    return queryset


def apply_article_admin_filters(request, queryset, active_filters):
    selected_status = request.GET.get("status", "").strip()
    selected_featured = request.GET.get("featured", "").strip()
    selected_category = request.GET.get("category", "").strip()

    if selected_status:
        queryset = queryset.filter(status=selected_status)
        active_filters.append(f"Status: {get_article_status_label(selected_status)}")
    if selected_featured == "yes":
        queryset = queryset.filter(is_featured=True)
        active_filters.append("Wyróżnione")
    elif selected_featured == "no":
        queryset = queryset.filter(is_featured=False)
        active_filters.append("Niewyróżnione")
    if selected_category:
        queryset = queryset.filter(category_id=selected_category)
        category_name = BlogCategory.objects.filter(pk=selected_category).values_list("name", flat=True).first()
        if category_name:
            active_filters.append(f"Kategoria: {category_name}")

    return queryset


def apply_newsletter_admin_filters(request, queryset, active_filters):
    selected_status = request.GET.get("status", "").strip()
    selected_source = request.GET.get("source", "").strip()
    selected_period = request.GET.get("period", "").strip()

    if selected_status == "active":
        queryset = queryset.filter(is_active=True, unsubscribed_at__isnull=True)
        active_filters.append("Aktywne")
    elif selected_status == "inactive":
        queryset = queryset.filter(Q(is_active=False) | Q(unsubscribed_at__isnull=False))
        active_filters.append("Nieaktywne")

    if selected_source:
        queryset = queryset.filter(source=selected_source)
        active_filters.append(f"Źródło: {get_newsletter_source_label(selected_source)}")

    if selected_period in {"7", "30", "90"}:
        days = int(selected_period)
        queryset = queryset.filter(subscribed_at__gte=timezone.now() - timedelta(days=days))
        active_filters.append(f"Ostatnie {days} dni")

    return queryset


def apply_order_admin_filters(request, queryset, active_filters):
    selected_status = request.GET.get("status", "").strip()
    selected_period = request.GET.get("period", "").strip()

    if selected_status:
        queryset = queryset.filter(status=selected_status)
        active_filters.append(f"Status: {get_order_status_label(selected_status)}")

    if selected_period in {"7", "30", "90"}:
        days = int(selected_period)
        queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=days))
        active_filters.append(f"Ostatnie {days} dni")

    return queryset


def apply_shipping_method_admin_filters(request, queryset, active_filters):
    selected_state = request.GET.get("state", "").strip()

    if selected_state == "active":
        queryset = queryset.filter(is_active=True)
        active_filters.append("Aktywne")
    elif selected_state == "inactive":
        queryset = queryset.filter(is_active=False)
        active_filters.append("Ukryte")
    elif selected_state == "free_from":
        queryset = queryset.filter(free_from_amount__isnull=False)
        active_filters.append("Z progiem darmowej dostawy")

    return queryset


def apply_discount_code_admin_filters(request, queryset, active_filters):
    selected_state = request.GET.get("state", "").strip()
    now = timezone.now()

    if selected_state == "active":
        queryset = queryset.filter(get_discount_current_query(now))
        active_filters.append("Aktywne teraz")
    elif selected_state == "inactive":
        queryset = queryset.filter(is_active=False)
        active_filters.append("Wyłączone")
    elif selected_state == "expired":
        queryset = queryset.filter(ends_at__lt=now)
        active_filters.append("Po terminie")
    elif selected_state == "limited":
        queryset = queryset.filter(max_uses__isnull=False)
        active_filters.append("Z limitem użyć")

    return queryset


def apply_analytics_session_filters(request, queryset, active_filters):
    selected_device = request.GET.get("device", "").strip()
    selected_source = request.GET.get("source", "").strip()
    selected_period = request.GET.get("period", "").strip()

    if selected_device:
        queryset = queryset.filter(device_type=selected_device)
        active_filters.append(f"Urządzenie: {get_analytics_device_label(selected_device)}")

    if selected_source == "direct":
        queryset = queryset.filter(referrer="", utm_source="")
        active_filters.append("Źródło: wejście bezpośrednie")
    elif selected_source == "campaign":
        queryset = queryset.exclude(utm_source="")
        active_filters.append("Źródło: kampania UTM")
    elif selected_source == "referral":
        queryset = queryset.exclude(referrer="").filter(utm_source="")
        active_filters.append("Źródło: strona odsyłająca")

    if selected_period in {"1", "7", "30", "90"}:
        days = int(selected_period)
        queryset = queryset.filter(last_seen_at__gte=timezone.now() - timedelta(days=days))
        active_filters.append("Ostatnie 24 godziny" if days == 1 else f"Ostatnie {days} dni")

    return queryset


def apply_analytics_event_filters(request, queryset, active_filters):
    selected_event_type = request.GET.get("event_type", "").strip()
    selected_device = request.GET.get("device", "").strip()
    selected_period = request.GET.get("period", "").strip()

    if selected_event_type:
        queryset = queryset.filter(event_type=selected_event_type)
        active_filters.append(f"Zdarzenie: {get_analytics_event_type_label(selected_event_type)}")
    if selected_device:
        queryset = queryset.filter(session__device_type=selected_device)
        active_filters.append(f"Urządzenie: {get_analytics_device_label(selected_device)}")
    if selected_period in {"1", "7", "30", "90"}:
        days = int(selected_period)
        queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=days))
        active_filters.append("Ostatnie 24 godziny" if days == 1 else f"Ostatnie {days} dni")

    return queryset


def get_discount_current_query(now):
    return (
        Q(is_active=True)
        & (Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        & (Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        & (Q(max_uses__isnull=True) | Q(used_count__lt=F("max_uses")))
    )


def get_product_status_label(status):
    return dict(Product.STATUS_CHOICES).get(status, status)


def get_outfit_status_label(status):
    return {
        Outfit.STATUS_DRAFT: "Szkic",
        Outfit.STATUS_ACTIVE: "Aktywna",
        Outfit.STATUS_ARCHIVED: "Archiwalna",
    }.get(status, status)


def get_article_status_label(status):
    return {
        Article.STATUS_DRAFT: "Szkic",
        Article.STATUS_PUBLISHED: "Opublikowany",
        Article.STATUS_ARCHIVED: "Archiwalny",
    }.get(status, status)


def get_newsletter_source_choices():
    return [
        (NewsletterSubscriber.SOURCE_FOOTER, "Stopka"),
        (NewsletterSubscriber.SOURCE_HOME, "Strona główna"),
        (NewsletterSubscriber.SOURCE_POPUP, "Popup"),
        (NewsletterSubscriber.SOURCE_OTHER, "Inne"),
    ]


def get_newsletter_source_label(source):
    return dict(get_newsletter_source_choices()).get(source, source)


def get_newsletter_period_choices():
    return [
        ("7", "Ostatnie 7 dni"),
        ("30", "Ostatnie 30 dni"),
        ("90", "Ostatnie 90 dni"),
    ]


def get_order_status_choices():
    return [
        (Order.STATUS_DRAFT, "Szkic"),
        (Order.STATUS_AWAITING_PAYMENT, "Oczekuje na płatność"),
        (Order.STATUS_PLACED, "Złożone"),
        (Order.STATUS_CONFIRMED, "Potwierdzone"),
        (Order.STATUS_PACKED, "Spakowane"),
        (Order.STATUS_SHIPPED, "Wysłane"),
        (Order.STATUS_CANCELLED, "Anulowane"),
    ]


def get_order_status_label(status):
    return dict(get_order_status_choices()).get(status, status)


def get_order_period_choices():
    return [
        ("7", "Ostatnie 7 dni"),
        ("30", "Ostatnie 30 dni"),
        ("90", "Ostatnie 90 dni"),
    ]


def get_order_status_class(status):
    return {
        Order.STATUS_DRAFT: "draft",
        Order.STATUS_AWAITING_PAYMENT: "draft",
        Order.STATUS_PLACED: "placed",
        Order.STATUS_CONFIRMED: "confirmed",
        Order.STATUS_PACKED: "packed",
        Order.STATUS_SHIPPED: "shipped",
        Order.STATUS_CANCELLED: "cancelled",
    }.get(status, "draft")


def get_shipping_method_state_choices():
    return [
        ("active", "Aktywne"),
        ("inactive", "Ukryte"),
        ("free_from", "Z darmową dostawą"),
    ]


def get_discount_code_state_choices():
    return [
        ("active", "Aktywne teraz"),
        ("inactive", "Wyłączone"),
        ("expired", "Po terminie"),
        ("limited", "Z limitem użyć"),
    ]


def get_analytics_device_choices():
    return [
        ("mobile", "Telefon"),
        ("desktop", "Komputer"),
        ("tablet", "Tablet"),
        ("unknown", "Nieznane"),
    ]


def get_analytics_device_label(device_type):
    normalized = (device_type or "").strip().lower()
    return dict(get_analytics_device_choices()).get(normalized, "Nieznane")


def get_analytics_period_choices():
    return [
        ("1", "Ostatnie 24 godziny"),
        ("7", "Ostatnie 7 dni"),
        ("30", "Ostatnie 30 dni"),
        ("90", "Ostatnie 90 dni"),
    ]


def get_analytics_source_choices():
    return [
        ("direct", "Wejście bezpośrednie"),
        ("campaign", "Kampania UTM"),
        ("referral", "Strona odsyłająca"),
    ]


def get_analytics_event_type_choices():
    return [
        (AnalyticsEvent.EVENT_PAGE_VIEW, "Wyświetlenie strony"),
        (AnalyticsEvent.EVENT_PRODUCT_VIEW, "Wyświetlenie produktu"),
        (AnalyticsEvent.EVENT_SEARCH, "Wyszukiwanie"),
        (AnalyticsEvent.EVENT_FILTER_APPLIED, "Użycie filtra"),
        (AnalyticsEvent.EVENT_ADD_TO_CART, "Dodanie do koszyka"),
        (AnalyticsEvent.EVENT_CART_VIEW, "Wyświetlenie koszyka"),
    ]


def get_analytics_event_type_label(event_type):
    return dict(get_analytics_event_type_choices()).get(event_type, event_type)


def get_analytics_event_type_class(event_type):
    return {
        AnalyticsEvent.EVENT_PAGE_VIEW: "page-view",
        AnalyticsEvent.EVENT_PRODUCT_VIEW: "product-view",
        AnalyticsEvent.EVENT_SEARCH: "search",
        AnalyticsEvent.EVENT_FILTER_APPLIED: "filter",
        AnalyticsEvent.EVENT_ADD_TO_CART: "cart",
        AnalyticsEvent.EVENT_CART_VIEW: "cart-view",
    }.get(event_type, "other")


def get_discount_type_label(discount_type):
    return {
        DiscountCode.TYPE_PERCENT: "Procent",
        DiscountCode.TYPE_FIXED: "Kwota",
    }.get(discount_type, discount_type)


def get_discount_status(discount_code):
    now = timezone.now()
    if not discount_code.is_active:
        return "Wyłączony", "archived"
    if discount_code.starts_at and discount_code.starts_at > now:
        return "Zaplanowany", "draft"
    if discount_code.ends_at and discount_code.ends_at < now:
        return "Po terminie", "archived"
    if discount_code.max_uses is not None and discount_code.used_count >= discount_code.max_uses:
        return "Wykorzystany", "archived"
    return "Aktywny", "active"


def format_admin_money(value):
    if value is None:
        return "Brak"
    return f"{value:.2f}".replace(".", ",") + " zł"


def format_admin_number(value):
    if value is None:
        return "Brak"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_discount_value(discount_code):
    if discount_code.discount_type == DiscountCode.TYPE_PERCENT:
        return f"{format_admin_number(discount_code.value)}%"
    return format_admin_money(discount_code.value)


def get_discount_usage_label(discount_code):
    if discount_code.max_uses is None:
        return f"{discount_code.used_count} / bez limitu"
    return f"{discount_code.used_count} / {discount_code.max_uses}"


def get_discount_date_label(discount_code):
    if discount_code.starts_at and discount_code.ends_at:
        return f"{discount_code.starts_at:%d.%m.%Y} - {discount_code.ends_at:%d.%m.%Y}"
    if discount_code.starts_at:
        return f"od {discount_code.starts_at:%d.%m.%Y}"
    if discount_code.ends_at:
        return f"do {discount_code.ends_at:%d.%m.%Y}"
    return "bez terminu"


def get_article_cover_url(article):
    if not article or not article.cover_image:
        return ""
    try:
        return article.cover_image.url
    except ValueError:
        return ""


def get_outfit_main_image(outfit):
    images = list(outfit.images.all())
    for image in images:
        if image.is_main:
            return image
    return images[0] if images else None


def calculate_outfit_products_total(outfit):
    if not getattr(outfit, "pk", None):
        return 0
    total = 0
    for item in outfit.items.all():
        total += item.unit_price * item.quantity
    return total


def calculate_outfit_discount(outfit, products_total=None):
    products_total = calculate_outfit_products_total(outfit) if products_total is None else products_total
    if outfit.bundle_price and products_total and outfit.bundle_price < products_total:
        return products_total - outfit.bundle_price
    return 0


def build_outfit_list_summary():
    outfits = Outfit.objects.all()
    return {
        "total_count": outfits.count(),
        "active_count": outfits.filter(status=Outfit.STATUS_ACTIVE).count(),
        "featured_count": outfits.filter(is_featured=True).count(),
        "with_promo_count": outfits.filter(bundle_price__isnull=False).count(),
    }


def build_outfit_row(outfit):
    image = get_outfit_main_image(outfit)
    image_url = ""
    if image and image.image:
        try:
            image_url = image.image.url
        except ValueError:
            image_url = ""
    products_total = calculate_outfit_products_total(outfit)
    discount = calculate_outfit_discount(outfit, products_total)
    return {
        "object": outfit,
        "admin_url": reverse("dashboard:outfit_workspace", args=[outfit.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["outfits", outfit.pk]),
        "preview_url": outfit.get_absolute_url(),
        "image_url": image_url,
        "image_alt": (image.alt_text or outfit.name) if image else outfit.name,
        "name": outfit.name,
        "short_description": outfit.short_description,
        "status": outfit.status,
        "status_label": get_outfit_status_label(outfit.status),
        "is_featured": outfit.is_featured,
        "aesthetics": list(outfit.aesthetics.all()[:3]),
        "item_count": outfit.items.count(),
        "image_count": outfit.images.count(),
        "products_total": products_total,
        "promo_price": outfit.bundle_price,
        "discount": discount,
    }


def build_outfit_workspace_summary(outfit):
    products_total = calculate_outfit_products_total(outfit)
    discount = calculate_outfit_discount(outfit, products_total)
    return {
        "products_total": products_total,
        "promo_price": getattr(outfit, "bundle_price", None),
        "discount": discount,
        "item_count": outfit.items.count() if getattr(outfit, "pk", None) else 0,
        "image_count": outfit.images.count() if getattr(outfit, "pk", None) else 0,
        "status_label": get_outfit_status_label(outfit.status) if getattr(outfit, "status", None) else "Szkic",
        "is_featured": bool(getattr(outfit, "is_featured", False)),
    }


def build_article_list_summary():
    articles = Article.objects.all()
    return {
        "total_count": articles.count(),
        "published_count": articles.filter(status=Article.STATUS_PUBLISHED).count(),
        "draft_count": articles.filter(status=Article.STATUS_DRAFT).count(),
        "featured_count": articles.filter(is_featured=True).count(),
        "with_cover_count": articles.exclude(cover_image="").count(),
    }


def build_article_row(article):
    cover_url = get_article_cover_url(article)
    return {
        "object": article,
        "admin_url": reverse("dashboard:article_workspace", args=[article.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["articles", article.pk]),
        "preview_url": article.get_absolute_url() if article.slug else "",
        "cover_url": cover_url,
        "cover_alt": article.title,
        "title": article.title,
        "intro": article.intro,
        "category": article.category,
        "status": article.status,
        "status_label": get_article_status_label(article.status),
        "is_featured": article.is_featured,
        "published_at": article.published_at,
        "updated_at": article.updated_at,
        "aesthetics": list(article.aesthetics.all()[:3]),
        "product_count": article.products.count(),
        "outfit_count": article.outfits.count(),
        "has_cover": bool(cover_url),
    }


def build_article_workspace_summary(article):
    return {
        "status_label": get_article_status_label(getattr(article, "status", Article.STATUS_DRAFT)),
        "category": getattr(article, "category", None),
        "is_featured": bool(getattr(article, "is_featured", False)),
        "published_at": getattr(article, "published_at", None),
        "product_count": article.products.count() if getattr(article, "pk", None) else 0,
        "outfit_count": article.outfits.count() if getattr(article, "pk", None) else 0,
        "aesthetic_count": article.aesthetics.count() if getattr(article, "pk", None) else 0,
        "cover_url": get_article_cover_url(article),
        "slug": getattr(article, "slug", ""),
    }


def build_newsletter_summary():
    subscribers = NewsletterSubscriber.objects.all()
    now = timezone.now()
    return {
        "total_count": subscribers.count(),
        "active_count": subscribers.filter(is_active=True, unsubscribed_at__isnull=True).count(),
        "inactive_count": subscribers.filter(Q(is_active=False) | Q(unsubscribed_at__isnull=False)).distinct().count(),
        "new_30_count": subscribers.filter(subscribed_at__gte=now - timedelta(days=30)).count(),
        "missing_consent_count": subscribers.filter(consent_text="").count(),
    }


def build_newsletter_source_rows():
    subscribers = NewsletterSubscriber.objects.all()
    rows = []
    max_active_count = 1
    counts_by_source = {}

    for value, label in get_newsletter_source_choices():
        source_queryset = subscribers.filter(source=value)
        active_count = source_queryset.filter(is_active=True, unsubscribed_at__isnull=True).count()
        counts_by_source[value] = active_count
        max_active_count = max(max_active_count, active_count)
        rows.append(
            {
                "value": value,
                "label": label,
                "total_count": source_queryset.count(),
                "active_count": active_count,
                "latest_at": source_queryset.order_by("-subscribed_at").values_list("subscribed_at", flat=True).first(),
            }
        )

    for row in rows:
        active_count = counts_by_source[row["value"]]
        row["bar_width"] = 0 if active_count == 0 else max(8, round((active_count / max_active_count) * 100))

    return rows


def build_newsletter_active_email_list():
    return ", ".join(
        NewsletterSubscriber.objects.filter(is_active=True, unsubscribed_at__isnull=True).order_by("email").values_list("email", flat=True)
    )


def build_newsletter_row(subscriber):
    is_sendable = subscriber.is_active and not subscriber.unsubscribed_at
    return {
        "object": subscriber,
        "admin_url": reverse("dashboard:model_edit", args=["newsletter-subscribers", subscriber.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["newsletter-subscribers", subscriber.pk]),
        "email": subscriber.email,
        "source": subscriber.source,
        "source_label": get_newsletter_source_label(subscriber.source),
        "is_active": subscriber.is_active,
        "is_sendable": is_sendable,
        "has_consent": bool(subscriber.consent_text),
        "status_label": "Aktywna" if subscriber.is_active else "Nieaktywna",
        "status_class": "active" if subscriber.is_active else "archived",
        "consent_text": subscriber.consent_text,
        "subscribed_at": subscriber.subscribed_at,
        "unsubscribed_at": subscriber.unsubscribed_at,
    }


def build_newsletter_detail_context(subscriber):
    if not subscriber:
        return {
            "status_label": "Nowy adres",
            "status_class": "draft",
            "source_label": "Nie wybrano",
            "is_sendable": False,
            "sendability_label": "po zapisie",
            "subscribed_at": None,
            "unsubscribed_at": None,
            "has_consent": False,
            "consent_text": "",
            "email": "",
        }

    return {
        "status_label": "Aktywna" if subscriber.is_active else "Nieaktywna",
        "status_class": "active" if subscriber.is_active else "archived",
        "source_label": get_newsletter_source_label(subscriber.source),
        "is_sendable": subscriber.is_active and not subscriber.unsubscribed_at,
        "sendability_label": "Tak" if subscriber.is_active and not subscriber.unsubscribed_at else "Nie",
        "subscribed_at": subscriber.subscribed_at,
        "unsubscribed_at": subscriber.unsubscribed_at,
        "has_consent": bool(subscriber.consent_text),
        "consent_text": subscriber.consent_text,
        "email": subscriber.email,
    }


def build_order_summary():
    orders = Order.objects.all()
    active_orders = orders.exclude(status__in=[Order.STATUS_DRAFT, Order.STATUS_CANCELLED])
    open_statuses = [Order.STATUS_PLACED, Order.STATUS_CONFIRMED, Order.STATUS_PACKED]
    now = timezone.now()
    return {
        "total_count": orders.count(),
        "open_count": orders.filter(status__in=open_statuses).count(),
        "new_30_count": orders.filter(created_at__gte=now - timedelta(days=30)).count(),
        "cancelled_count": orders.filter(status=Order.STATUS_CANCELLED).count(),
        "revenue_total": active_orders.aggregate(total=Sum("grand_total"))["total"] or 0,
    }


def build_order_status_rows():
    orders = Order.objects.all()
    rows = []
    max_count = 1
    counts = {}
    for value, label in get_order_status_choices():
        count = orders.filter(status=value).count()
        counts[value] = count
        max_count = max(max_count, count)
        rows.append(
            {
                "value": value,
                "label": label,
                "count": count,
                "class": get_order_status_class(value),
            }
        )
    for row in rows:
        count = counts[row["value"]]
        row["bar_width"] = 0 if count == 0 else max(8, round((count / max_count) * 100))
    return rows


def build_order_item_summary():
    items = OrderItem.objects.all()
    return {
        "total_count": items.count(),
        "quantity_count": items.aggregate(total=Sum("quantity"))["total"] or 0,
        "sales_total": items.aggregate(total=Sum("line_total"))["total"] or 0,
        "unique_products": items.values("product_id").distinct().count(),
    }


def build_shipping_method_summary():
    methods = ShippingMethod.objects.all()
    cheapest_price = methods.filter(is_active=True).order_by("price").values_list("price", flat=True).first()
    return {
        "total_count": methods.count(),
        "active_count": methods.filter(is_active=True).count(),
        "free_from_count": methods.filter(free_from_amount__isnull=False).count(),
        "cheapest_price": cheapest_price,
        "order_count": Order.objects.filter(shipping_method__isnull=False).count(),
    }


def build_shipping_method_row(method):
    return {
        "object": method,
        "admin_url": reverse("dashboard:model_edit", args=["shipping-methods", method.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["shipping-methods", method.pk]),
        "name": method.name,
        "code": method.code,
        "description": method.description,
        "price": method.price,
        "price_label": format_admin_money(method.price),
        "free_from_amount": method.free_from_amount,
        "free_from_label": format_admin_money(method.free_from_amount) if method.free_from_amount is not None else "Brak progu",
        "is_active": method.is_active,
        "status_label": "Aktywna" if method.is_active else "Ukryta",
        "status_class": "active" if method.is_active else "archived",
        "sort_order": method.sort_order,
        "order_count": getattr(method, "order_count", method.orders.count()),
    }


def build_shipping_method_detail_context(method):
    if not method:
        return {
            "status_label": "Nowa metoda",
            "status_class": "draft",
            "price_label": "po zapisie",
            "free_from_label": "opcjonalnie",
            "order_count": 0,
            "code": "utworzy się z nazwy",
            "description": "",
        }

    return {
        "status_label": "Aktywna" if method.is_active else "Ukryta",
        "status_class": "active" if method.is_active else "archived",
        "price_label": format_admin_money(method.price),
        "free_from_label": format_admin_money(method.free_from_amount) if method.free_from_amount is not None else "Brak progu",
        "order_count": method.orders.count(),
        "code": method.code,
        "description": method.description,
    }


def build_discount_code_summary():
    discounts = DiscountCode.objects.all()
    now = timezone.now()
    return {
        "total_count": discounts.count(),
        "active_count": discounts.filter(get_discount_current_query(now)).count(),
        "expired_count": discounts.filter(ends_at__lt=now).count(),
        "limited_count": discounts.filter(max_uses__isnull=False).count(),
        "used_count": discounts.aggregate(total=Sum("used_count"))["total"] or 0,
        "order_count": Order.objects.filter(discount_code__isnull=False).count(),
    }


def build_discount_code_row(discount_code):
    status_label, status_class = get_discount_status(discount_code)
    return {
        "object": discount_code,
        "admin_url": reverse("dashboard:model_edit", args=["discount-codes", discount_code.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["discount-codes", discount_code.pk]),
        "code": discount_code.code,
        "discount_type_label": get_discount_type_label(discount_code.discount_type),
        "value_label": format_discount_value(discount_code),
        "minimum_order_label": (
            format_admin_money(discount_code.minimum_order_amount)
            if discount_code.minimum_order_amount is not None
            else "Brak minimum"
        ),
        "usage_label": get_discount_usage_label(discount_code),
        "date_label": get_discount_date_label(discount_code),
        "is_active": discount_code.is_active,
        "status_label": status_label,
        "status_class": status_class,
        "order_count": getattr(discount_code, "order_count", discount_code.orders.count()),
        "created_at": discount_code.created_at,
    }


def build_discount_code_detail_context(discount_code):
    if not discount_code:
        return {
            "status_label": "Nowy kod",
            "status_class": "draft",
            "value_label": "po zapisie",
            "usage_label": "0 / bez limitu",
            "date_label": "bez terminu",
            "minimum_order_label": "opcjonalnie",
            "order_count": 0,
            "code": "np. SPOOKY10",
        }

    status_label, status_class = get_discount_status(discount_code)
    return {
        "status_label": status_label,
        "status_class": status_class,
        "value_label": format_discount_value(discount_code),
        "usage_label": get_discount_usage_label(discount_code),
        "date_label": get_discount_date_label(discount_code),
        "minimum_order_label": (
            format_admin_money(discount_code.minimum_order_amount)
            if discount_code.minimum_order_amount is not None
            else "Brak minimum"
        ),
        "order_count": discount_code.orders.count(),
        "code": discount_code.code,
    }


def build_analytics_session_summary():
    sessions = AnalyticsSession.objects.all()
    events = AnalyticsEvent.objects.all()
    now = timezone.now()
    return {
        "total_count": sessions.count(),
        "active_count": sessions.filter(last_seen_at__gte=now - timedelta(minutes=30)).count(),
        "last_24_count": sessions.filter(last_seen_at__gte=now - timedelta(days=1)).count(),
        "unique_visitors": count_unique_visitors(events),
        "campaign_count": sessions.exclude(utm_source="").count(),
        "event_count": events.count(),
    }


def build_analytics_event_summary():
    events = AnalyticsEvent.objects.all()
    now = timezone.now()
    return {
        "total_count": events.count(),
        "last_24_count": events.filter(created_at__gte=now - timedelta(days=1)).count(),
        "page_view_count": events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW).count(),
        "product_view_count": events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW).count(),
        "add_to_cart_count": events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART).count(),
        "session_count": events.values("session_id").distinct().count(),
    }


def build_analytics_session_row(session):
    events = sorted(list(session.events.all()), key=lambda event: event.created_at)
    first_event = events[0] if events else None
    last_event = events[-1] if events else None
    return {
        "object": session,
        "admin_url": reverse("dashboard:model_edit", args=["analytics-sessions", session.pk]),
        "session_key": session.session_key,
        "short_session_key": shorten_identifier(session.session_key),
        "visitor_id": session.visitor_id,
        "short_visitor_id": shorten_identifier(session.visitor_id) if session.visitor_id else "Brak",
        "device_label": get_analytics_device_label(session.device_type),
        "device_class": (session.device_type or "unknown").lower(),
        "source_label": get_analytics_source_label(session),
        "source_detail": get_analytics_source_detail(session),
        "first_seen_at": session.first_seen_at,
        "last_seen_at": session.last_seen_at,
        "duration_label": format_analytics_duration(session.first_seen_at, session.last_seen_at),
        "event_count": getattr(session, "event_count", len(events)),
        "page_view_count": getattr(session, "page_view_count", count_events(events, AnalyticsEvent.EVENT_PAGE_VIEW)),
        "product_view_count": getattr(session, "product_view_count", count_events(events, AnalyticsEvent.EVENT_PRODUCT_VIEW)),
        "add_to_cart_count": getattr(session, "add_to_cart_count", count_events(events, AnalyticsEvent.EVENT_ADD_TO_CART)),
        "entry_path": first_event.path if first_event else "Brak zdarzeń",
        "exit_path": last_event.path if last_event else "Brak zdarzeń",
        "is_active": session.last_seen_at >= timezone.now() - timedelta(minutes=30),
    }


def build_analytics_event_row(event):
    return {
        "object": event,
        "admin_url": reverse("dashboard:model_edit", args=["analytics-events", event.pk]),
        "session_url": reverse("dashboard:model_edit", args=["analytics-sessions", event.session_id]),
        "event_type": event.event_type,
        "event_type_label": get_analytics_event_type_label(event.event_type),
        "event_type_class": get_analytics_event_type_class(event.event_type),
        "path": event.path,
        "product": event.product,
        "variant": event.variant,
        "device_label": get_analytics_device_label(event.session.device_type),
        "source_label": get_analytics_source_label(event.session),
        "session_key": shorten_identifier(event.session.session_key),
        "metadata_summary": format_analytics_metadata_summary(event.metadata),
        "created_at": event.created_at,
    }


def build_analytics_session_detail(session):
    events = sorted(list(session.events.all()), key=lambda event: event.created_at)
    event_rows = [build_analytics_event_row(event) for event in events]
    counts = {
        event_type: count_events(events, event_type)
        for event_type, _label in get_analytics_event_type_choices()
    }
    return {
        "object": session,
        "session_key": session.session_key,
        "short_session_key": shorten_identifier(session.session_key),
        "visitor_id": session.visitor_id or "Brak",
        "device_label": get_analytics_device_label(session.device_type),
        "device_class": (session.device_type or "unknown").lower(),
        "source_label": get_analytics_source_label(session),
        "source_detail": get_analytics_source_detail(session),
        "referrer": session.referrer,
        "utm_source": session.utm_source,
        "utm_medium": session.utm_medium,
        "utm_campaign": session.utm_campaign,
        "user_agent": session.user_agent or "Brak danych",
        "first_seen_at": session.first_seen_at,
        "last_seen_at": session.last_seen_at,
        "duration_label": format_analytics_duration(session.first_seen_at, session.last_seen_at),
        "event_count": len(events),
        "page_view_count": counts[AnalyticsEvent.EVENT_PAGE_VIEW],
        "product_view_count": counts[AnalyticsEvent.EVENT_PRODUCT_VIEW],
        "add_to_cart_count": counts[AnalyticsEvent.EVENT_ADD_TO_CART],
        "cart_view_count": counts[AnalyticsEvent.EVENT_CART_VIEW],
        "entry_path": events[0].path if events else "Brak zdarzeń",
        "exit_path": events[-1].path if events else "Brak zdarzeń",
        "events": event_rows,
        "is_active": session.last_seen_at >= timezone.now() - timedelta(minutes=30),
    }


def build_analytics_event_detail(event):
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    product_url = reverse("dashboard:product_workspace", args=[event.product_id]) if event.product_id else ""
    return {
        "object": event,
        "event_type_label": get_analytics_event_type_label(event.event_type),
        "event_type_class": get_analytics_event_type_class(event.event_type),
        "path": event.path,
        "created_at": event.created_at,
        "product": event.product,
        "product_url": product_url,
        "variant": event.variant,
        "metadata": metadata,
        "metadata_rows": [{"key": key, "value": format_analytics_metadata_value(value)} for key, value in metadata.items()],
        "metadata_json": json.dumps(metadata, ensure_ascii=False, indent=2),
        "session_url": reverse("dashboard:model_edit", args=["analytics-sessions", event.session_id]),
        "session_key": event.session.session_key,
        "short_session_key": shorten_identifier(event.session.session_key),
        "visitor_id": event.session.visitor_id or "Brak",
        "device_label": get_analytics_device_label(event.session.device_type),
        "source_label": get_analytics_source_label(event.session),
        "source_detail": get_analytics_source_detail(event.session),
    }


def get_analytics_source_label(session):
    if session.utm_source:
        return session.utm_source
    if session.referrer:
        hostname = urlparse(session.referrer).hostname
        return hostname or session.referrer
    return "Wejście bezpośrednie"


def get_analytics_source_detail(session):
    if session.utm_source:
        details = [session.utm_medium, session.utm_campaign]
        return " · ".join(value for value in details if value) or "Kampania UTM"
    if session.referrer:
        return session.referrer
    return "Brak referrera i parametrów UTM"


def format_analytics_duration(start_at, end_at):
    if not start_at or not end_at:
        return "Brak danych"
    seconds = max(0, int((end_at - start_at).total_seconds()))
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} godz. {minutes} min"


def shorten_identifier(value, visible=10):
    value = str(value or "")
    if len(value) <= visible * 2 + 1:
        return value or "Brak"
    return f"{value[:visible]}…{value[-visible:]}"


def count_events(events, event_type):
    return sum(1 for event in events if event.event_type == event_type)


def format_analytics_metadata_summary(metadata):
    if not isinstance(metadata, dict) or not metadata:
        return "Brak dodatkowych danych"
    pairs = [f"{key}: {format_analytics_metadata_value(value)}" for key, value in list(metadata.items())[:3]]
    return " · ".join(pairs)


def format_analytics_metadata_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "Tak" if value else "Nie"
    if value in (None, ""):
        return "Brak"
    return str(value)


def build_order_product_catalog_data():
    products = Product.objects.prefetch_related(
        "images",
        "variants__color",
        "variants__size",
    ).order_by("name")
    data = {}
    for product in products:
        image = get_product_image_data(product)
        data[str(product.pk)] = {
            "name": product.name,
            "price": str(product.current_price),
            "image_url": image["url"],
            "image_alt": image["alt"],
            "variants": [
                {
                    "id": str(variant.pk),
                    "label": get_variant_snapshot_label(variant),
                    "sku": variant.sku or "",
                    "price": str(variant.price),
                }
                for variant in product.variants.all()
            ],
        }
    return data


def get_product_image_data(product):
    image = product.main_image if product else None
    if image and image.image:
        try:
            return {"url": image.image.url, "alt": image.alt_text or product.name}
        except ValueError:
            pass
    return {"url": "", "alt": product.name if product else ""}


def get_variant_snapshot_label(variant):
    parts = []
    if variant.color:
        parts.append(variant.color.name)
    if variant.size:
        parts.append(variant.size.name)
    return " / ".join(parts) or "Domyślny"


def build_order_row(order):
    items = list(order.items.all())
    quantity_count = sum(item.quantity for item in items)
    return {
        "object": order,
        "admin_url": reverse("dashboard:order_workspace", args=[order.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["orders", order.pk]),
        "order_number": order.order_number or f"Zamówienie #{order.pk}",
        "customer_name": get_order_customer_name(order),
        "email": order.email,
        "phone": order.phone,
        "status": order.status,
        "status_label": get_order_status_label(order.status),
        "status_class": get_order_status_class(order.status),
        "is_test": order.is_test,
        "city": order.shipping_city,
        "shipping_method": order.shipping_method,
        "grand_total": order.grand_total,
        "item_count": len(items),
        "quantity_count": quantity_count,
        "created_at": order.created_at,
        "placed_at": order.placed_at,
        "items_preview": [item.product_name for item in items[:3]],
        "has_more_items": len(items) > 3,
        "is_open": order.status in {Order.STATUS_PLACED, Order.STATUS_CONFIRMED, Order.STATUS_PACKED},
    }


def build_order_item_list_row(item):
    image = get_order_item_image(item)
    return {
        "object": item,
        "admin_url": reverse("dashboard:order_item_detail", args=[item.pk]),
        "delete_url": reverse("dashboard:model_delete", args=["order-items", item.pk]),
        "order_url": reverse("dashboard:order_workspace", args=[item.order_id]),
        "product_url": reverse("dashboard:product_workspace", args=[item.product_id]) if item.product_id else "",
        "order_number": item.order.order_number or f"Zamówienie #{item.order_id}",
        "order_status_label": get_order_status_label(item.order.status),
        "order_status_class": get_order_status_class(item.order.status),
        "customer_name": get_order_customer_name(item.order),
        "email": item.order.email,
        "product_name": item.product_name,
        "variant_name": item.variant_name,
        "sku": item.sku,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "line_total": item.line_total,
        "created_at": item.created_at,
        "image_url": image["url"],
        "image_alt": image["alt"],
    }


def build_order_item_detail_context(item):
    image = get_order_item_image(item)
    return {
        "image_url": image["url"],
        "image_alt": image["alt"],
        "order_number": item.order.order_number or f"Zamówienie #{item.order_id}",
        "order_url": reverse("dashboard:order_workspace", args=[item.order_id]),
        "product_url": reverse("dashboard:product_workspace", args=[item.product_id]) if item.product_id else "",
        "order_status_label": get_order_status_label(item.order.status),
        "order_status_class": get_order_status_class(item.order.status),
        "customer_name": get_order_customer_name(item.order),
        "email": item.order.email,
        "snapshot_rows": [
            {"label": "Nazwa w zamówieniu", "value": item.product_name},
            {"label": "Wariant w zamówieniu", "value": item.variant_name or "Brak"},
            {"label": "Kod wariantu", "value": item.sku or "Brak"},
            {"label": "Ilość", "value": item.quantity},
            {"label": "Cena za sztukę", "value": item.unit_price},
            {"label": "Razem", "value": item.line_total},
        ],
    }


def build_order_payment_info(order):
    if not getattr(order, "pk", None):
        return None
    payment = order.payments.order_by("-created_at").first()
    if payment is None:
        return None
    return {
        "status": payment.status,
        "status_label": payment.get_status_display(),
        "provider_label": payment.get_provider_display(),
        "method": payment.method,
        "amount": payment.amount,
        "p24_order_id": payment.p24_order_id,
        "paid_at": payment.paid_at,
        "is_paid": payment.is_paid,
    }


def build_order_detail_context(order):
    items = build_order_item_rows(order) if getattr(order, "pk", None) else []
    quantity_count = sum(item["quantity"] for item in items)
    return {
        "payment": build_order_payment_info(order),
        "order_number": getattr(order, "order_number", "") or (f"Zamówienie #{order.pk}" if getattr(order, "pk", None) else "Nowe zamówienie"),
        "customer_name": get_order_customer_name(order) if getattr(order, "pk", None) else "Nowa klientka",
        "status_label": get_order_status_label(getattr(order, "status", Order.STATUS_DRAFT)),
        "status_class": get_order_status_class(getattr(order, "status", Order.STATUS_DRAFT)),
        "is_test": getattr(order, "is_test", False),
        "item_count": len(items),
        "quantity_count": quantity_count,
        "items": items,
        "address_lines": get_order_address_lines(order),
        "timeline": build_order_timeline(order),
        "totals": build_order_total_rows(order),
        "steps": build_order_status_steps(getattr(order, "status", Order.STATUS_DRAFT)),
        "is_open": getattr(order, "status", Order.STATUS_DRAFT) in {Order.STATUS_PLACED, Order.STATUS_CONFIRMED, Order.STATUS_PACKED},
    }


def sync_order_totals_from_items(order):
    subtotal = order.items.aggregate(total=Sum("line_total"))["total"] or Decimal("0.00")
    order.subtotal = subtotal
    order.grand_total = max(Decimal("0.00"), subtotal - order.discount_total + order.shipping_total)
    order.save(update_fields=["subtotal", "grand_total", "updated_at"])


def build_order_item_rows(order):
    rows = []
    if not getattr(order, "pk", None):
        return rows
    for item in order.items.all():
        image = get_order_item_image(item)
        rows.append(
            {
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "image_url": image["url"],
                "image_alt": image["alt"],
                "product_url": reverse("dashboard:product_workspace", args=[item.product_id]) if item.product_id else "",
            }
        )
    return rows


def get_order_item_image(item):
    product = getattr(item, "product", None)
    image = product.main_image if product else None
    if image and image.image:
        try:
            return {"url": image.image.url, "alt": image.alt_text or item.product_name}
        except ValueError:
            pass
    return {"url": "", "alt": item.product_name}


def build_order_total_rows(order):
    return [
        {"label": "Produkty", "value": getattr(order, "subtotal", 0)},
        {"label": "Rabat", "value": getattr(order, "discount_total", 0)},
        {"label": "Dostawa", "value": getattr(order, "shipping_total", 0)},
        {"label": "Razem", "value": getattr(order, "grand_total", 0), "is_strong": True},
    ]


def build_order_timeline(order):
    if not getattr(order, "pk", None):
        return []
    return [
        {"label": "Utworzone", "date": order.created_at},
        {"label": "Złożone", "date": order.placed_at},
        {"label": "Ostatnia zmiana", "date": order.updated_at},
    ]


def build_order_status_steps(active_status):
    return [
        {
            "label": label,
            "value": value,
            "is_active": value == active_status,
            "class": get_order_status_class(value),
        }
        for value, label in get_order_status_choices()
    ]


def get_order_customer_name(order):
    first_name = getattr(order, "first_name", "") or ""
    last_name = getattr(order, "last_name", "") or ""
    name = f"{first_name} {last_name}".strip()
    return name or getattr(order, "email", "") or "Brak danych"


def get_order_address_lines(order):
    if not getattr(order, "pk", None):
        return []
    if getattr(order, "pickup_point_code", ""):
        lines = [
            f"Paczkomat {order.pickup_point_name or order.pickup_point_code}",
            order.pickup_point_address,
        ]
    else:
        lines = [
            order.shipping_address_line_1,
            order.shipping_address_line_2,
            f"{order.shipping_postal_code} {order.shipping_city}".strip(),
            order.shipping_country,
        ]
    return [line for line in lines if line]


def is_taxonomy_model(model):
    return model in {Category, Aesthetic, Color, Size, BlogCategory}


def prepare_taxonomy_queryset(model, queryset):
    if model is BlogCategory:
        return queryset.annotate(
            dashboard_article_count=Count("articles", distinct=True),
            dashboard_published_article_count=Count(
                "articles",
                filter=Q(articles__status=Article.STATUS_PUBLISHED),
                distinct=True,
            ),
            dashboard_featured_article_count=Count(
                "articles",
                filter=Q(articles__is_featured=True),
                distinct=True,
            ),
        ).order_by("sort_order", "name")
    if model is Category:
        return queryset.select_related("parent").annotate(
            dashboard_product_count=Count("products", distinct=True),
            dashboard_active_product_count=Count(
                "products",
                filter=Q(products__status=Product.STATUS_ACTIVE),
                distinct=True,
            ),
            dashboard_children_count=Count("children", distinct=True),
        ).order_by("name")
    if model is Aesthetic:
        return queryset.annotate(
            dashboard_product_count=Count("products", distinct=True),
            dashboard_active_product_count=Count(
                "products",
                filter=Q(products__status=Product.STATUS_ACTIVE),
                distinct=True,
            ),
        ).order_by("sort_order", "name")
    if model is Color:
        return queryset.annotate(
            dashboard_product_count=Count("variants__product", distinct=True),
            dashboard_active_product_count=Count(
                "variants__product",
                filter=Q(variants__product__status=Product.STATUS_ACTIVE),
                distinct=True,
            ),
            dashboard_variant_count=Count("variants", distinct=True),
        ).order_by("name")
    return queryset.annotate(
        dashboard_product_count=Count("variants__product", distinct=True),
        dashboard_active_product_count=Count(
            "variants__product",
            filter=Q(variants__product__status=Product.STATUS_ACTIVE),
            distinct=True,
        ),
        dashboard_variant_count=Count("variants", distinct=True),
    ).order_by("sort_order", "name")


def apply_taxonomy_filters(request, queryset, active_filters):
    selected_visibility = request.GET.get("visibility", "")
    if selected_visibility == "active":
        active_filters.append("Widoczne")
        return queryset.filter(is_active=True)
    if selected_visibility == "hidden":
        active_filters.append("Ukryte")
        return queryset.filter(is_active=False)
    return queryset


def get_taxonomy_copy(model):
    if model is BlogCategory:
        return {
            "singular": "kategoria poradników",
            "plural": "kategorie poradników",
            "preview_label": "Kategoria poradników",
            "add_label": "Dodaj kategorię",
            "save_label": "Zapisz kategorię",
            "delete_label": "Usuń kategorię",
            "description": "Kategorie porządkują poradniki SEO, inspiracje i treści powiązane ze sprzedażą.",
            "empty_description": "Opis kategorii nie jest jeszcze uzupełniony.",
            "form_description": "To dane używane przy poradnikach, filtrach treści i przyszłych stronach SEO.",
            "preview_description": "Krótki podgląd tego, jak kategoria będzie wyglądać w panelu i linkach do poradników.",
        }
    if model is Category:
        return {
            "singular": "kategoria",
            "plural": "kategorie",
            "preview_label": "Kategoria",
            "add_label": "Dodaj kategorię",
            "save_label": "Zapisz kategorię",
            "delete_label": "Usuń kategorię",
            "description": "Kategorie porządkują typy produktów w katalogu i filtrach.",
            "empty_description": "Opis kategorii nie jest jeszcze uzupełniony.",
            "form_description": "To są dane, które wpływają na filtrowanie katalogu i późniejsze strony kolekcji.",
            "preview_description": "Krótki kontekst, żeby od razu było widać, czy ta pozycja ma sens w katalogu.",
        }
    if model is Aesthetic:
        return {
            "singular": "estetyka",
            "plural": "estetyki",
            "preview_label": "Estetyka",
            "add_label": "Dodaj estetykę",
            "save_label": "Zapisz estetykę",
            "delete_label": "Usuń estetykę",
            "description": "Estetyki opisują klimat produktu i pomagają budować kolekcje oraz inspiracje.",
            "empty_description": "Opis estetyki nie jest jeszcze uzupełniony.",
            "form_description": "To są dane, które wpływają na filtrowanie katalogu i późniejsze strony kolekcji.",
            "preview_description": "Krótki kontekst, żeby od razu było widać, czy ta pozycja ma sens w katalogu.",
        }
    if model is Color:
        return {
            "singular": "kolor",
            "plural": "kolory",
            "preview_label": "Kolor",
            "add_label": "Dodaj kolor",
            "save_label": "Zapisz kolor",
            "delete_label": "Usuń kolor",
            "description": "Kolory są używane w wariantach produktu, filtrach katalogu i swatchach.",
            "empty_description": "Kolor nie ma osobnego opisu, najważniejsze są nazwa i HEX.",
            "form_description": "To są dane, które wpływają na warianty produktów i filtry katalogu.",
            "preview_description": "Krótki kontekst, żeby od razu było widać, czy ta pozycja ma sens w katalogu.",
        }
    return {
        "singular": "rozmiar",
        "plural": "rozmiary",
        "preview_label": "Rozmiar",
        "add_label": "Dodaj rozmiar",
        "save_label": "Zapisz rozmiar",
        "delete_label": "Usuń rozmiar",
        "description": "Rozmiary są używane w wariantach produktu i filtrach katalogu.",
        "empty_description": "Rozmiar nie ma osobnego opisu, najważniejsza jest nazwa i kolejność.",
        "form_description": "To są dane, które wpływają na warianty produktów i filtry katalogu.",
        "preview_description": "Krótki kontekst, żeby od razu było widać, czy ta pozycja ma sens w katalogu.",
    }


def build_taxonomy_list_context(config):
    base_queryset = config.model.objects.all()
    copy = get_taxonomy_copy(config.model)
    if config.model is BlogCategory:
        article_queryset = Article.objects.filter(category__in=base_queryset).distinct()
        published_article_count = article_queryset.filter(status=Article.STATUS_PUBLISHED).count()
        return {
            **copy,
            "search_placeholder": "Szukaj po nazwie lub opisie",
            "total_count": base_queryset.count(),
            "active_count": base_queryset.filter(is_active=True).count(),
            "hidden_count": base_queryset.filter(is_active=False).count(),
            "assigned_content_label": "Poradniki",
            "assigned_content_count": article_queryset.count(),
            "assigned_content_help": f"{published_article_count} opublikowane",
            "extra_label": "Wyróżnione",
            "extra_count": article_queryset.filter(is_featured=True).count(),
            "extra_help": "na listach i stronie",
        }

    product_queryset = get_taxonomy_product_queryset(config.model, base_queryset)
    context = {
        **copy,
        "search_placeholder": "Szukaj po nazwie lub opisie" if config.model in {Category, Aesthetic} else "Szukaj po nazwie",
        "total_count": base_queryset.count(),
        "active_count": base_queryset.filter(is_active=True).count(),
        "hidden_count": base_queryset.filter(is_active=False).count(),
        "assigned_product_count": product_queryset.count(),
        "active_product_count": product_queryset.filter(status=Product.STATUS_ACTIVE).count(),
        "assigned_content_label": "Produkty",
        "assigned_content_count": product_queryset.count(),
        "assigned_content_help": f"{product_queryset.filter(status=Product.STATUS_ACTIVE).count()} aktywne",
    }
    if config.model is Category:
        context["extra_label"] = "Podkategorie"
        context["extra_count"] = Category.objects.filter(parent__isnull=False).count()
        context["extra_help"] = "Dane pomocnicze"
    elif config.model is Aesthetic:
        context["extra_label"] = "Opisane"
        context["extra_count"] = base_queryset.exclude(description="").count()
        context["extra_help"] = "Dane pomocnicze"
    elif config.model is Color:
        context["extra_label"] = "Warianty"
        context["extra_count"] = ProductVariant.objects.filter(color__in=base_queryset).count()
        context["extra_help"] = "Dane pomocnicze"
    else:
        context["extra_label"] = "Warianty"
        context["extra_count"] = ProductVariant.objects.filter(size__in=base_queryset).count()
        context["extra_help"] = "Dane pomocnicze"
    return context


def get_taxonomy_product_queryset(model, taxonomy_queryset):
    if model is Category:
        return Product.objects.filter(category__in=taxonomy_queryset).distinct()
    if model is Aesthetic:
        return Product.objects.filter(aesthetics__in=taxonomy_queryset).distinct()
    if model is Color:
        return Product.objects.filter(variants__color__in=taxonomy_queryset).distinct()
    return Product.objects.filter(variants__size__in=taxonomy_queryset).distinct()


def get_taxonomy_preview_url(model, obj):
    if model is BlogCategory:
        return f"{reverse('blog:list')}?category={obj.slug}"

    parameter = {
        Category: "category",
        Aesthetic: "aesthetic",
        Color: "color",
        Size: "size",
    }[model]
    return f"{reverse('catalog:product_list')}?{parameter}={obj.slug}"


def build_taxonomy_row(config, obj):
    if config.model is BlogCategory:
        article_count = getattr(obj, "dashboard_article_count", 0)
        published_article_count = getattr(obj, "dashboard_published_article_count", 0)
        featured_article_count = getattr(obj, "dashboard_featured_article_count", 0)
        return {
            "object": obj,
            "admin_url": get_admin_object_url(config, obj),
            "delete_url": reverse("dashboard:model_delete", args=[config.slug, obj.pk]),
            "preview_url": get_taxonomy_preview_url(config.model, obj),
            "eyebrow": f"Kategoria poradników #{obj.sort_order}",
            "name": obj.name,
            "description": obj.description.strip(),
            "slug": obj.slug,
            "is_active": obj.is_active,
            "article_count": article_count,
            "published_article_count": published_article_count,
            "featured_article_count": featured_article_count,
            "facts": [
                {"label": "Poradniki", "value": article_count},
                {"label": "Opublikowane", "value": published_article_count},
                {"label": "Wyróżnione", "value": featured_article_count},
                {"label": "Kolejność", "value": obj.sort_order},
            ],
            "color_hex": "",
        }

    product_count = getattr(obj, "dashboard_product_count", 0)
    active_product_count = getattr(obj, "dashboard_active_product_count", 0)
    facts = [
        {"label": "Produkty", "value": product_count},
        {"label": "Aktywne", "value": active_product_count},
    ]
    color_hex = ""

    if config.model is Category:
        eyebrow = "Podkategoria" if obj.parent_id else "Kategoria główna"
        facts.extend(
            [
                {"label": "Podkategorie", "value": getattr(obj, "dashboard_children_count", 0)},
                {"label": "Nadrzędna", "value": obj.parent.name if obj.parent else "Brak"},
            ]
        )
        description = obj.description.strip()
    elif config.model is Aesthetic:
        eyebrow = f"Estetyka #{obj.sort_order}"
        facts.append({"label": "Kolejność", "value": obj.sort_order})
        description = obj.description.strip()
    elif config.model is Color:
        color_hex = obj.hex_code or ""
        eyebrow = color_hex or "Kolor bez HEX"
        facts.extend(
            [
                {"label": "Warianty", "value": getattr(obj, "dashboard_variant_count", 0)},
                {"label": "HEX", "value": color_hex or "Brak"},
            ]
        )
        description = "Kolor używany w wariantach produktu i filtrach katalogu."
    else:
        eyebrow = f"Rozmiar #{obj.sort_order}"
        facts.extend(
            [
                {"label": "Warianty", "value": getattr(obj, "dashboard_variant_count", 0)},
                {"label": "Kolejność", "value": obj.sort_order},
            ]
        )
        description = "Rozmiar używany w wariantach produktu i filtrach katalogu."

    return {
        "object": obj,
        "admin_url": get_admin_object_url(config, obj),
        "delete_url": reverse("dashboard:model_delete", args=[config.slug, obj.pk]),
        "preview_url": get_taxonomy_preview_url(config.model, obj),
        "eyebrow": eyebrow,
        "name": obj.name,
        "description": description,
        "slug": obj.slug,
        "is_active": obj.is_active,
        "product_count": product_count,
        "active_product_count": active_product_count,
        "facts": facts,
        "color_hex": color_hex,
    }


def build_taxonomy_detail_context(config, obj):
    copy = get_taxonomy_copy(config.model)
    context = {
        **copy,
        "description": "Slug utworzy się automatycznie po zapisaniu nazwy.",
        "preview_url": "",
        "product_count": 0,
        "active_product_count": 0,
        "content_label": "Produkty",
        "content_count": 0,
        "content_help": "0 aktywne",
        "related_title": "Powiązane produkty",
        "related_items": [],
        "related_empty": "Na razie nic nie jest przypisane.",
        "detail_stat_label": "Status",
        "detail_stat_value": "-",
        "detail_stat_help": "Dane pojawią się po zapisaniu.",
        "color_hex": "",
    }
    if config.model is BlogCategory:
        context.update(
            {
                "content_label": "Poradniki",
                "content_help": "0 opublikowane",
                "related_title": "Poradniki w kategorii",
                "related_empty": "Na razie żaden poradnik nie jest przypisany do tej kategorii.",
            }
        )
    if not obj:
        return context

    if config.model is BlogCategory:
        article_queryset = Article.objects.filter(category=obj)
        published_article_count = article_queryset.filter(status=Article.STATUS_PUBLISHED).count()
        context.update(
            {
                "description": getattr(obj, "description", "") or copy["empty_description"],
                "slug": obj.slug,
                "is_active": obj.is_active,
                "preview_url": get_taxonomy_preview_url(config.model, obj),
                "content_label": "Poradniki",
                "content_count": article_queryset.count(),
                "content_help": f"{published_article_count} opublikowane",
                "related_title": "Poradniki w kategorii",
                "related_items": [
                    {
                        "label": article.title,
                        "meta": get_article_status_label(article.status),
                    }
                    for article in article_queryset.order_by("-published_at", "-created_at")[:6]
                ],
                "related_empty": "Na razie żaden poradnik nie jest przypisany do tej kategorii.",
                "detail_stat_label": "Kolejność",
                "detail_stat_value": obj.sort_order,
                "detail_stat_help": "Niżej znaczy wcześniej",
            }
        )
        return context

    product_queryset = get_taxonomy_product_queryset(config.model, config.model.objects.filter(pk=obj.pk))
    active_product_count = product_queryset.filter(status=Product.STATUS_ACTIVE).count()
    context.update(
        {
            "description": getattr(obj, "description", "") or copy["empty_description"],
            "slug": obj.slug,
            "is_active": obj.is_active,
            "preview_url": get_taxonomy_preview_url(config.model, obj),
            "product_count": product_queryset.count(),
            "active_product_count": active_product_count,
            "content_count": product_queryset.count(),
            "content_help": f"{active_product_count} aktywne",
            "related_items": [
                {
                    "label": product.name,
                    "meta": product.get_status_display(),
                }
                for product in product_queryset.order_by("name")[:6]
            ],
        }
    )
    if config.model is Category:
        context["parent"] = obj.parent
        context["detail_stat_label"] = "Podkategorie"
        context["detail_stat_value"] = obj.children.count()
        context["detail_stat_help"] = f"Nadrzędna: {obj.parent}" if obj.parent else "Kategoria główna"
    elif config.model is Aesthetic:
        context["detail_stat_label"] = "Kolejność"
        context["detail_stat_value"] = obj.sort_order
        context["detail_stat_help"] = "Niżej znaczy wcześniej"
    elif config.model is Color:
        context["color_hex"] = obj.hex_code or ""
        context["detail_stat_label"] = "HEX"
        context["detail_stat_value"] = obj.hex_code or "Brak"
        context["detail_stat_help"] = f"{obj.variants.count()} wariantów używa tego koloru"
    else:
        context["detail_stat_label"] = "Kolejność"
        context["detail_stat_value"] = obj.sort_order
        context["detail_stat_help"] = f"{obj.variants.count()} wariantów używa tego rozmiaru"
    return context


def apply_product_sorting(queryset, request):
    sort_key = request.GET.get("sort", "").strip()
    direction = get_sort_direction(request)
    if sort_key not in PRODUCT_SORT_HEADERS:
        return queryset

    if sort_key == "stock":
        stock_subquery = (
            ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True)
            .values("product")
            .annotate(total=Sum("stock_quantity"))
            .values("total")
        )
        queryset = queryset.annotate(
            dashboard_stock_quantity=Coalesce(
                Subquery(stock_subquery, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            )
        )
        return queryset.order_by(order_field("dashboard_stock_quantity", direction), "name")

    if sort_key == "regular_price":
        queryset = queryset.annotate(
            dashboard_regular_price=F("regular_price")
        )
        return queryset.order_by(order_field("dashboard_regular_price", direction), "name")

    if sort_key == "sale_price":
        queryset = queryset.annotate(
            dashboard_has_sale=Case(
                When(sale_price__lt=F("regular_price"), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            dashboard_sale_price=Coalesce("sale_price", Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        )
        return queryset.order_by(
            "-dashboard_has_sale",
            order_field("dashboard_sale_price", direction),
            "name",
        )

    sort_fields = {
        "product": ("name",),
        "category": ("category__name", "name"),
        "status": ("status", "name"),
        "featured": ("is_featured", "name"),
    }[sort_key]
    return queryset.order_by(*(order_field(field, direction) for field in sort_fields))


def get_sort_direction(request):
    direction = request.GET.get("direction", "asc").strip().lower()
    return direction if direction in {"asc", "desc"} else "asc"


def order_field(field, direction):
    if direction == "desc":
        return f"-{field}"
    return field


def build_product_sort_headers(request):
    active_sort = request.GET.get("sort", "").strip()
    active_direction = get_sort_direction(request)
    base_params = request.GET.copy()
    base_params.pop("page", None)
    headers = {}

    for key, label in PRODUCT_SORT_HEADERS.items():
        next_direction = "desc" if active_sort == key and active_direction == "asc" else "asc"
        params = base_params.copy()
        params["sort"] = key
        params["direction"] = next_direction
        headers[key] = {
            "label": label,
            "url": f"?{params.urlencode()}",
            "is_active": active_sort == key,
            "direction": active_direction if active_sort == key else "",
            "marker": "↑" if active_sort == key and active_direction == "asc" else "↓" if active_sort == key else "",
        }
    return headers


def limit_image_variants(image_formset, product):
    variants = product.variants.select_related("color", "size")
    for form in image_formset.forms:
        if "variant" in form.fields:
            form.fields["variant"].queryset = variants
            form.fields["variant"].empty_label = "Wszystkie"


def delete_workspace_images(product, raw_ids):
    image_ids = parse_id_list(raw_ids)
    if image_ids:
        ProductImage.objects.filter(product=product, pk__in=image_ids).delete()


def delete_workspace_variants(product, raw_ids):
    variant_ids = parse_id_list(raw_ids)
    if variant_ids:
        ProductVariant.objects.filter(product=product, pk__in=variant_ids).delete()


def delete_workspace_outfit_images(outfit, raw_ids):
    image_ids = parse_id_list(raw_ids)
    if image_ids:
        OutfitImage.objects.filter(outfit=outfit, pk__in=image_ids).delete()


def delete_workspace_outfit_items(outfit, raw_ids):
    item_ids = parse_id_list(raw_ids)
    if item_ids:
        OutfitItem.objects.filter(outfit=outfit, pk__in=item_ids).delete()


def delete_workspace_outfit_hotspots(outfit, raw_ids):
    hotspot_ids = parse_id_list(raw_ids)
    if hotspot_ids:
        OutfitHotspot.objects.filter(outfit=outfit, pk__in=hotspot_ids).delete()


def parse_id_list(raw_ids):
    ids = []
    for value in (raw_ids or "").split(","):
        value = value.strip()
        if value.isdigit():
            ids.append(int(value))
    return ids


def filter_product_image_files(files):
    valid_files = []
    rejected_names = []
    for uploaded_file in files:
        extension = Path(uploaded_file.name).suffix.lower()
        content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
        if extension in ALLOWED_PRODUCT_IMAGE_EXTENSIONS or content_type in ALLOWED_PRODUCT_IMAGE_CONTENT_TYPES:
            valid_files.append(uploaded_file)
        else:
            rejected_names.append(uploaded_file.name)
    return valid_files, rejected_names


def create_product_images(product, image_files):
    if not image_files:
        return []

    max_order = product.images.aggregate(max_order=Max("sort_order"))["max_order"]
    next_order = 0 if max_order is None else max_order + 1
    created_images = []
    for index, image_file in enumerate(image_files):
        created_images.append(
            ProductImage.objects.create(
                product=product,
                image=image_file,
                alt_text=product.name,
                sort_order=next_order + index,
                is_main=False,
            )
        )
    return created_images


def sync_product_main_image(product):
    first_image = product.images.order_by("sort_order", "id").first()
    product.images.filter(is_main=True).update(is_main=False)
    if first_image:
        ProductImage.objects.filter(pk=first_image.pk).update(is_main=True)


def create_outfit_images(outfit, image_files):
    if not image_files:
        return []

    max_order = outfit.images.aggregate(max_order=Max("sort_order"))["max_order"]
    next_order = 0 if max_order is None else max_order + 1
    created_images = []
    for index, image_file in enumerate(image_files):
        created_images.append(
            OutfitImage.objects.create(
                outfit=outfit,
                image=image_file,
                alt_text=outfit.name,
                sort_order=next_order + index,
                is_main=False,
            )
        )
    return created_images


def sync_outfit_main_image(outfit):
    first_image = outfit.images.order_by("sort_order", "id").first()
    outfit.images.filter(is_main=True).update(is_main=False)
    if first_image:
        OutfitImage.objects.filter(pk=first_image.pk).update(is_main=True)


def build_product_workspace_stats(product):
    now = timezone.localtime()
    start_date = now.date() - timedelta(days=29)
    start_at = timezone.make_aware(datetime.combine(start_date, time.min), timezone.get_current_timezone())
    product_events = AnalyticsEvent.objects.filter(product=product, created_at__gte=start_at, created_at__lte=now)
    view_events = product_events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW)
    cart_events = product_events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART)
    order_items = OrderItem.objects.filter(
        product=product,
        order__created_at__gte=start_at,
    ).exclude(order__status__in=[Order.STATUS_DRAFT, Order.STATUS_CANCELLED])
    purchased_quantity = order_items.aggregate(total=Sum("quantity"))["total"] or 0
    order_count = order_items.values("order_id").distinct().count()

    daily_stats = build_product_daily_stats(start_date, now.date(), view_events, cart_events, order_items)

    return {
        "unique_viewers": count_unique_visitors(view_events),
        "product_views": view_events.count(),
        "add_to_cart": cart_events.count(),
        "orders": order_count,
        "purchased_quantity": purchased_quantity,
        "view_to_cart_rate": product_percent(cart_events.count(), view_events.count()),
        "cart_to_order_rate": product_percent(order_count, cart_events.count()),
        "daily_rows": daily_stats["rows"],
        "y_ticks": daily_stats["y_ticks"],
        "max_value": daily_stats["max_value"],
        "has_activity": any(row["views"] or row["cart"] or row["orders"] for row in daily_stats["rows"]),
    }


def build_product_daily_stats(start_date, end_date, view_events, cart_events, order_items):
    dates = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
    views_by_day = {
        row["day"]: row["count"]
        for row in view_events.annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id"))
    }
    cart_by_day = {
        row["day"]: row["count"]
        for row in cart_events.annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id"))
    }
    orders_by_day = {
        row["day"]: row["count"]
        for row in order_items.annotate(day=TruncDate("created_at")).values("day").annotate(count=Sum("quantity"))
    }
    max_value = max(
        [1]
        + [views_by_day.get(day, 0) for day in dates]
        + [cart_by_day.get(day, 0) for day in dates]
        + [orders_by_day.get(day, 0) for day in dates]
    )
    rows = []
    for day in dates:
        views = views_by_day.get(day, 0)
        cart = cart_by_day.get(day, 0)
        orders = orders_by_day.get(day, 0)
        rows.append(
            {
                "label": day.strftime("%d.%m"),
                "views": views,
                "cart": cart,
                "orders": orders,
                "views_height": product_bar_height(views, max_value),
                "cart_height": product_bar_height(cart, max_value),
                "orders_height": product_bar_height(orders, max_value),
            }
        )
    return {
        "rows": rows,
        "max_value": max_value,
        "y_ticks": build_product_chart_ticks(max_value),
    }


def build_product_chart_ticks(max_value):
    values = sorted({0, round(max_value / 2), max_value}, reverse=True)
    return [
        {
            "value": value,
            "position": product_bar_height(value, max_value),
        }
        for value in values
    ]


def product_bar_height(value, max_value):
    if not value:
        return "0"
    height = max(6, round((value / max_value) * 100, 2))
    return f"{height:.2f}".rstrip("0").rstrip(".")


def product_percent(numerator, denominator):
    if not denominator:
        return "0%"
    return f"{round((numerator / denominator) * 100, 1):g}%".replace(".", ",")


def build_product_fieldsets(form):
    return [
        {
            "title": "Podstawy produktu",
            "description": "Nazwa, kategoria, estetyki i widoczność w sklepie. Slug tworzy się automatycznie z nazwy.",
            "fields": [form[name] for name in ["name", "category", "aesthetics", "status"]],
        },
        {
            "title": "Treść na karcie produktu",
            "description": "Główny opis produktu oraz krótka inspiracja stylizacyjna.",
            "fields": [
                form[name]
                for name in ["description", "styling_tips"]
            ],
        },
        {
            "title": "Cena",
            "description": "Cena regularna oraz opcjonalna cena promocyjna.",
            "fields": [
                form[name]
                for name in [
                    "regular_price",
                    "sale_price",
                ]
            ],
        },
        {
            "title": "Oznaczenia i etykiety",
            "description": "Etykiety na karcie produktu. „Promocja” pojawia się automatycznie, gdy ustawisz cenę promocyjną. „Ostatnie sztuki” pojawia się automatycznie, gdy stan spadnie do progu poniżej — chyba że je wyłączysz.",
            "fields": [form[name] for name in ["is_new", "is_bestseller", "is_featured", "disable_low_stock_badge", "low_stock_threshold"]],
        },
        {
            "title": "SEO",
            "description": "Tytuł i opis do wyników wyszukiwania oraz późniejszej optymalizacji.",
            "fields": [form[name] for name in ["seo_title", "seo_description"]],
        },
    ]


def build_outfit_fieldsets(form):
    return [
        {
            "title": "Podstawy stylizacji",
            "description": "Nazwa, estetyki i widoczność w sklepie. Slug tworzy się automatycznie z nazwy.",
            "fields": [form[name] for name in ["name", "aesthetics", "status"]],
        },
        {
            "title": "Treść stylizacji",
            "description": "Opis widoczny na liście, karcie stylizacji i w inspiracjach stylizacyjnych.",
            "fields": [form[name] for name in ["short_description", "mood_description", "styling_tips"]],
        },
        {
            "title": "Cena zestawu",
            "description": "Cena osobno liczy się z produktów. Cena promocyjna jest opcjonalna.",
            "fields": [form["bundle_price"]],
        },
        {
            "title": "SEO",
            "description": "Tytuł i opis do wyników wyszukiwania oraz późniejszej optymalizacji.",
            "fields": [form[name] for name in ["seo_title", "seo_description"]],
        },
    ]


def build_article_fieldsets(form):
    return [
        {
            "title": "1. Podstawowe informacje",
            "description": "Tytuł i zajawka budują nagłówek poradnika oraz kartę na liście.",
            "fields": [form[name] for name in ["title", "intro"]],
        },
        {
            "title": "2. Treść poradnika",
            "description": "Możesz pisać ręcznie albo wkleić gotowy tekst z formatowaniem, np. z ChatuGPT.",
            "fields": [form["body"]],
        },
        {
            "title": "3. Powiązania",
            "description": "Połącz poradnik z estetykami, produktami i gotowymi stylizacjami.",
            "fields": [form[name] for name in ["aesthetics", "products", "outfits"]],
        },
    ]


def build_article_publication_fields(form):
    return [form[name] for name in ["status", "is_featured", "published_at"]]


def build_article_cover_fields(form):
    return [form[name] for name in ["category", "cover_image"]]


def build_article_seo_fields(form):
    return [form[name] for name in ["seo_title", "seo_description"]]


def build_order_fieldsets(form):
    return [
        {
            "title": "Status i identyfikacja",
            "description": "Numer, status i data złożenia zamówienia.",
            "fields": [form[name] for name in ["order_number", "status", "placed_at"]],
        },
        {
            "title": "Klientka",
            "description": "Dane kontaktowe osoby składającej zamówienie.",
            "fields": [form[name] for name in ["email", "phone", "first_name", "last_name"]],
        },
        {
            "title": "Adres dostawy",
            "description": "Adres, kraj i metoda dostawy. Płatności zostają poza tym etapem.",
            "fields": [
                form[name]
                for name in [
                    "shipping_address_line_1",
                    "shipping_address_line_2",
                    "shipping_postal_code",
                    "shipping_city",
                    "shipping_country",
                    "shipping_method",
                ]
            ],
        },
        {
            "title": "Kwoty",
            "description": "Podsumowanie wartości zamówienia. Na razie bez integracji płatności.",
            "fields": [
                form[name]
                for name in [
                    "subtotal",
                    "discount_total",
                    "shipping_total",
                    "grand_total",
                    "discount_code",
                ]
            ],
        },
        {
            "title": "Notatki i analityka",
            "description": "Wiadomość klientki oraz robocze powiązanie z późniejszą analityką ścieżki.",
            "fields": [form[name] for name in ["customer_note", "source_session_key"]],
        },
    ]


def build_row(config, obj):
    return {
        "object": obj,
        "cells": [format_value(get_nested_value(obj, field)) for field in config.list_fields],
        "admin_url": get_admin_object_url(config, obj),
    }


def build_product_row(product):
    image = product.main_image
    image_url = ""
    if image and image.image:
        try:
            image_url = image.image.url
        except ValueError:
            image_url = ""
    variants = list(product.variants.all())
    stock_quantity = sum(variant.stock_quantity for variant in variants if variant.is_active)
    return {
        "object": product,
        "admin_url": reverse("dashboard:product_workspace", args=[product.pk]),
        "image_url": image_url,
        "image_alt": (image.alt_text or product.name) if image else product.name,
        "name": product.name,
        "category": product.category,
        "regular_price": product.regular_price,
        "sale_price": product.sale_price if product.has_sale_price else None,
        "stock_quantity": stock_quantity,
        "variant_count": len(variants),
        "status": product.status,
        "status_label": product.get_status_display(),
        "is_available": product.is_available,
        "is_featured": product.is_featured,
    }


def get_nested_value(obj, field_path):
    value = obj
    for part in field_path.split("__"):
        value = getattr(value, part, None)
        if value is None:
            return ""
    return value


def format_value(value):
    if isinstance(value, bool):
        return "Tak" if value else "Nie"
    return value


def get_admin_object_url(config, obj):
    if config.model is Product:
        return reverse("dashboard:product_workspace", args=[obj.pk])
    if config.model is Outfit:
        return reverse("dashboard:outfit_workspace", args=[obj.pk])
    if config.model is Article:
        return reverse("dashboard:article_workspace", args=[obj.pk])
    if config.model is Order:
        return reverse("dashboard:order_workspace", args=[obj.pk])
    return reverse("dashboard:model_edit", args=[config.slug, obj.pk])


def build_section_cards():
    cards = []
    for section, configs in get_sections().items():
        cards.append(
            {
                "name": section,
                "items": [
                    {
                        "slug": config.slug,
                        "label": config.label,
                        "count": config.model._default_manager.count(),
                    }
                    for config in configs
                ],
            }
        )
    return cards
