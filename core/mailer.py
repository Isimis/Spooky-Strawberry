"""Wysyłka maili: szablon bazowy (wzorek) + podstawianie pól + zapis w skrzynce.

Każdy mail wysyłany z panelu owijamy w szablon bazowy (``system_key="base-layout"``),
w którym znacznik ``{{ content }}`` jest zastępowany właściwą treścią. Pola w treści,
np. ``{{ first_name }}`` czy ``{{ order_number }}``, podstawiamy z przekazanego kontekstu.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from .models import Message, MessageTemplate

# system_key szablonu bazowego (wzorka). Owija treść każdego maila.
BASE_LAYOUT_KEY = "base-layout"
# Znacznik w szablonie bazowym, w miejsce którego wstawiamy treść maila.
CONTENT_PLACEHOLDER = "{{ content }}"


def get_base_layout():
    """Zwraca szablon bazowy (MessageTemplate) albo None, jeśli go nie ma."""
    return MessageTemplate.objects.filter(system_key=BASE_LAYOUT_KEY).first()


def render_text(text, context=None):
    """Podstawia pola Django (``{{ ... }}``) w pojedynczym stringu (np. temacie)."""
    if not text:
        return ""
    return Template(text).render(Context(context or {}))


def render_email_html(body_html, context=None):
    """Renderuje treść maila i owija ją w szablon bazowy.

    1. Podstawiamy pola w treści (``{{ first_name }}`` itd.).
    2. Wstawiamy gotową treść do szablonu bazowego pod ``{{ content }}``.
    """
    context = context or {}
    rendered_body = Template(body_html or "").render(Context(context))

    layout = get_base_layout()
    if not (layout and layout.body_html and CONTENT_PLACEHOLDER in layout.body_html):
        return rendered_body

    layout_context = Context({**context, "content": mark_safe(rendered_body)})
    return Template(layout.body_html).render(layout_context)


def send_message(
    *,
    subject,
    body_html,
    to_email,
    context=None,
    from_email=None,
    template=None,
    record=True,
    fail_silently=False,
):
    """Wysyła pojedynczego maila (HTML + tekstowy fallback) i zapisuje go w skrzynce.

    Zwraca utworzony obiekt ``Message`` (lub None, gdy ``record=False``).
    """
    context = context or {}
    rendered_subject = render_text(subject, context)
    html = render_email_html(body_html, context)
    sender = from_email or settings.DEFAULT_FROM_EMAIL

    email = EmailMultiAlternatives(
        subject=rendered_subject,
        body=strip_tags(html),
        from_email=sender,
        to=[to_email],
    )
    email.attach_alternative(html, "text/html")
    email.send(fail_silently=fail_silently)

    # Kopia do folderu „Sent" na IMAP → mail widoczny także w webmailu (nie tylko w panelu).
    # Best-effort: nie może wpłynąć na wysyłkę ani ją wywrócić.
    try:
        from .mailbox import append_to_sent

        append_to_sent(email.message().as_bytes())
    except Exception:
        pass

    if not record:
        return None

    return Message.objects.create(
        direction=Message.DIRECTION_OUTBOUND,
        status=Message.STATUS_SENT,
        subject=rendered_subject,
        body_html=html,
        from_email=sender if "@" in sender and "<" not in sender else (settings.EMAIL_HOST_USER or ""),
        to_email=to_email,
        template=template,
        sent_at=timezone.now(),
    )


def send_bulk(
    *,
    subject,
    body_html,
    recipients,
    context_for=None,
    from_email=None,
    template=None,
):
    """Wysyła tego samego maila do wielu odbiorców, każdemu osobno.

    ``context_for`` to opcjonalna funkcja ``email -> dict`` z polami do podstawienia
    (np. imię konkretnej klientki). Zwraca ``(wyslane, bledy)`` - listy adresów.
    """
    sent, failed = [], []
    for email in recipients:
        context = context_for(email) if context_for else {}
        try:
            send_message(
                subject=subject,
                body_html=body_html,
                to_email=email,
                context=context,
                from_email=from_email,
                template=template,
                fail_silently=False,
            )
            sent.append(email)
        except Exception:
            failed.append(email)
    return sent, failed
