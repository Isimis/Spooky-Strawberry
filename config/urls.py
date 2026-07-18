from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path

from core.sitemaps import sitemaps


def robots_txt(request):
    base_url = (settings.SITE_BASE_URL or request.build_absolute_uri("/")).rstrip("/")
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /django-admin/",
            "Disallow: /admin/",
            "Disallow: /konto/",
            "Disallow: /koszyk/",
            "Disallow: /zamowienie/",
            "Disallow: /platnosci/",
            "Disallow: /szukaj/",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")

urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("admin/", include("dashboard.urls")),
    path("django-admin/", admin.site.urls),
    path("", include("catalog.urls")),
    path("", include("cart.urls")),
    path("", include("checkout.urls")),
    path("", include("payments.urls")),
    path("", include("outfits.urls")),
    path("", include("blog.urls")),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
