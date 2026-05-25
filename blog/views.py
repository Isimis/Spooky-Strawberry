from django.shortcuts import get_object_or_404, render

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

    return render(
        request,
        "blog/list.html",
        {
            "articles": articles,
            "categories": BlogCategory.objects.filter(is_active=True).order_by("sort_order", "name"),
            "selected_category": selected_category,
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
    return render(
        request,
        "blog/detail.html",
        {
            "article": article,
            "related_articles": related_articles,
        },
    )
