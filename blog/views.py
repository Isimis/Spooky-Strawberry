from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from analytics.models import AnalyticsEvent
from analytics.services import track_event
from core.seo import article_schema, breadcrumb_schema, collection_page_schema, organization_schema, plain_text, title_with_store_name

from .models import Article, BlogCategory


def article_list(request):
    selected_category = request.GET.get("category", "")
    articles = (
        Article.objects.filter(status=Article.STATUS_PUBLISHED)
        .select_related("category")
        .prefetch_related("aesthetics", "products__images", "outfits__images")
        .order_by("-published_at", "-created_at")
    )
    if selected_category:
        articles = articles.filter(category__slug=selected_category)

    # Wyróżniony wpis ma pierwszeństwo w dużej karcie. Jeżeli żaden nie jest
    # zaznaczony, pokazujemy najnowszy, aby strona zawsze miała główny artykuł.
    featured_article = articles.filter(is_featured=True).first() or articles.first()
    if featured_article:
        articles = articles.exclude(pk=featured_article.pk)

    return render(
        request,
        "blog/list.html",
        {
            "articles": articles,
            "featured_article": featured_article,
            "categories": BlogCategory.objects.filter(is_active=True).order_by("sort_order", "name"),
            "selected_category": selected_category,
            "seo_title": "Lifestyle alternatywny: poradniki i inspiracje | Spooky Strawberry",
            "seo_description": "Poradniki o stylu alternatywnym: dark coquette, jirai kei, rajstopy, kabaretki i dodatki do Twoich stylizacji.",
            "seo_structured_data": [
                organization_schema(request),
                collection_page_schema(request, "Poradniki Spooky Strawberry", reverse("blog:list")),
            ],
        },
    )


def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.select_related("category").prefetch_related(
            "aesthetics",
            "products__images",
            "products__aesthetics",
            "outfits__images",
            "outfits__aesthetics",
        ),
        slug=slug,
        status=Article.STATUS_PUBLISHED,
    )
    related_articles = (
        Article.objects.filter(status=Article.STATUS_PUBLISHED, aesthetics__in=article.aesthetics.all())
        .exclude(pk=article.pk)
        .distinct()
        .order_by("-published_at", "-created_at")[:3]
    )
    track_event(request, AnalyticsEvent.EVENT_ARTICLE_VIEW, article=article)
    word_count = len((article.body or "").split())
    reading_minutes = max(1, round(word_count / 200)) if word_count else 1
    return render(
        request,
        "blog/detail.html",
        {
            "article": article,
            "related_articles": related_articles,
            "reading_minutes": reading_minutes,
            "seo_title": title_with_store_name(article.seo_title or article.title),
            "seo_description": plain_text(article.seo_description or article.intro),
            "seo_image_url": article.cover_image and article.cover_image.url,
            "seo_og_type": "article",
            "seo_structured_data": [
                organization_schema(request),
                article_schema(request, article),
                breadcrumb_schema(
                    request,
                    [("Start", reverse("core:home")), ("Lifestyle", reverse("blog:list")), (article.title, article.get_absolute_url())],
                ),
            ],
        },
    )
