from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from django.urls import reverse

from .mail_backends import apply_subject_prefix
from .mailbox import import_email_message
from .models import Message, NewsletterSubscriber


class NewsletterTests(TestCase):
    def test_newsletter_subscribe_creates_subscriber(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "test@example.com", "next": reverse("core:home")},
        )

        self.assertRedirects(response, reverse("core:newsletter_thanks"))
        self.assertTrue(NewsletterSubscriber.objects.filter(email="test@example.com").exists())

    def test_duplicate_newsletter_subscribe_returns_to_next(self):
        NewsletterSubscriber.objects.create(email="dup@example.com")
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "dup@example.com", "next": reverse("core:home")},
        )
        self.assertRedirects(response, reverse("core:home"))

    def test_newsletter_thanks_renders(self):
        response = self.client.get(reverse("core:newsletter_thanks"))
        self.assertContains(response, "SPOOKY10")

    def test_newsletter_ajax_returns_json_and_sets_session(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "ajax@example.com"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["created"])
        # Kod NIE może być ujawniony w potwierdzeniu — ma przyjść mailem.
        self.assertNotIn("SPOOKY10", data["message"])
        self.assertIn("ajax@example.com", data["message"])
        self.assertEqual(self.client.session["newsletter_email"], "ajax@example.com")
        self.assertTrue(NewsletterSubscriber.objects.filter(email="ajax@example.com").exists())


class SearchTests(TestCase):
    def test_search_no_results_shows_empty_state(self):
        response = self.client.get(reverse("core:search"), {"q": "zzzqqq-brak"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brak wyników")


class ContactFormTests(TestCase):
    def test_contact_form_creates_inbound_message(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "name": "Maja",
                "email": "maja@example.pl",
                "subject": "Zwrot / reklamacja",
                "message": "Chcialabym zapytac o zwrot.",
            },
        )

        self.assertRedirects(response, reverse("core:contact"))
        message = Message.objects.get()
        self.assertEqual(message.direction, Message.DIRECTION_INBOUND)
        self.assertEqual(message.status, Message.STATUS_RECEIVED)
        self.assertEqual(message.from_email, "maja@example.pl")
        self.assertIsNone(message.read_at)
        self.assertIn("Zwrot / reklamacja", message.subject)
        self.assertIn("Chcialabym zapytac o zwrot.", message.body_html)


class MailboxImportTests(TestCase):
    @override_settings(MAILBOX_IMAP_USER="kontakt@spookystrawberry.pl", MAILBOX_IMAP_FOLDER="INBOX")
    def test_import_email_message_creates_inbound_message_once(self):
        raw_message = (
            "From: Klientka <klientka@example.pl>\r\n"
            "To: kontakt@spookystrawberry.pl\r\n"
            "Subject: Zwrot zamowienia\r\n"
            "Message-ID: <return-1@example.pl>\r\n"
            "Date: Tue, 30 Jun 2026 10:15:00 +0200\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            "Dzien dobry,\r\nchcialabym zglosic zwrot.\r\n"
        ).encode("utf-8")

        first = import_email_message("101", raw_message)
        second = import_email_message("101", raw_message)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.get()
        self.assertEqual(message.direction, Message.DIRECTION_INBOUND)
        self.assertEqual(message.status, Message.STATUS_RECEIVED)
        self.assertEqual(message.from_email, "klientka@example.pl")
        self.assertEqual(message.to_email, "kontakt@spookystrawberry.pl")
        self.assertEqual(message.external_id, "message-id:<return-1@example.pl>")
        self.assertIsNone(message.read_at)
        self.assertIn("zglosic zwrot", message.body_html)


class MailBackendTests(TestCase):
    @override_settings(MAIL_SUBJECT_PREFIX="[SERWER TESTOWY]")
    def test_apply_subject_prefix_adds_prefix_once(self):
        message = EmailMessage(subject="Test")

        apply_subject_prefix([message])
        apply_subject_prefix([message])

        self.assertEqual(message.subject, "[SERWER TESTOWY] Test")

    @override_settings(MAIL_SUBJECT_PREFIX="")
    def test_apply_subject_prefix_skips_empty_prefix(self):
        message = EmailMessage(subject="Test")

        apply_subject_prefix([message])

        self.assertEqual(message.subject, "Test")


@override_settings(
    CANONICAL_HOST="spookystrawberry.pl",
    ALLOWED_HOSTS=["spookystrawberry.pl", "www.spookystrawberry.pl", "testserver"],
)
class CanonicalHostMiddlewareTests(TestCase):
    def test_www_redirects_to_canonical(self):
        resp = self.client.get("/", HTTP_HOST="www.spookystrawberry.pl")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], "http://spookystrawberry.pl/")

    def test_canonical_host_not_redirected(self):
        resp = self.client.get("/", HTTP_HOST="spookystrawberry.pl")
        self.assertNotEqual(resp.status_code, 301)

    @override_settings(CANONICAL_HOST="")
    def test_disabled_when_unset(self):
        resp = self.client.get("/", HTTP_HOST="www.spookystrawberry.pl")
        self.assertNotEqual(resp.status_code, 301)


class OrderStatusTimelineTests(TestCase):
    def _order(self, status):
        from decimal import Decimal
        from orders.models import Order
        return Order.objects.create(email="a@b.pl", first_name="A", last_name="B", status=status, grand_total=Decimal("10"))

    def test_placed_marks_placed_and_payment_done(self):
        from core.views import build_status_timeline
        from orders.models import Order
        s = build_status_timeline(self._order(Order.STATUS_PLACED))
        self.assertEqual(s[0]["state"], "done")   # Zamówienie złożone
        self.assertEqual(s[1]["state"], "done")   # Płatność potwierdzona
        self.assertEqual(s[2]["state"], "active")  # Spakowane

    def test_awaiting_payment_marks_payment_active(self):
        from core.views import build_status_timeline
        from orders.models import Order
        s = build_status_timeline(self._order(Order.STATUS_AWAITING_PAYMENT))
        self.assertEqual(s[0]["state"], "done")
        self.assertEqual(s[1]["state"], "active")

    def test_shipped_progresses_further(self):
        from core.views import build_status_timeline
        from orders.models import Order
        s = build_status_timeline(self._order(Order.STATUS_SHIPPED))
        self.assertEqual([x["state"] for x in s[:4]], ["done", "done", "done", "done"])
        self.assertEqual(s[4]["state"], "active")
