from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods

from analytics.models import AnalyticsEvent
from catalog.models import Product, ProductImage, ProductVariant
from dashboard.models import DataQualityIssue
from orders.models import Order

from .forms import ProductDashboardForm, ProductImageFormSet, ProductVariantFormSet, build_model_form
from .registry import MODEL_REGISTRY, get_model_config, get_sections
from .services import get_dashboard_analytics, refresh_all_product_quality_issues, refresh_product_quality_issues


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
def model_list(request, model_slug):
    config = get_required_config(model_slug)
    queryset = config.model._default_manager.all()
    query = request.GET.get("q", "").strip()
    active_filters = []

    if config.model is Product:
        queryset = queryset.select_related("category").prefetch_related("images", "variants", "aesthetics")
        queryset = apply_product_admin_filters(request, queryset, active_filters)

    if query and config.search_fields:
        filters = Q()
        for field in config.search_fields:
            filters |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(filters)
        active_filters.append(f"Szukaj: {query}")

    paginator = Paginator(queryset.distinct(), 25)
    page = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    rows = [build_row(config, obj) for obj in page.object_list]
    return render(
        request,
        "dashboard/model_list.html",
        {
            "config": config,
            "rows": rows,
            "page": page,
            "query": query,
            "query_string": query_params.urlencode(),
            "active_filters": active_filters,
            "product_statuses": Product.STATUS_CHOICES if config.model is Product else None,
            "selected_status": request.GET.get("status", ""),
            "selected_stock": request.GET.get("stock", ""),
            "selected_quality": request.GET.get("quality", ""),
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_create(request, model_slug):
    config = get_required_config(model_slug)
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    return render(
        request,
        "dashboard/model_form.html",
        {
            "config": config,
            "form": form,
            "object": None,
            "mode": "create",
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_edit(request, model_slug, pk):
    config = get_required_config(model_slug)
    obj = get_object_or_404(config.model, pk=pk)
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    return render(
        request,
        "dashboard/model_form.html",
        {
            "config": config,
            "form": form,
            "object": obj,
            "mode": "edit",
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_delete(request, model_slug, pk):
    config = get_required_config(model_slug)
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
        if product_form.is_valid() and variant_formset.is_valid() and image_formset.is_valid():
            product = product_form.save()
            variant_formset.instance = product
            variant_formset.save()
            image_formset.instance = product
            image_formset.save()
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
            "sections": get_sections(),
        },
    )


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
        active_filters.append(f"Status: {selected_status}")
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


def limit_image_variants(image_formset, product):
    variants = product.variants.select_related("color", "size")
    for form in image_formset.forms:
        if "variant" in form.fields:
            form.fields["variant"].queryset = variants


def build_product_fieldsets(form):
    return [
        {
            "title": "Podstawy produktu",
            "description": "Nazwa, adres URL, typ produktu i estetyki.",
            "fields": [form[name] for name in ["name", "slug", "category", "aesthetics"]],
        },
        {
            "title": "Treści na karcie produktu",
            "description": "Opisy, detale i inspiracje stylizacyjne widoczne dla klientki.",
            "fields": [
                form[name]
                for name in ["short_description", "mood_description", "details", "styling_tips"]
            ],
        },
        {
            "title": "Cena i status",
            "description": "Cena bazowa, oznaczenia na stronie i widoczność produktu.",
            "fields": [
                form[name]
                for name in [
                    "base_price",
                    "compare_at_price",
                    "is_featured",
                    "is_new_drop",
                    "sort_order",
                    "status",
                ]
            ],
        },
        {
            "title": "SEO",
            "description": "Tytuł i opis do wyników wyszukiwania oraz późniejszej optymalizacji.",
            "fields": [form[name] for name in ["seo_title", "seo_description"]],
        },
    ]


def build_row(config, obj):
    return {
        "object": obj,
        "cells": [format_value(get_nested_value(obj, field)) for field in config.list_fields],
        "admin_url": get_admin_object_url(config, obj),
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
