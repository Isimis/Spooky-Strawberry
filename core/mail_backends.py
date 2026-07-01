"""Backendy e-mail dodające wspólny prefiks do tematu każdej wiadomości.

Prefiks sterowany jest ustawieniem ``MAIL_SUBJECT_PREFIX`` (czytanym z env).
Na środowisku testowym/serwerze ustawiamy np. ``[SERWER TESTOWY] ``, dzięki
czemu wszystkie maile (zamówienia, newsletter, konta itd.) są wyraźnie
oznaczone — niezależnie od miejsca w kodzie, bo wszystko przechodzi przez
backend wysyłki.
"""

from django.conf import settings
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


def apply_subject_prefix(email_messages):
    prefix = (getattr(settings, "MAIL_SUBJECT_PREFIX", "") or "").strip()
    if not prefix:
        return email_messages
    for message in email_messages:
        subject = message.subject or ""
        if not subject.startswith(prefix):
            message.subject = f"{prefix} {subject}".strip()
    return email_messages


class PrefixedSMTPEmailBackend(SMTPEmailBackend):
    def send_messages(self, email_messages):
        return super().send_messages(apply_subject_prefix(email_messages))


class PrefixedConsoleEmailBackend(ConsoleEmailBackend):
    def send_messages(self, email_messages):
        return super().send_messages(apply_subject_prefix(email_messages))
