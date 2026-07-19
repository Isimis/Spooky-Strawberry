from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Aesthetic, Category, Product
from orders.models import Order

from .mail_backends import apply_subject_prefix
from .mailbox import MailboxConfigurationError, import_email_message, sync_mailbox
from .models import Message, NewsletterSubscriber


class SearchDiscoveryTests(TestCase):
    def test_robots_points_to_the_xml_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Sitemap:")
        self.assertContains(response, "/sitemap.xml")

    def test_xml_sitemap_is_public(self):
        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<urlset", status_code=200)
        self.assertContains(response, "/sklep/", status_code=200)

    def test_human_readable_sitemap_is_public(self):
        response = self.client.get(reverse("core:sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mapa strony")


class HomeAestheticsTests(TestCase):
    def test_home_lists_every_active_aesthetic(self):
        for number in range(1, 10):
            Aesthetic.objects.create(
                name=f"Estetyka {number}",
                slug=f"estetyka-{number}",
                is_active=True,
                sort_order=number,
            )
        Aesthetic.objects.create(name="Ukryta", slug="ukryta", is_active=False)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["aesthetics"].count(), 9)
        self.assertContains(response, "Estetyka 9")
        self.assertNotContains(response, "Ukryta")


class DesignSystemTests(TestCase):
    def test_design_system_uses_full_size_cards_and_working_controls(self):
        category = Category.objects.create(name="Chokery", slug="chokery-design")
        Product.objects.create(
            name="Choker testowy",
            slug="choker-testowy",
            category=category,
            regular_price="29.00",
            status=Product.STATUS_ACTIVE,
        )
        Aesthetic.objects.create(name="Soft Goth", slug="soft-goth-design", is_active=True)

        response = self.client.get(reverse("core:design_system"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ds-card-preview--product")
        self.assertContains(response, "ds-card-preview--aesthetic")
        self.assertContains(response, "data-demo-size")
        self.assertContains(response, reverse("core:search"))


class OrderStatusByTokenTests(TestCase):
    def _order(self):
        order = Order.objects.create(
            email="klientka@example.pl",
            first_name="Ada",
            last_name="Nowak",
            status=Order.STATUS_PLACED,
            subtotal=Decimal("29.00"),
            grand_total=Decimal("29.00"),
        )
        order.order_number = f"SS-{10000 + order.pk}"
        order.save(update_fields=["order_number"])
        return order

    def test_token_opens_order_without_entering_data(self):
        order = self._order()
        response = self.client.get(
            reverse("core:order_status")
            + f"?number={order.order_number}&token={order.confirmation_token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)

    def test_wrong_token_shows_not_found(self):
        self._order()
        response = self.client.get(reverse("core:order_status") + "?token=zly-token")
        self.assertEqual(response.status_code, 200)
        # Nieprawidłowy token nie ujawnia prywatnych danych zamówienia.
        self.assertNotContains(response, "klientka@example.pl")

    def test_status_page_prefills_logged_in_email(self):
        User = get_user_model()
        User.objects.create_user(username="ala@example.pl", email="ala@example.pl", password="spookypass123")
        self.client.login(username="ala@example.pl", password="spookypass123")
        response = self.client.get(reverse("core:order_status"))
        self.assertEqual(response.status_code, 200)
        # E-mail zalogowanego klienta podstawia się w formularzu, ale bez auto-wyszukiwania.
        self.assertContains(response, 'value="ala@example.pl"')
        self.assertNotContains(response, "Nie znaleźliśmy")


class MailboxDisabledTests(TestCase):
    @override_settings(MAILBOX_ENABLED=False)
    def test_sync_disabled_raises_configuration_error(self):
        with self.assertRaises(MailboxConfigurationError):
            sync_mailbox()


class SystemEmailTests(TestCase):
    """Sprawdza, że każdy systemowy mail wychodzi, jest owinięty w szablon bazowy
    (spójny wygląd) i zawiera właściwą treść."""

    def _order(self, **extra):
        from catalog.models import Category, Product, ProductVariant
        from orders.models import OrderItem

        category = Category.objects.create(name="Chokery", slug="mail-chokery")
        product = Product.objects.create(
            name="Aksamitka", slug="mail-aksamitka", category=category,
            regular_price=Decimal("39.00"), status=Product.STATUS_ACTIVE,
        )
        variant = ProductVariant.objects.create(product=product, stock_quantity=5, is_active=True)
        order = Order.objects.create(
            email="klientka@example.pl", first_name="Ada", last_name="Nowak", phone="500600700",
            shipping_address_line_1="Ciemna 13", shipping_postal_code="00-001", shipping_city="Warszawa",
            status=Order.STATUS_PLACED, subtotal=Decimal("39.00"),
            shipping_total=Decimal("0.00"), grand_total=Decimal("39.00"), **extra,
        )
        order.order_number = f"SS-{10000 + order.pk}"
        order.save(update_fields=["order_number"])
        OrderItem.objects.create(
            order=order, product=product, variant=variant, product_name="Aksamitka",
            quantity=1, unit_price=Decimal("39.00"), line_total=Decimal("39.00"),
        )
        return order

    def _html(self):
        from django.core import mail

        self.assertTrue(mail.outbox, "Brak wysłanego maila")
        msg = mail.outbox[-1]
        html = msg.alternatives[0][0]
        # Każdy mail owinięty szablonem bazowym (nagłówek + stopka).
        self.assertIn("akcesoria alternatywne", html)
        self.assertIn("kontakt@spookystrawberry.pl", html)
        return msg, html

    def test_account_verification(self):
        from core.emails import send_account_verification

        send_account_verification("nowa@example.pl", "Ada", "https://spookystrawberry.pl/konto/potwierdz/x/y/")
        msg, html = self._html()
        self.assertEqual(msg.to, ["nowa@example.pl"])
        self.assertIn("Potwierdź", msg.subject)
        self.assertIn("https://spookystrawberry.pl/konto/potwierdz/x/y/", html)
        self.assertIn("Ada", html)

    def test_password_reset(self):
        from core.emails import send_password_reset

        send_password_reset("nowa@example.pl", "Ada", "https://spookystrawberry.pl/konto/reset/x/y/")
        msg, html = self._html()
        self.assertIn("hasł", msg.subject.lower())
        self.assertIn("https://spookystrawberry.pl/konto/reset/x/y/", html)

    def test_newsletter_welcome_has_code(self):
        from core.emails import send_newsletter_welcome

        send_newsletter_welcome("nowa@example.pl")
        msg, html = self._html()
        self.assertIn("SPOOKY10", html)

    @override_settings(SITE_BASE_URL="https://spookystrawberry.pl")
    def test_order_confirmation(self):
        from core.emails import send_order_confirmation

        order = self._order()
        send_order_confirmation(order)
        msg, html = self._html()
        self.assertEqual(msg.to, ["klientka@example.pl"])
        self.assertIn(order.order_number, html)
        self.assertIn("Aksamitka", html)
        self.assertIn("Śledź zamówienie", html)
        self.assertIn(f"token={order.confirmation_token}", html)

    @override_settings(SITE_BASE_URL="https://spookystrawberry.pl")
    def test_order_shipped_with_tracking(self):
        from core.emails import send_order_shipped

        order = self._order(tracking_number="PL123456789", tracking_url="https://track/PL123456789")
        send_order_shipped(order)
        msg, html = self._html()
        self.assertIn(order.order_number, html)
        self.assertIn("PL123456789", html)
        self.assertIn("drodze", msg.subject.lower())

    @override_settings(ORDER_NOTIFICATION_EMAIL="obsluga@example.pl", SITE_BASE_URL="https://spookystrawberry.pl")
    def test_admin_order_notification(self):
        from core.emails import send_admin_order_notification

        order = self._order()
        send_admin_order_notification(order)
        msg, html = self._html()
        self.assertEqual(msg.to, ["obsluga@example.pl"])
        self.assertIn(order.order_number, html)
        self.assertIn("klientka@example.pl", html)

    @override_settings(ORDER_NOTIFICATION_EMAIL="")
    def test_admin_notification_skipped_when_unset(self):
        from django.core import mail

        from core.emails import send_admin_order_notification

        send_admin_order_notification(self._order())
        self.assertEqual(len(mail.outbox), 0)


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
        # Kod NIE może być ujawniony w potwierdzeniu - ma przyjść mailem.
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

    @override_settings(MAILBOX_IMAP_USER="kontakt@spookystrawberry.pl", MAILBOX_IMAP_FOLDER="INBOX")
    def test_existing_message_gets_attachment_during_a_later_sync(self):
        raw_without_attachment = (
            "From: Sklep <kontakt@spookystrawberry.pl>\r\n"
            "To: kontakt@spookystrawberry.pl\r\n"
            "Subject: Backup\r\n"
            "Message-ID: <backup-1@example.pl>\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Wiadomosc z backupem.\r\n"
        ).encode("utf-8")
        raw_with_attachment = (
            "From: Sklep <kontakt@spookystrawberry.pl>\r\n"
            "To: kontakt@spookystrawberry.pl\r\n"
            "Subject: Backup\r\n"
            "Message-ID: <backup-1@example.pl>\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: multipart/mixed; boundary=backup\r\n\r\n"
            "--backup\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
            "Wiadomosc z backupem.\r\n"
            "--backup\r\nContent-Type: application/octet-stream; name=backup.dump.enc\r\n"
            "Content-Disposition: attachment; filename=backup.dump.enc\r\n"
            "Content-Transfer-Encoding: base64\r\n\r\n"
            "dGVzdC1iYWNrdXAK\r\n--backup--\r\n"
        ).encode("utf-8")

        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
            MESSAGE_ATTACHMENT_ROOT=media_root,
        ):
            first = import_email_message("102", raw_without_attachment)
            second = import_email_message("102", raw_with_attachment)
            attachment = first.attachments.get()

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            self.assertEqual(attachment.filename, "backup.dump.enc")
            attachment.file.open("rb")
            self.assertEqual(attachment.file.read(), b"test-backup\n")
            attachment.file.close()


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
