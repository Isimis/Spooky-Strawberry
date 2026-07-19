import html
import hashlib
import imaplib
import logging
import os
import time
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import get_valid_filename
from django.utils import timezone

from .models import Message, MessageAttachment

logger = logging.getLogger(__name__)


class MailboxConfigurationError(RuntimeError):
    pass


def mailbox_is_configured():
    return all(
        [
            settings.MAILBOX_IMAP_HOST,
            settings.MAILBOX_IMAP_USER,
            settings.MAILBOX_IMAP_PASSWORD,
        ]
    )


def mailbox_enabled():
    """Czy skrzynka IMAP jest w ogóle aktywna na tym środowisku (lokalnie wyłączona)."""
    return bool(getattr(settings, "MAILBOX_ENABLED", False)) and mailbox_is_configured()


def append_to_sent(raw_bytes):
    """Best-effort: dokłada kopię wysłanego maila do folderu „Sent" na serwerze IMAP.

    Dzięki temu wychodzące wiadomości są widoczne także w webmailu, nie tylko w panelu.
    Nigdy nie rzuca wyjątkiem - wysyłka maila nie może zależeć od dostępności IMAP.
    """
    if not (getattr(settings, "MAILBOX_SAVE_SENT", False) and mailbox_enabled()):
        return False
    folder = getattr(settings, "MAILBOX_IMAP_SENT_FOLDER", "Sent") or "Sent"
    client = None
    try:
        client = _connect()
        client.append(folder, r"(\Seen)", imaplib.Time2Internaldate(time.time()), raw_bytes)
        return True
    except Exception as exc:  # noqa: BLE001 - zapis do Sent jest opcjonalny
        logger.warning("Nie udało się zapisać kopii maila w folderze Sent: %s", exc)
        return False
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def _connect():
    if not mailbox_is_configured():
        raise MailboxConfigurationError("Brakuje konfiguracji IMAP w zmiennych środowiskowych.")

    if settings.MAILBOX_IMAP_USE_SSL:
        client = imaplib.IMAP4_SSL(settings.MAILBOX_IMAP_HOST, settings.MAILBOX_IMAP_PORT)
    else:
        client = imaplib.IMAP4(settings.MAILBOX_IMAP_HOST, settings.MAILBOX_IMAP_PORT)
    client.login(settings.MAILBOX_IMAP_USER, settings.MAILBOX_IMAP_PASSWORD)
    return client


def _decode_addresses(value):
    addresses = [email for _, email in getaddresses([value or ""]) if email]
    return ", ".join(addresses)


def _message_body(message):
    html_body = ""
    text_body = ""
    is_delivery_report = message.get_content_type() == "multipart/report"

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if part.is_multipart() or content_type in {"message/rfc822", "message/delivery-status"}:
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if content_type == "text/plain" and not text_body:
                text_body = part.get_content()
                if is_delivery_report:
                    break
            elif content_type == "text/html" and not html_body:
                html_body = part.get_content()
    else:
        if message.get_content_type() == "text/html":
            html_body = message.get_content()
        elif message.get_content_type() == "text/plain":
            text_body = message.get_content()

    if html_body and not is_delivery_report:
        return html_body
    if text_body:
        escaped = html.escape(text_body).replace("\n", "<br>")
        return f"<p>{escaped}</p>"
    return "<p>(Wiadomość bez treści)</p>"


def _received_at(message):
    raw_date = message.get("Date")
    if not raw_date:
        return timezone.now()
    try:
        parsed = parsedate_to_datetime(raw_date)
    except (TypeError, ValueError, IndexError):
        return timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed.astimezone(timezone.get_current_timezone())


def _external_id(uid, message):
    message_id = (message.get("Message-ID") or "").strip()
    if message_id:
        return f"message-id:{message_id[:240]}"
    return f"imap:{settings.MAILBOX_IMAP_USER}:{settings.MAILBOX_IMAP_FOLDER}:{uid}"


def _attachment_parts(message):
    """Zwraca binarną zawartość każdego rzeczywistego załącznika wiadomości."""
    index = 0
    for part in message.walk():
        if part.is_multipart() or part.get_content_type() in {"message/rfc822", "message/delivery-status"}:
            continue

        disposition = part.get_content_disposition()
        raw_filename = part.get_filename()
        if disposition not in {"attachment", "inline"} and not raw_filename:
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        index += 1
        basename = os.path.basename((raw_filename or "").replace("\\", "/"))
        filename = get_valid_filename(basename) or f"zalacznik-{index}"
        yield filename, part.get_content_type() or "application/octet-stream", payload


def _store_attachments(message_record, parsed_message):
    """Zapisuje załączniki i bezpiecznie pomija te już zapisane przy ponownej synchronizacji."""
    for filename, content_type, payload in _attachment_parts(parsed_message):
        checksum = hashlib.sha256(payload).hexdigest()
        if MessageAttachment.objects.filter(message=message_record, checksum=checksum).exists():
            continue
        attachment = MessageAttachment(
            message=message_record,
            filename=filename[:255],
            content_type=content_type[:120],
            size=len(payload),
            checksum=checksum,
        )
        attachment.file.save(filename, ContentFile(payload), save=False)
        attachment.save()


def import_email_message(uid, raw_bytes):
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    external_id = _external_id(uid, message)
    existing = Message.objects.filter(external_id=external_id).first()
    if existing:
        _store_attachments(existing, message)
        return None

    with transaction.atomic():
        imported = Message.objects.create(
            direction=Message.DIRECTION_INBOUND,
            status=Message.STATUS_RECEIVED,
            subject=(message.get("Subject") or "").strip()[:200],
            body_html=_message_body(message),
            from_email=_decode_addresses(message.get("From"))[:254],
            to_email=_decode_addresses(message.get("To"))[:254],
            external_id=external_id,
            received_at=_received_at(message),
        )
        _store_attachments(imported, message)
    return imported


def sync_mailbox(limit=None):
    if not mailbox_enabled():
        raise MailboxConfigurationError(
            "Skrzynka pocztowa jest wyłączona na tym środowisku (np. serwer lokalny)."
        )
    limit = limit or settings.MAILBOX_SYNC_LIMIT
    imported = []

    client = _connect()
    try:
        status, _ = client.select(settings.MAILBOX_IMAP_FOLDER, readonly=True)
        if status != "OK":
            raise MailboxConfigurationError(f"Nie udało się otworzyć folderu IMAP: {settings.MAILBOX_IMAP_FOLDER}.")

        status, data = client.uid("search", None, "ALL")
        if status != "OK":
            raise MailboxConfigurationError("Nie udało się pobrać listy wiadomości z IMAP.")

        uids = data[0].split()[-limit:]
        for uid in reversed(uids):
            status, fetched = client.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not fetched:
                continue
            for item in fetched:
                if not isinstance(item, tuple):
                    continue
                obj = import_email_message(uid.decode("ascii", errors="ignore"), item[1])
                if obj is not None:
                    imported.append(obj)
                break
    finally:
        try:
            client.close()
        except imaplib.IMAP4.error:
            pass
        client.logout()

    return imported
