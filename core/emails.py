"""Wysyłka systemowych maili na bazie szablonów z panelu.

Zasada podziału (żeby edycja w panelu miała sens):
- CAŁA treść maila (nagłówki, teksty, przyciski, kod rabatowy) mieszka w szablonie
  (MessageTemplate) i jest w pełni widoczna oraz edytowalna w panelu.
- Placeholdery ({{ ... }}) istnieją TYLKO dla danych, które naprawdę zmieniają się
  przy każdej wysyłce: imię, numer zamówienia, lista produktów, adres dostawy,
  linki z jednorazowymi tokenami itd. Kod podstawia wartości - nic więcej.

Wygląd (ramka, nagłówek, stopka, responsywność) daje szablon bazowy `base-layout`.
Wysyłamy przez panelowy mailer (`send_message`), więc każdy mail trafia też do
skrzynki panelu i (na produkcji) do folderu „Sent" w webmailu.
"""

from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

# Paleta i fonty - używane przy budowaniu dynamicznych bloków (lista produktów).
ACCENT = "#c2185b"
INK = "#1c1620"
MUTED = "#6c6470"
LINE = "#efe7ee"
FONT = "Arial,Helvetica,sans-serif"


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


# --- Dynamiczne bloki (jedyne rzeczy, których nie da się wpisać ręcznie w szablonie) ---

def order_lines(order):
    """Lista produktów zamówienia + podsumowanie kwot (tabela, inline CSS)."""
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
    discount = ""
    if Decimal(order.discount_total) > 0:
        code = f" · {order.discount_code.code}" if order.discount_code_id else ""
        discount = (
            f'<tr><td style="font-family:{FONT};font-size:13px;color:{MUTED};">Rabat{code}</td>'
            f'<td align="right" style="font-family:{FONT};font-size:13px;color:{INK};">-{money(order.discount_total)}</td></tr>'
        )
    totals = (
        f'<tr><td style="padding:10px 0 0;font-family:{FONT};font-size:13px;color:{MUTED};">Produkty</td>'
        f'<td align="right" style="padding:10px 0 0;font-family:{FONT};font-size:13px;color:{INK};">{money(order.subtotal)}</td></tr>'
        + discount
        + f'<tr><td style="font-family:{FONT};font-size:13px;color:{MUTED};">Dostawa</td>'
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
    """Wysyła maila na podstawie szablonu z panelu, podstawiając pola z kontekstu."""
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
        # Wysyłka maila nigdy nie może wywrócić operacji biznesowej (rejestracja, zakup...).
        return None


# --- Wysokopoziomowe wysyłki poszczególnych maili ---

def send_account_verification(to_email, first_name, link):
    return send_system_email(
        "account-verification",
        to_email=to_email,
        context={
            "first_name": first_name,
            "link": link,
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
            "preheader": "Link do ustawienia nowego hasła.",
        },
    )


def send_newsletter_welcome(to_email):
    # Ten mail nie ma żadnych zmiennych - cała treść (w tym kod rabatowy i przycisk)
    # jest wpisana wprost w szablonie i edytowalna w panelu.
    return send_system_email(
        "newsletter-welcome",
        to_email=to_email,
        context={"preheader": "Twój kod rabatowy na pierwsze zakupy."},
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
            "status_url": order_status_url(order),
            "preheader": f"Potwierdzenie zamówienia {order.order_number}.",
        },
    )


def _tracking_block(order):
    """Ramka z numerem przesyłki (+ opcjonalny przycisk śledzenia). Pusta, gdy brak numeru.
    To treść warunkowa/dynamiczna, więc budujemy ją w kodzie zamiast {% if %} w szablonie."""
    from .email_seed import INFO_BOX_CLOSE, INFO_BOX_OPEN, button

    number = (order.tracking_number or "").strip()
    if not number:
        return ""
    html = (
        INFO_BOX_OPEN
        + '<span style="color:#6c6470;">Numer przesyłki:</span> <strong>' + number + "</strong>"
        + INFO_BOX_CLOSE
    )
    url = (order.tracking_url or "").strip()
    if url:
        html += button(url, "Śledź przesyłkę")
    return mark_safe(html)


def send_order_shipped(order):
    return send_system_email(
        "order-shipped",
        to_email=order.email,
        context={
            "first_name": order.first_name,
            "order_number": order.order_number,
            "tracking": _tracking_block(order),
            "status_url": order_status_url(order),
            "preheader": f"Zamówienie {order.order_number} jest w drodze.",
        },
    )


def send_admin_order_notification(order):
    to_email = (getattr(settings, "ORDER_NOTIFICATION_EMAIL", "") or "").strip()
    if not to_email:
        return None
    return send_system_email(
        "order-admin-notification",
        to_email=to_email,
        context={
            "order_number": order.order_number,
            "total": money(order.grand_total),
            "customer_name": f"{order.first_name} {order.last_name}".strip(),
            "customer_email": order.email,
            "customer_phone": order.phone or "-",
            "items": order_lines(order),
            "delivery": delivery_text(order),
            "panel_url": _abs_url(reverse("dashboard:order_workspace", args=[order.pk])),
            "preheader": f"Nowe zamówienie {order.order_number} na {money(order.grand_total)}.",
        },
    )
