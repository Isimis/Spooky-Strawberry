"""Budowanie i wysyłka systemowych maili - spójny styl graficzny i treść.

Wygląd (nagłówek, ramka, stopka, responsywność) mieszka w szablonie bazowym
(`base-layout`, edytowalnym w panelu). Tutaj składamy TREŚĆ każdego maila z gotowych,
spójnych komponentów (przycisk, lista produktów, ramka szczegółów) - wszystko na
inline-CSS + tabelach, żeby ładowało się poprawnie na każdej poczcie (mobile i PC).

Wysyłamy przez panelowy mailer (`send_message`), więc każdy mail trafia też do
skrzynki panelu i (na produkcji) do folderu „Sent" w webmailu.
"""

from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

# Paleta marki (spójna ze sklepem)
ACCENT = "#c2185b"
INK = "#1c1620"
MUTED = "#6c6470"
LINE = "#efe7ee"
SOFT = "#faf3f7"

FONT = "Arial,Helvetica,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"

# Style współdzielone (spójny nagłówek/akapit w każdym mailu)
H1 = f"margin:0 0 14px;font-family:{SERIF};font-size:23px;line-height:1.3;color:{INK};font-weight:700;"
P = f"margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.65;color:{INK};"
P_MUTED = f"margin:0 0 14px;font-family:{FONT};font-size:13px;line-height:1.6;color:{MUTED};"


# --- Adresy bezwzględne (maile nie mają dostępu do request) ---

def _abs_url(path):
    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    return f"{base}{path}" if base else path


def order_status_url(order):
    """Link otwierający zamówienie od razu (po sekretnym tokenie)."""
    query = urlencode({"number": order.order_number or "", "token": order.confirmation_token})
    return _abs_url(f"{reverse('core:order_status')}?{query}")


def money(value):
    return f"{Decimal(value):.2f}".replace(".", ",") + " zł"


# --- Komponenty treści (zwracają bezpieczny HTML do wstawienia w {{ ... }}) ---

def cta_button(url, label):
    """Przycisk „bulletproof" (tabela + padding) - działa też w Outlooku."""
    return mark_safe(
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0;">'
        f'<tr><td align="center" bgcolor="{ACCENT}" style="border-radius:999px;">'
        f'<a href="{url}" style="display:inline-block;padding:14px 32px;font-family:{FONT};'
        f'font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:999px;">'
        f'{label}</a></td></tr></table>'
    )


def fallback_link(url):
    return mark_safe(
        f'<p style="margin:0 0 14px;font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};">'
        'Gdyby przycisk nie działał, skopiuj ten link do przeglądarki:<br>'
        f'<a href="{url}" style="color:{ACCENT};word-break:break-all;">{url}</a></p>'
    )


def info_box(rows, title=None):
    """Ramka szczegółów: lista par (etykieta, wartość)."""
    inner = ""
    if title:
        inner += (
            f'<div style="font-family:{FONT};font-size:11px;text-transform:uppercase;'
            f'letter-spacing:1px;color:{MUTED};margin:0 0 8px;">{title}</div>'
        )
    for label, value in rows:
        if value in (None, ""):
            continue
        inner += (
            f'<div style="font-family:{FONT};font-size:14px;line-height:1.55;color:{INK};margin:3px 0;">'
            f'<span style="color:{MUTED};">{label}:</span> {value}</div>'
        )
    return mark_safe(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0 18px;">'
        f'<tr><td style="background:{SOFT};border-radius:12px;padding:16px 18px;">{inner}</td></tr></table>'
    )


def order_lines(order):
    """Lista produktów zamówienia + podsumowanie kwot."""
    rows = ""
    for item in order.items.all():
        variant = (
            f' <span style="color:{MUTED};">· {item.variant_name}</span>' if item.variant_name else ""
        )
        rows += (
            "<tr>"
            f'<td style="padding:10px 0;font-family:{FONT};font-size:14px;color:{INK};'
            f'border-bottom:1px solid {LINE};">{item.product_name}{variant}<br>'
            f'<span style="color:{MUTED};font-size:12px;">{item.quantity} × {money(item.unit_price)}</span></td>'
            f'<td align="right" style="padding:10px 0;font-family:{FONT};font-size:14px;font-weight:700;'
            f'color:{INK};border-bottom:1px solid {LINE};white-space:nowrap;">{money(item.line_total)}</td>'
            "</tr>"
        )
    shipping = "gratis" if Decimal(order.shipping_total) == 0 else money(order.shipping_total)
    totals = (
        f'<tr><td style="padding:10px 0 0;font-family:{FONT};font-size:13px;color:{MUTED};">Produkty</td>'
        f'<td align="right" style="padding:10px 0 0;font-family:{FONT};font-size:13px;color:{INK};">{money(order.subtotal)}</td></tr>'
        f'<tr><td style="font-family:{FONT};font-size:13px;color:{MUTED};">Dostawa</td>'
        f'<td align="right" style="font-family:{FONT};font-size:13px;color:{INK};">{shipping}</td></tr>'
        f'<tr><td style="padding-top:8px;font-family:{FONT};font-size:16px;font-weight:700;color:{INK};">Razem</td>'
        f'<td align="right" style="padding-top:8px;font-family:{FONT};font-size:16px;font-weight:700;color:{ACCENT};">{money(order.grand_total)}</td></tr>'
    )
    return mark_safe(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:6px 0 18px;">{rows}{totals}</table>'
    )


def delivery_text(order):
    if order.pickup_point_code:
        text = f"Paczkomat {order.pickup_point_name or order.pickup_point_code}"
        if order.pickup_point_address:
            text += f", {order.pickup_point_address}"
        return text
    parts = [order.shipping_address_line_1]
    if order.shipping_address_line_2:
        parts.append(order.shipping_address_line_2)
    tail = f"{order.shipping_postal_code} {order.shipping_city}".strip()
    if tail:
        parts.append(tail)
    return ", ".join(p for p in parts if p)


# --- Wysyłka: renderuje szablon systemowy (subject + body) i wysyła przez mailer ---

def send_system_email(system_key, *, to_email, context=None, fail_silently=True):
    """Wysyła maila na podstawie szablonu systemowego (z bazy) - treść + temat są
    edytowalne w panelu, a dynamiczne elementy podstawiamy przez kontekst."""
    from .mailer import send_message
    from .models import MessageTemplate

    if not to_email:
        return None
    template = MessageTemplate.objects.filter(system_key=system_key, is_active=True).first()
    if template is None:
        return None
    try:
        return send_message(
            subject=template.subject,
            body_html=template.body_html,
            to_email=to_email,
            context=context or {},
            template=template,
            fail_silently=fail_silently,
        )
    except Exception:
        # Wysyłka maila nigdy nie może wywrócić operacji biznesowej (rejestracja, zakup…).
        return None


# --- Wysokopoziomowe wysyłki poszczególnych maili ---

def send_account_verification(to_email, first_name, link):
    return send_system_email(
        "account-verification",
        to_email=to_email,
        context={
            "first_name": first_name,
            "link": link,
            "cta": cta_button(link, "Potwierdź adres e-mail"),
            "fallback": fallback_link(link),
            "preheader": "Potwierdź adres e-mail, aby aktywować konto.",
        },
    )


def send_password_reset(to_email, first_name, link):
    return send_system_email(
        "password-reset",
        to_email=to_email,
        context={
            "first_name": first_name,
            "link": link,
            "cta": cta_button(link, "Ustaw nowe hasło"),
            "fallback": fallback_link(link),
            "preheader": "Link do ustawienia nowego hasła.",
        },
    )


def send_newsletter_welcome(to_email, discount_code="SPOOKY10"):
    return send_system_email(
        "newsletter-welcome",
        to_email=to_email,
        context={
            "discount_code": discount_code,
            "cta": cta_button(_abs_url(reverse("catalog:product_list")), "Zacznij zakupy"),
            "preheader": f"Twój kod {discount_code} - -10% na pierwsze zakupy.",
        },
    )


def send_order_confirmation(order):
    return send_system_email(
        "order-confirmation",
        to_email=order.email,
        context={
            "first_name": order.first_name,
            "order_number": order.order_number,
            "items": order_lines(order),
            "delivery": delivery_text(order),
            "cta": cta_button(order_status_url(order), "Śledź zamówienie"),
            "preheader": f"Potwierdzenie zamówienia {order.order_number}.",
        },
    )


def _tracking_block(order):
    number = (getattr(order, "tracking_number", "") or "").strip()
    if not number:
        return ""
    url = (getattr(order, "tracking_url", "") or "").strip()
    rows = [("Numer przesyłki", number)]
    box = info_box(rows, title="Śledzenie")
    if url:
        box = mark_safe(box + cta_button(url, "Śledź przesyłkę"))
    return box


def send_order_shipped(order):
    return send_system_email(
        "order-shipped",
        to_email=order.email,
        context={
            "first_name": order.first_name,
            "order_number": order.order_number,
            "tracking": _tracking_block(order),
            "cta": cta_button(order_status_url(order), "Zobacz status zamówienia"),
            "preheader": f"Zamówienie {order.order_number} jest w drodze.",
        },
    )


def send_admin_order_notification(order):
    to_email = (getattr(settings, "ORDER_NOTIFICATION_EMAIL", "") or "").strip()
    if not to_email:
        return None
    panel_url = _abs_url(reverse("dashboard:order_workspace", args=[order.pk]))
    customer = info_box(
        [
            ("Klient", f"{order.first_name} {order.last_name}".strip()),
            ("E-mail", order.email),
            ("Telefon", order.phone),
        ],
        title="Dane klienta",
    )
    return send_system_email(
        "order-admin-notification",
        to_email=to_email,
        context={
            "order_number": order.order_number,
            "total": money(order.grand_total),
            "customer": customer,
            "items": order_lines(order),
            "delivery": delivery_text(order),
            "cta": cta_button(panel_url, "Otwórz w panelu"),
            "preheader": f"Nowe zamówienie {order.order_number} - {money(order.grand_total)}.",
        },
    )
