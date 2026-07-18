from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Article
from catalog.models import Aesthetic, Category, Product
from outfits.models import Outfit


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Product.objects.filter(status=Product.STATUS_ACTIVE)

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)


class AestheticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Aesthetic.objects.filter(is_active=True)


class OutfitSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Outfit.objects.filter(status=Outfit.STATUS_ACTIVE)

    def lastmod(self, obj):
        return obj.updated_at


class ArticleSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Article.objects.filter(status=Article.STATUS_PUBLISHED)

    def lastmod(self, obj):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "monthly"
    names = (
        "core:home", "catalog:product_list", "catalog:aesthetic_list", "outfits:list",
        "blog:list", "core:about", "core:contact", "core:shipping", "core:returns",
        "core:terms", "core:privacy", "core:accessibility", "core:sitemap",
    )

    def items(self):
        return self.names

    def location(self, item):
        return reverse(item)


sitemaps = {
    "pages": StaticViewSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "aesthetics": AestheticSitemap,
    "outfits": OutfitSitemap,
    "articles": ArticleSitemap,
}
