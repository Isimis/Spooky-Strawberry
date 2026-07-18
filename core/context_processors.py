from django.conf import settings

from .models import SiteSettings
from .store_info import STORE_INFO


def site_settings(request):
    """Udostępnia globalne ustawienia treści (pasek, drop, progi) we wszystkich szablonach."""
    return {"site_settings": SiteSettings.load(), "store_info": STORE_INFO}


def seo(request):
    """Wspólne techniczne dane SEO, niezależne od wyglądu strony."""
    base_url = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    canonical_url = f"{base_url}{request.path}" if base_url else request.build_absolute_uri(request.path)

    match = getattr(request, "resolver_match", None)
    namespace = match.namespace if match else ""
    url_name = match.url_name if match else ""
    noindex = namespace in {"accounts", "cart", "checkout", "dashboard", "payments"}
    noindex = noindex or (namespace == "core" and url_name in {"search", "order_status", "design_system"})
    noindex = noindex or (namespace in {"catalog", "blog", "outfits"} and bool(request.GET))

    return {
        "seo_canonical_url": canonical_url,
        "seo_noindex": noindex,
        "seo_site_url": base_url or request.build_absolute_uri("/").rstrip("/"),
    }
