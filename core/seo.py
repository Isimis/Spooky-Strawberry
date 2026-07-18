"""Małe, wspólne narzędzia SEO.

Informacje są budowane po stronie serwera, aby roboty wyszukiwarek dostały
kompletny HTML już przy pierwszym pobraniu strony.
"""

import re

from django.conf import settings
from django.utils.html import strip_tags

from .store_info import STORE_INFO


def absolute_url(request, path):
    """Zwraca kanoniczny, bezwzględny adres dla ścieżki lub pliku media."""
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path

    base_url = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if base_url:
        return f"{base_url}/{path.lstrip('/')}"
    return request.build_absolute_uri(path)


def plain_text(value, limit=255):
    """Opis do meta danych bez znaczników i składni używanej w opisach."""
    text = strip_tags(value or "")
    text = re.sub(r"[*_#>`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def title_with_store_name(value):
    """Dopisuje markę tylko wtedy, gdy nie ma jej już w ręcznie wpisanym tytule."""
    title = (value or "").strip()
    if "spooky strawberry" in title.casefold():
        return title
    return f"{title} | Spooky Strawberry" if title else "Spooky Strawberry"


def organization_schema(request):
    """Fakty o sklepie wspólne dla danych uporządkowanych."""
    return {
        "@context": "https://schema.org",
        "@type": ["Organization", "OnlineStore"],
        "@id": f"{absolute_url(request, '/')}#organization",
        "name": "Spooky Strawberry",
        "legalName": STORE_INFO["seller_name"],
        "url": absolute_url(request, "/"),
        "email": STORE_INFO["contact_email"],
        "telephone": STORE_INFO["contact_phone"],
        "taxID": STORE_INFO["tax_id"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "ul. ppłk. pil. Romualda Sulińskiego 8B",
            "postalCode": "96-100",
            "addressLocality": "Skierniewice",
            "addressCountry": "PL",
        },
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "email": STORE_INFO["contact_email"],
            "telephone": STORE_INFO["contact_phone"],
            "availableLanguage": "pl",
        },
        "hasMerchantReturnPolicy": {
            "@type": "MerchantReturnPolicy",
            "applicableCountry": "PL",
            "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
            "merchantReturnDays": 14,
            "returnMethod": "https://schema.org/ReturnByMail",
        },
    }


def website_schema(request):
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{absolute_url(request, '/')}#website",
        "name": "Spooky Strawberry",
        "url": absolute_url(request, "/"),
        "inLanguage": "pl-PL",
        "publisher": {"@id": f"{absolute_url(request, '/')}#organization"},
    }


def product_schema(request, product, variant):
    """Dane produktu zgodne z widoczną, wybraną ofertą na karcie produktu."""
    image = product.main_image
    offer = {
        "@type": "Offer",
        "url": absolute_url(request, product.get_absolute_url()),
        "priceCurrency": "PLN",
        "price": str(variant.price if variant else product.current_price),
        "availability": (
            "https://schema.org/InStock"
            if variant and variant.is_in_stock
            else "https://schema.org/OutOfStock"
        ),
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {"@id": f"{absolute_url(request, '/')}#organization"},
    }
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "url": absolute_url(request, product.get_absolute_url()),
        "description": plain_text(product.description, limit=500),
        "brand": {"@type": "Brand", "name": "Spooky Strawberry"},
        "offers": offer,
    }
    if image:
        data["image"] = absolute_url(request, image.image.url)
    if variant and variant.sku:
        data["sku"] = variant.sku
    if variant and variant.color:
        data["color"] = variant.color.name
    if variant and variant.size:
        data["size"] = variant.size.name
    return data


def article_schema(request, article):
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.title,
        "description": plain_text(article.seo_description or article.intro, limit=255),
        "mainEntityOfPage": absolute_url(request, article.get_absolute_url()),
        "url": absolute_url(request, article.get_absolute_url()),
        "inLanguage": "pl-PL",
        "author": {"@type": "Organization", "name": "Zespół Spooky Strawberry"},
        "publisher": {"@id": f"{absolute_url(request, '/')}#organization"},
        "dateModified": article.updated_at.isoformat(),
    }
    if article.published_at:
        data["datePublished"] = article.published_at.isoformat()
    if article.cover_image:
        data["image"] = absolute_url(request, article.cover_image.url)
    return data


def breadcrumb_schema(request, items):
    """items: lista par (widoczna nazwa, ścieżka)."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": absolute_url(request, path),
            }
            for position, (name, path) in enumerate(items, start=1)
        ],
    }


def collection_page_schema(request, name, path, description=""):
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": name,
        "url": absolute_url(request, path),
        "inLanguage": "pl-PL",
        "isPartOf": {"@id": f"{absolute_url(request, '/')}#website"},
    }
    if description:
        data["description"] = plain_text(description)
    return data
