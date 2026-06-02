from pathlib import Path
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
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

from analytics.models import AnalyticsEvent
from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size
from dashboard.models import DataQualityIssue
from orders.models import Order, OrderItem
from outfits.models import Outfit, OutfitImage, OutfitItem

from .forms import (
    OutfitDashboardForm,
    OutfitImageFormSet,
    OutfitItemFormSet,
    ArticleDashboardForm,
    ProductDashboardForm,
    ProductImageFormSet,
    ProductVariantFormSet,
    build_model_form,
)
from .registry import MODEL_REGISTRY, get_model_config, get_sections
from .services import count_unique_visitors, get_dashboard_analytics, refresh_all_product_quality_issues, refresh_product_quality_issues


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
    elif is_taxonomy_model(config.model):
        rows = [build_taxonomy_row(config, obj) for obj in page.object_list]
    else:
        rows = [build_row(config, obj) for obj in page.object_list]
    if config.model is Outfit:
        template_name = "dashboard/outfit_list.html"
    elif config.model is Article:
        template_name = "dashboard/article_list.html"
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
            "product_sort_headers": build_product_sort_headers(request) if config.model is Product else None,
            "outfit_summary": build_outfit_list_summary() if config.model is Outfit else None,
            "article_summary": build_article_list_summary() if config.model is Article else None,
            "article_categories": BlogCategory.objects.filter(is_active=True).order_by("sort_order", "name") if config.model is Article else None,
            "taxonomy": build_taxonomy_list_context(config) if is_taxonomy_model(config.model) else None,
            "sections": get_sections(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def model_create(request, model_slug):
    config = get_required_config(model_slug)
    if config.model is Outfit:
        return redirect("dashboard:outfit_create_workspace")
    if config.model is Article:
        return redirect("dashboard:article_create_workspace")
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    template_name = "dashboard/taxonomy_form.html" if is_taxonomy_model(config.model) else "dashboard/model_form.html"
    return render(
        request,
        template_name,
        {
            "config": config,
            "form": form,
            "object": None,
            "mode": "create",
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
    obj = get_object_or_404(config.model, pk=pk)
    form_class = build_model_form(config.model)
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Zapisano: {obj}")
        return redirect(get_admin_object_url(config, obj))

    template_name = "dashboard/taxonomy_form.html" if is_taxonomy_model(config.model) else "dashboard/model_form.html"
    return render(
        request,
        template_name,
        {
            "config": config,
            "form": form,
            "object": obj,
            "mode": "edit",
            "taxonomy": build_taxonomy_detail_context(config, obj) if is_taxonomy_model(config.model) else None,
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
            messages.success(request, "Kreacja utworzona. Teraz możesz dodać produkty i zdjęcia.")
            return redirect("dashboard:outfit_workspace", pk=outfit.pk)
        messages.error(request, "Nie udało się utworzyć kreacji. Sprawdź błędy w formularzu.")

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

    if request.method == "POST":
        new_image_files, rejected_image_names = filter_product_image_files(request.FILES.getlist("new_images"))
        if outfit_form.is_valid() and item_formset.is_valid() and image_formset.is_valid():
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
                    delete_workspace_outfit_images(outfit, request.POST.get("deleted_image_ids", ""))
                    delete_workspace_outfit_items(outfit, request.POST.get("deleted_item_ids", ""))
                    create_outfit_images(outfit, new_image_files)
                    sync_outfit_main_image(outfit)
                messages.success(request, "Kreacja zapisana razem z produktami i zdjęciami.")
                return redirect("dashboard:outfit_workspace", pk=outfit.pk)
        messages.error(request, "Nie udało się zapisać kreacji. Sprawdź błędy w formularzu.")

    return render(
        request,
        "dashboard/outfit_workspace.html",
        {
            "outfit": outfit,
            "outfit_form": outfit_form,
            "item_formset": item_formset,
            "image_formset": image_formset,
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
            "title": "SEO",
            "description": "Tytuł i opis do wyników wyszukiwania oraz późniejszej optymalizacji.",
            "fields": [form[name] for name in ["seo_title", "seo_description"]],
        },
    ]


def build_outfit_fieldsets(form):
    return [
        {
            "title": "Podstawy kreacji",
            "description": "Nazwa, estetyki i widoczność w sklepie. Slug tworzy się automatycznie z nazwy.",
            "fields": [form[name] for name in ["name", "aesthetics", "status"]],
        },
        {
            "title": "Treść kreacji",
            "description": "Opis widoczny na liście, karcie kreacji i w inspiracjach stylizacyjnych.",
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
            "description": "Połącz poradnik z estetykami, produktami i gotowymi kreacjami.",
            "fields": [form[name] for name in ["aesthetics", "products", "outfits"]],
        },
    ]


def build_article_publication_fields(form):
    return [form[name] for name in ["status", "is_featured", "published_at"]]


def build_article_cover_fields(form):
    return [form[name] for name in ["category", "cover_image"]]


def build_article_seo_fields(form):
    return [form[name] for name in ["seo_title", "seo_description"]]


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
