from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch

from analytics.models import AnalyticsEvent, AnalyticsSession
from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size
from core.models import Message, NewsletterSubscriber
from dashboard.forms import OrderDashboardForm
from dashboard.models import DataQualityIssue
from dashboard.registry import get_model_config, get_sections
from dashboard.services import get_dashboard_analytics
from dashboard.views import filter_product_image_files, sync_product_main_image
from orders.models import DiscountCode, Order, OrderItem, ShippingMethod
from outfits.models import Outfit, OutfitHotspot, OutfitImage, OutfitItem


class OrderTestFlagFormTests(TestCase):
    def test_order_form_exposes_a_single_manual_test_flag(self):
        form = OrderDashboardForm()

        self.assertIn("is_test", form.fields)
        self.assertEqual(form.fields["is_test"].label, "Zamówienie testowe")


class DashboardAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="staff",
            password="pass",
            is_staff=True,
        )
        self.regular_user = user_model.objects.create_user(
            username="regular",
            password="pass",
            is_staff=False,
        )

    def test_dashboard_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response["Location"])

    def test_user_accounts_list_renders_with_type_and_section(self):
        self.client.login(username="staff", password="pass")
        response = self.client.get(reverse("dashboard:model_list", args=["user-accounts"]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/user_account_list.html")
        self.assertContains(response, "Konta użytkowników")
        self.assertContains(response, "Klient")  # typ konta dla zwykłego usera
        self.assertIn("Klienci", get_sections())

    def test_user_account_detail_toggles_staff_access(self):
        self.client.login(username="staff", password="pass")
        url = reverse("dashboard:user_account_detail", args=[self.regular_user.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zarządzanie")

        self.client.post(url, {"action": "toggle_staff"})
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)

    def test_user_account_generic_create_blocked(self):
        self.client.login(username="staff", password="pass")
        create = self.client.get(reverse("dashboard:model_create", args=["user-accounts"]))
        # Generyczny formularz (z hasłem) jest zablokowany - używamy dedykowanego.
        self.assertEqual(create.status_code, 302)

    def test_user_account_detail_lists_all_consents(self):
        self.client.login(username="staff", password="pass")
        response = self.client.get(reverse("dashboard:user_account_detail", args=[self.regular_user.pk]))
        self.assertContains(response, "Potwierdzenie e-mail")
        self.assertContains(response, "Zgoda marketingowa")
        self.assertContains(response, "Newsletter")
        # Zgody systemowe / niekontrolowalne nie są tu wymieniane.
        self.assertNotContains(response, "Pliki cookie")

    def test_user_account_create_view(self):
        self.client.login(username="staff", password="pass")
        response = self.client.post(
            reverse("dashboard:user_account_create"),
            {"email": "Nowa@Example.PL", "password": "spookypass123", "accepts_marketing": "on"},
        )
        user_model = get_user_model()
        new_user = user_model.objects.get(email__iexact="nowa@example.pl")
        self.assertRedirects(response, reverse("dashboard:user_account_detail", args=[new_user.pk]))
        self.assertEqual(new_user.username, "nowa@example.pl")
        self.assertTrue(new_user.customer_profile.accepts_marketing)

    def test_email_templates_list_and_edit(self):
        from core.models import MessageTemplate

        self.client.login(username="staff", password="pass")
        list_resp = self.client.get(reverse("dashboard:model_list", args=["email-templates"]))
        self.assertEqual(list_resp.status_code, 200)
        self.assertTemplateUsed(list_resp, "dashboard/email_template_list.html")
        self.assertContains(list_resp, "Szablony maili")
        self.assertIn("Komunikacja", get_sections())

        tpl = MessageTemplate.objects.filter(is_system=True).first()
        self.assertIsNotNone(tpl)
        edit_page = self.client.get(reverse("dashboard:email_template_edit", args=[tpl.pk]))
        self.assertEqual(edit_page.status_code, 200)
        self.assertTemplateUsed(edit_page, "dashboard/email_template_form.html")
        self.assertContains(edit_page, "data-mc-area")
        edit = self.client.post(
            reverse("dashboard:email_template_edit", args=[tpl.pk]),
            {"subject": "Nowy temat testowy", "body_html": "<p>Cześć</p>", "is_active": "on"},
        )
        self.assertEqual(edit.status_code, 302)
        tpl.refresh_from_db()
        self.assertEqual(tpl.subject, "Nowy temat testowy")

    def test_messages_hub_list_compose_detail(self):
        from core.models import Message

        self.client.login(username="staff", password="pass")
        list_resp = self.client.get(reverse("dashboard:model_list", args=["messages"]))
        self.assertEqual(list_resp.status_code, 200)
        self.assertTemplateUsed(list_resp, "dashboard/message_list.html")
        self.assertContains(list_resp, "Skrzynka")
        self.assertContains(list_resp, "Odśwież pocztę")

        compose = self.client.post(
            reverse("dashboard:message_compose"),
            {"to_email": "klient@example.pl", "subject": "Cześć", "body_html": "<p>Test</p>"},
        )
        message = Message.objects.get(to_email="klient@example.pl")
        self.assertRedirects(compose, reverse("dashboard:message_detail", args=[message.pk]))
        self.assertEqual(message.direction, Message.DIRECTION_OUTBOUND)
        self.assertEqual(message.status, Message.STATUS_SENT)

        detail = self.client.get(reverse("dashboard:message_detail", args=[message.pk]))
        self.assertContains(detail, "Cześć")

    def test_message_compose_sends_and_records_attachments(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings

        self.client.login(username="staff", password="pass")
        attachment = SimpleUploadedFile("instrukcja.pdf", b"pdf-content", content_type="application/pdf")

        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
            MESSAGE_ATTACHMENT_ROOT=media_root,
        ):
            response = self.client.post(
                reverse("dashboard:message_compose"),
                {
                    "to_email": "klient@example.pl",
                    "subject": "Dokument",
                    "body_html": "<p>W załączniku.</p>",
                    "attachments": attachment,
                },
            )
            message = Message.objects.get(to_email="klient@example.pl")
            stored = message.attachments.get()
            download = self.client.get(reverse("dashboard:message_attachment_download", args=[stored.pk]))

            self.assertRedirects(response, reverse("dashboard:message_detail", args=[message.pk]))
            self.assertEqual(stored.filename, "instrukcja.pdf")
            stored.file.open("rb")
            self.assertEqual(stored.file.read(), b"pdf-content")
            stored.file.close()
            self.assertEqual(download.status_code, 200)
            self.assertEqual(b"".join(download.streaming_content), b"pdf-content")

    def test_unread_inbound_message_shows_in_topbar_and_marks_read(self):
        from core.models import Message

        message = Message.objects.create(
            direction=Message.DIRECTION_INBOUND,
            status=Message.STATUS_RECEIVED,
            subject="Nowa odpowiedź",
            body_html="<p>Treść odpowiedzi klientki.</p>",
            from_email="klientka@example.pl",
            to_email="kontakt@spookystrawberry.pl",
            received_at=timezone.now(),
        )

        self.client.login(username="staff", password="pass")
        home_response = self.client.get(reverse("dashboard:home"))
        list_response = self.client.get(reverse("dashboard:model_list", args=["messages"]), {"box": "inbound"})
        detail_response = self.client.get(reverse("dashboard:message_detail", args=[message.pk]))

        self.assertContains(home_response, "dashboard-mail-alert is-hot")
        self.assertContains(home_response, "<strong>1</strong>", html=True)
        self.assertContains(list_response, "dashboard-message-row--unread")
        self.assertContains(list_response, "Nowa")
        self.assertContains(detail_response, "Wiadomość przychodząca")
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

        home_after_read = self.client.get(reverse("dashboard:home"))
        self.assertNotContains(home_after_read, "dashboard-mail-alert is-hot")
        self.assertContains(home_after_read, "<strong>0</strong>", html=True)

    @patch("dashboard.views.sync_mailbox")
    def test_message_sync_button_refreshes_mailbox(self, sync_mailbox_mock):
        sync_mailbox_mock.return_value = []

        self.client.login(username="staff", password="pass")
        response = self.client.post(reverse("dashboard:sync_messages"))

        self.assertRedirects(response, reverse("dashboard:model_list", args=["messages"]))
        sync_mailbox_mock.assert_called_once_with()

    def test_bulk_compose_selects_recipients_and_sends(self):
        from django.core import mail
        from core.models import Message, NewsletterSubscriber

        NewsletterSubscriber.objects.create(email="a@example.pl", is_active=True)
        NewsletterSubscriber.objects.create(email="b@example.pl", is_active=True)

        self.client.login(username="staff", password="pass")

        # Zaznaczenie odbiorców na liście przerzuca ich do edytora.
        bulk = self.client.post(
            reverse("dashboard:bulk_compose"),
            {"emails": ["a@example.pl", "b@example.pl", "a@example.pl"], "back": "/admin/newsletter-subscribers/"},
        )
        self.assertRedirects(bulk, reverse("dashboard:message_compose"))
        self.assertEqual(self.client.session["compose_recipients"], ["a@example.pl", "b@example.pl"])

        compose_page = self.client.get(reverse("dashboard:message_compose"))
        self.assertContains(compose_page, "a@example.pl")
        self.assertContains(compose_page, "Odbiorcy (2)")

        sent = self.client.post(
            reverse("dashboard:message_compose"),
            {"subject": "Drop 🦇", "body_html": "<p>Cześć {{ first_name }}!</p>"},
        )
        self.assertRedirects(sent, reverse("dashboard:model_list", args=["messages"]))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(Message.objects.filter(subject="Drop 🦇").count(), 2)
        # Sesja czyszczona po wysyłce.
        self.assertNotIn("compose_recipients", self.client.session)

    def test_base_layout_wraps_outgoing_mail(self):
        from django.core import mail
        from core.mailer import BASE_LAYOUT_KEY
        from core.models import MessageTemplate

        # Szablon bazowy istnieje, ma własną stronę i nie ląduje w liście szablonów.
        self.assertTrue(MessageTemplate.objects.filter(system_key=BASE_LAYOUT_KEY).exists())

        self.client.login(username="staff", password="pass")
        list_resp = self.client.get(reverse("dashboard:model_list", args=["email-templates"]))
        # Wzorek nie miesza się z listą zwykłych szablonów (ma własną podkategorię).
        self.assertNotContains(list_resp, "Szablon bazowy maili (wzór)")

        edit_page = self.client.get(reverse("dashboard:base_layout_edit"))
        self.assertEqual(edit_page.status_code, 200)
        self.assertTemplateUsed(edit_page, "dashboard/base_layout_form.html")

        self.client.post(
            reverse("dashboard:base_layout_edit"),
            {"body_html": "<div class=\"frame\">RAMKA {{ content }} STOPKA</div>"},
        )

        self.client.post(
            reverse("dashboard:message_compose"),
            {"to_email": "klient@example.pl", "subject": "Test", "body_html": "<p>Środek</p>"},
        )
        self.assertEqual(len(mail.outbox), 1)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn("RAMKA", html_body)
        self.assertIn("Środek", html_body)
        self.assertIn("STOPKA", html_body)
        self.assertNotIn("{{ content }}", html_body)

    def test_user_account_edit_and_delete(self):
        self.client.login(username="staff", password="pass")
        url = reverse("dashboard:user_account_detail", args=[self.regular_user.pk])
        self.client.post(url, {"action": "save", "email": "edited@example.pl", "first_name": "Zo", "accepts_marketing": "on"})
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.email, "edited@example.pl")
        self.assertTrue(self.regular_user.customer_profile.accepts_marketing)

        delete = self.client.post(url, {"action": "delete"})
        self.assertRedirects(delete, reverse("dashboard:model_list", args=["user-accounts"]))
        self.assertFalse(get_user_model().objects.filter(pk=self.regular_user.pk).exists())

    def test_dashboard_rejects_non_staff_user(self):
        self.client.login(username="regular", password="pass")
        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response["Location"])

    def test_staff_user_can_open_dashboard_and_model_list(self):
        self.client.login(username="staff", password="pass")

        home_response = self.client.get(reverse("dashboard:home"))
        list_response = self.client.get(reverse("dashboard:model_list", args=["products"]))

        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "Statystyki")
        self.assertContains(home_response, "Ruch godzinowy")
        self.assertContains(home_response, "Ostatni miesiąc")
        self.assertEqual(list_response.status_code, 200)

    def test_dashboard_shows_analytics_summary(self):
        session = AnalyticsSession.objects.create(
            session_key="test-session",
            referrer="https://www.instagram.com/spookystrawberry",
            device_type="desktop",
            user_agent="Mozilla/5.0 Local Browser",
        )
        AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            path="/sklep/",
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/sklep/")
        self.assertContains(response, "instagram.com")
        self.assertContains(response, "Komputer")

    def test_dashboard_groups_legacy_sessions_by_browser_for_unique_users(self):
        user_agent = "Local Test Browser"
        for session_key in ("legacy-session-1", "legacy-session-2"):
            session = AnalyticsSession.objects.create(
                session_key=session_key,
                user_agent=user_agent,
                device_type="desktop",
            )
            AnalyticsEvent.objects.create(
                session=session,
                event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
                path="/",
            )

        analytics = get_dashboard_analytics()
        today = analytics["summary_cards"][0]

        self.assertEqual(today["sessions"], 2)
        self.assertEqual(today["unique_visitors"], 1)

    def test_staff_user_can_create_model_entry(self):
        self.client.login(username="staff", password="pass")
        response = self.client.post(
            reverse("dashboard:model_create", args=["colors"]),
            {
                "name": "Test Pink",
                "slug": "test-pink",
                "hex_code": "#ff7cad",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Color.objects.filter(slug="test-pink").exists())

    def test_dashboard_registry_moves_newsletter_to_marketing(self):
        sections = get_sections()

        self.assertNotIn("Treści strony", sections)
        self.assertNotIn("Klientki", sections)
        self.assertIsNone(get_model_config("site-pages"))
        self.assertIsNone(get_model_config("homepage-sections"))
        self.assertIsNone(get_model_config("customer-profiles"))
        self.assertIsNone(get_model_config("customer-addresses"))
        self.assertIsNone(get_model_config("favorite-products"))
        self.assertIsNone(get_model_config("checkout-drafts"))
        self.assertIsNone(get_model_config("dashboard-tasks"))
        self.assertIsNone(get_model_config("data-quality-issues"))
        self.assertIsNone(get_model_config("ai-jobs"))
        self.assertIsNone(get_model_config("ai-suggestions"))
        self.assertNotIn("Panel", sections)
        self.assertNotIn("AI", sections)
        self.assertIn("Marketing", sections)
        self.assertEqual([config.label for config in sections["Marketing"]], ["Newsletter"])
        self.assertEqual(
            [config.label for config in sections["Analityka"]],
            ["Sesje analityczne", "Zdarzenia analityczne"],
        )

    def test_analytics_session_list_and_detail_use_custom_readonly_views(self):
        session = AnalyticsSession.objects.create(
            session_key="analytics-session-key",
            visitor_id="visitor-analytics-1",
            device_type="mobile",
            referrer="https://www.instagram.com/spookystrawberry",
            utm_source="instagram",
            utm_medium="social",
            utm_campaign="summer-drop",
            user_agent="Mobile Test Browser",
        )
        AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            path="/",
        )
        AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW,
            path="/produkt/test/",
        )
        self.client.login(username="staff", password="pass")

        list_response = self.client.get(
            reverse("dashboard:model_list", args=["analytics-sessions"]),
            {"device": "mobile", "source": "campaign"},
        )
        detail_response = self.client.get(
            reverse("dashboard:model_edit", args=["analytics-sessions", session.id])
        )
        create_response = self.client.get(
            reverse("dashboard:model_create", args=["analytics-sessions"])
        )
        delete_response = self.client.get(
            reverse("dashboard:model_delete", args=["analytics-sessions", session.id])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "dashboard/analytics_session_list.html")
        self.assertContains(list_response, "Sesje analityczne")
        self.assertContains(list_response, "Telefon")
        self.assertContains(list_response, "instagram")
        self.assertEqual(list_response.context["rows"][0]["event_count"], 2)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "dashboard/analytics_session_detail.html")
        self.assertContains(detail_response, "Ścieżka użytkowniczki")
        self.assertContains(detail_response, "/produkt/test/")
        self.assertContains(detail_response, "summer-drop")
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(delete_response.status_code, 302)
        self.assertTrue(AnalyticsSession.objects.filter(pk=session.pk).exists())

    def test_analytics_event_list_and_detail_show_metadata_and_session(self):
        product = self.create_product("Analytics Choker", "analytics-choker")
        session = AnalyticsSession.objects.create(
            session_key="event-session-key",
            visitor_id="event-visitor",
            device_type="desktop",
            user_agent="Desktop Test Browser",
        )
        event = AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_ADD_TO_CART,
            path="/koszyk/dodaj/",
            product=product,
            metadata={"quantity": 2, "source": "product-card"},
        )
        self.client.login(username="staff", password="pass")

        list_response = self.client.get(
            reverse("dashboard:model_list", args=["analytics-events"]),
            {"event_type": AnalyticsEvent.EVENT_ADD_TO_CART, "device": "desktop"},
        )
        detail_response = self.client.get(
            reverse("dashboard:model_edit", args=["analytics-events", event.id])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "dashboard/analytics_event_list.html")
        self.assertContains(list_response, "Dodanie do koszyka")
        self.assertContains(list_response, "Analytics Choker")
        self.assertContains(list_response, "quantity: 2")
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "dashboard/analytics_event_detail.html")
        self.assertContains(detail_response, "Metadane zdarzenia")
        self.assertContains(detail_response, "product-card")
        self.assertContains(detail_response, "Zobacz całą sesję")

    def test_product_list_shows_image_prices_and_stock(self):
        product = self.create_product("List Product", "list-product")
        product.regular_price = "39.00"
        product.sale_price = "19.00"
        product.save(update_fields=["regular_price", "sale_price"])
        ProductVariant.objects.create(product=product, stock_quantity=7, is_active=True)
        ProductImage.objects.create(
            product=product,
            image="products/list-product/main.jpg",
            alt_text="List Product photo",
            is_main=True,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["products"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cena regularna")
        self.assertContains(response, "Cena promocyjna")
        self.assertContains(response, "Ilość")
        self.assertContains(response, "39,00")
        self.assertContains(response, "19,00")
        self.assertContains(response, "7 szt.")
        self.assertContains(response, "List Product photo")

    def test_product_list_can_be_sorted_by_name_and_stock(self):
        first_product = self.create_product("Alpha Choker", "alpha-choker")
        second_product = self.create_product("Beta Choker", "beta-choker")
        ProductVariant.objects.create(product=first_product, stock_quantity=2, is_active=True)
        ProductVariant.objects.create(product=second_product, stock_quantity=9, is_active=True)
        self.client.login(username="staff", password="pass")

        name_response = self.client.get(
            reverse("dashboard:model_list", args=["products"]),
            {"sort": "product", "direction": "desc"},
        )
        stock_response = self.client.get(
            reverse("dashboard:model_list", args=["products"]),
            {"sort": "stock", "direction": "desc"},
        )

        self.assertEqual(name_response.context["rows"][0]["name"], "Beta Choker")
        self.assertEqual(stock_response.context["rows"][0]["stock_quantity"], 9)
        self.assertContains(name_response, "dashboard-sort-link")

    def test_staff_user_can_open_product_workspace(self):
        product = self.create_product("Workspace Product", "workspace-product")
        ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:product_workspace", args=[product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace Product")
        self.assertContains(response, "Warianty")

    def test_product_workspace_uses_simplified_polish_product_fields(self):
        product = self.create_product("Workspace Product", "workspace-product")
        ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        ProductImage.objects.create(product=product, image="products/workspace/main.webp", sort_order=0)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:product_workspace", args=[product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opis")
        self.assertContains(response, "Porady dotyczące stylizacji")
        self.assertContains(response, "Dodaj wariant")
        self.assertContains(response, "Wybierz zdjęcia")
        self.assertContains(response, "Wszystkie")
        self.assertNotContains(response, 'name="product-slug"')
        self.assertNotContains(response, 'name="product-short_description"')
        self.assertNotContains(response, 'name="product-details"')
        self.assertNotContains(response, 'name="product-sort_order"')

    def test_product_workspace_shows_collapsed_product_stats(self):
        product = self.create_product("Stats Product", "stats-product")
        variant = ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        session = AnalyticsSession.objects.create(
            session_key="stats-session",
            visitor_id="visitor-1",
            user_agent="Local Test Browser",
        )
        AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW,
            path=product.get_absolute_url(),
            product=product,
            variant=variant,
        )
        AnalyticsEvent.objects.create(
            session=session,
            event_type=AnalyticsEvent.EVENT_ADD_TO_CART,
            path="/koszyk/dodaj/",
            product=product,
            variant=variant,
        )
        order = Order.objects.create(
            email="test@example.com",
            first_name="Ada",
            last_name="Test",
            shipping_address_line_1="Testowa 1",
            shipping_postal_code="00-000",
            shipping_city="Warszawa",
            status=Order.STATUS_PLACED,
            grand_total="29.00",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name=product.name,
            quantity=2,
            unit_price="29.00",
            line_total="58.00",
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:product_workspace", args=[product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Statystyki")
        self.assertContains(response, "Osoby, które weszły")
        self.assertContains(response, "Dodania do koszyka")
        self.assertContains(response, "Kupione sztuki")
        self.assertNotContains(response, "<details class=\"dashboard-product-stats\" open")
        self.assertEqual(response.context["product_stats"]["unique_viewers"], 1)
        self.assertEqual(response.context["product_stats"]["add_to_cart"], 1)
        self.assertEqual(response.context["product_stats"]["purchased_quantity"], 2)

    def test_product_workspace_regenerates_slug_from_name(self):
        product = self.create_product("Old Name", "old-name")
        variant = ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:product_workspace", args=[product.id]),
            {
                "product-name": "New Name",
                "product-category": str(product.category_id),
                "product-description": "Opis produktu.",
                "product-styling_tips": "Noś z czarnymi dodatkami.",
                "product-regular_price": "29.00",
                "product-sale_price": "",
                "product-seo_title": "",
                "product-seo_description": "",
                "product-status": Product.STATUS_ACTIVE,
                "product-low_stock_threshold": "3",
                "variants-TOTAL_FORMS": "1",
                "variants-INITIAL_FORMS": "1",
                "variants-MIN_NUM_FORMS": "0",
                "variants-MAX_NUM_FORMS": "1000",
                "variants-0-id": str(variant.id),
                "variants-0-color": "",
                "variants-0-size": "",
                "variants-0-sku": "",
                "variants-0-price_override": "",
                "variants-0-stock_quantity": "3",
                "variants-0-is_active": "on",
                "variants-0-sort_order": "0",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
            },
        )

        product.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(product.name, "New Name")
        self.assertEqual(product.slug, "new-name")

    def test_product_workspace_deletes_variant_from_workspace(self):
        product = self.create_product("Variant Delete Product", "variant-delete-product")
        color = Color.objects.create(name="Black", slug="black")
        first_variant = ProductVariant.objects.create(product=product, color=color, stock_quantity=3, is_active=True)
        second_variant = ProductVariant.objects.create(product=product, stock_quantity=5, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:product_workspace", args=[product.id]),
            {
                "deleted_variant_ids": str(first_variant.id),
                "deleted_image_ids": "",
                "product-name": product.name,
                "product-category": str(product.category_id),
                "product-description": "Opis produktu.",
                "product-styling_tips": "Noś z czarnymi dodatkami.",
                "product-regular_price": "29.00",
                "product-sale_price": "",
                "product-seo_title": "",
                "product-seo_description": "",
                "product-status": Product.STATUS_ACTIVE,
                "product-low_stock_threshold": "3",
                "variants-TOTAL_FORMS": "2",
                "variants-INITIAL_FORMS": "2",
                "variants-MIN_NUM_FORMS": "0",
                "variants-MAX_NUM_FORMS": "1000",
                "variants-0-id": str(first_variant.id),
                "variants-0-color": str(color.id),
                "variants-0-size": "",
                "variants-0-sku": "",
                "variants-0-price_override": "",
                "variants-0-stock_quantity": "3",
                "variants-0-is_active": "on",
                "variants-0-sort_order": "0",
                "variants-0-DELETE": "on",
                "variants-1-id": str(second_variant.id),
                "variants-1-color": "",
                "variants-1-size": "",
                "variants-1-sku": "",
                "variants-1-price_override": "",
                "variants-1-stock_quantity": "5",
                "variants-1-is_active": "on",
                "variants-1-sort_order": "1",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductVariant.objects.filter(id=first_variant.id).exists())
        self.assertTrue(ProductVariant.objects.filter(id=second_variant.id).exists())

    def test_product_workspace_deletes_image_from_workspace(self):
        product = self.create_product("Image Delete Product", "image-delete-product")
        variant = ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        image = ProductImage.objects.create(product=product, image="products/delete/main.webp", sort_order=0)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:product_workspace", args=[product.id]),
            {
                "deleted_variant_ids": "",
                "deleted_image_ids": str(image.id),
                "product-name": product.name,
                "product-category": str(product.category_id),
                "product-description": "Opis produktu.",
                "product-styling_tips": "Noś z czarnymi dodatkami.",
                "product-regular_price": "29.00",
                "product-sale_price": "",
                "product-seo_title": "",
                "product-seo_description": "",
                "product-status": Product.STATUS_ACTIVE,
                "product-low_stock_threshold": "3",
                "variants-TOTAL_FORMS": "1",
                "variants-INITIAL_FORMS": "1",
                "variants-MIN_NUM_FORMS": "0",
                "variants-MAX_NUM_FORMS": "1000",
                "variants-0-id": str(variant.id),
                "variants-0-color": "",
                "variants-0-size": "",
                "variants-0-sku": "",
                "variants-0-price_override": "",
                "variants-0-stock_quantity": "3",
                "variants-0-is_active": "on",
                "variants-0-sort_order": "0",
                "images-TOTAL_FORMS": "1",
                "images-INITIAL_FORMS": "1",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "images-0-id": str(image.id),
                "images-0-variant": "",
                "images-0-sort_order": "0",
                "images-0-DELETE": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductImage.objects.filter(id=image.id).exists())

    def test_sync_product_main_image_uses_first_gallery_image(self):
        product = self.create_product("Gallery Product", "gallery-product")
        second_image = ProductImage.objects.create(
            product=product,
            image="products/gallery/second.jpg",
            sort_order=2,
            is_main=True,
        )
        first_image = ProductImage.objects.create(
            product=product,
            image="products/gallery/first.jpg",
            sort_order=0,
            is_main=False,
        )

        sync_product_main_image(product)

        first_image.refresh_from_db()
        second_image.refresh_from_db()
        self.assertTrue(first_image.is_main)
        self.assertFalse(second_image.is_main)

    def test_product_image_upload_filter_accepts_shop_file_types(self):
        webp_file = SimpleUploadedFile("photo.webp", b"webp", content_type="image/webp")
        jpg_file = SimpleUploadedFile("photo.jpg", b"jpg", content_type="image/jpeg")
        bad_file = SimpleUploadedFile("photo.gif", b"gif", content_type="image/gif")

        valid_files, rejected_names = filter_product_image_files([webp_file, jpg_file, bad_file])

        self.assertEqual(valid_files, [webp_file, jpg_file])
        self.assertEqual(rejected_names, ["photo.gif"])

    def test_outfit_list_uses_custom_layout(self):
        outfit = Outfit.objects.create(
            name="Dark Coquette Set",
            slug="dark-coquette-set",
            short_description="Gotowa stylizacja z chokerem.",
            bundle_price="49.00",
            status=Outfit.STATUS_ACTIVE,
            is_featured=True,
        )
        product = self.create_product("Outfit Choker", "outfit-choker")
        OutfitItem.objects.create(outfit=outfit, product=product, quantity=2)
        OutfitImage.objects.create(outfit=outfit, image="outfits/set/main.webp", is_main=True)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["outfits"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/outfit_list.html")
        self.assertContains(response, "Dark Coquette Set")
        self.assertContains(response, "Cena promocyjna")
        self.assertContains(response, "49,00")
        self.assertNotContains(response, "Produkty w stylizacjach")
        self.assertNotContains(response, "Zdjęcia stylizacji")

    def test_staff_user_can_create_outfit_workspace(self):
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:outfit_create_workspace"),
            {
                "outfit-name": "New Outfit",
                "outfit-short_description": "Krótki opis.",
                "outfit-mood_description": "Opis klimatu.",
                "outfit-styling_tips": "Noś z chokerem.",
                "outfit-bundle_price": "59.00",
                "outfit-status": Outfit.STATUS_ACTIVE,
                "outfit-seo_title": "",
                "outfit-seo_description": "",
            },
        )

        outfit = Outfit.objects.get(name="New Outfit")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(outfit.slug, "new-outfit")
        self.assertEqual(outfit.bundle_price, Decimal("59.00"))

    def test_outfit_workspace_saves_items_and_promo_price(self):
        outfit = Outfit.objects.create(name="Workspace Outfit", slug="workspace-outfit", status=Outfit.STATUS_DRAFT)
        product = self.create_product("Workspace Choker", "workspace-choker")
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:outfit_workspace", args=[outfit.id]),
            {
                "deleted_item_ids": "",
                "deleted_image_ids": "",
                "outfit-name": "Workspace Outfit",
                "outfit-short_description": "Krótki opis.",
                "outfit-mood_description": "Opis klimatu.",
                "outfit-styling_tips": "Noś z chokerem.",
                "outfit-bundle_price": "39.00",
                "outfit-status": Outfit.STATUS_ACTIVE,
                "outfit-seo_title": "",
                "outfit-seo_description": "",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-product": str(product.id),
                "items-0-variant": "",
                "items-0-quantity": "2",
                "items-0-sort_order": "0",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "hotspots-TOTAL_FORMS": "0",
                "hotspots-INITIAL_FORMS": "0",
                "hotspots-MIN_NUM_FORMS": "0",
                "hotspots-MAX_NUM_FORMS": "1000",
            },
        )

        outfit.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(outfit.status, Outfit.STATUS_ACTIVE)
        self.assertEqual(outfit.bundle_price, Decimal("39.00"))
        self.assertTrue(OutfitItem.objects.filter(outfit=outfit, product=product, quantity=2).exists())

    def test_active_outfit_cannot_be_saved_without_products(self):
        outfit = Outfit.objects.create(name="Empty Outfit", slug="empty-outfit", status=Outfit.STATUS_DRAFT)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:outfit_workspace", args=[outfit.id]),
            {
                "deleted_item_ids": "",
                "deleted_image_ids": "",
                "outfit-name": "Empty Outfit",
                "outfit-short_description": "Krótki opis.",
                "outfit-mood_description": "Opis klimatu.",
                "outfit-styling_tips": "Noś z chokerem.",
                "outfit-bundle_price": "39.00",
                "outfit-status": Outfit.STATUS_ACTIVE,
                "outfit-seo_title": "",
                "outfit-seo_description": "",
                "items-TOTAL_FORMS": "0",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "hotspots-TOTAL_FORMS": "0",
                "hotspots-INITIAL_FORMS": "0",
                "hotspots-MIN_NUM_FORMS": "0",
                "hotspots-MAX_NUM_FORMS": "1000",
            },
        )

        outfit.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aktywna stylizacja musi mieć przynajmniej jeden produkt")
        self.assertEqual(outfit.status, Outfit.STATUS_DRAFT)

    def test_outfit_workspace_saves_hotspot(self):
        outfit = Outfit.objects.create(name="Hotspot Outfit", slug="hotspot-outfit", status=Outfit.STATUS_ACTIVE)
        product = self.create_product("Hotspot Choker", "hotspot-choker")
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:outfit_workspace", args=[outfit.id]),
            {
                "deleted_item_ids": "",
                "deleted_image_ids": "",
                "deleted_hotspot_ids": "",
                "outfit-name": outfit.name,
                "outfit-short_description": "",
                "outfit-mood_description": "",
                "outfit-styling_tips": "",
                "outfit-bundle_price": "",
                "outfit-status": Outfit.STATUS_ACTIVE,
                "outfit-seo_title": "",
                "outfit-seo_description": "",
                "items-TOTAL_FORMS": "0",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "hotspots-TOTAL_FORMS": "1",
                "hotspots-INITIAL_FORMS": "0",
                "hotspots-MIN_NUM_FORMS": "0",
                "hotspots-MAX_NUM_FORMS": "1000",
                "hotspots-0-product": str(product.id),
                "hotspots-0-pos_x": "33.50",
                "hotspots-0-pos_y": "60.25",
                "hotspots-0-sort_order": "0",
            },
        )

        self.assertEqual(response.status_code, 302)
        hotspot = OutfitHotspot.objects.get(outfit=outfit, product=product)
        self.assertEqual(hotspot.pos_x, Decimal("33.50"))
        self.assertEqual(hotspot.pos_y, Decimal("60.25"))

    def test_outfit_workspace_deletes_image(self):
        outfit = Outfit.objects.create(name="Image Outfit", slug="image-outfit", status=Outfit.STATUS_ACTIVE)
        image = OutfitImage.objects.create(outfit=outfit, image="outfits/delete/main.webp", sort_order=0)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:outfit_workspace", args=[outfit.id]),
            {
                "deleted_item_ids": "",
                "deleted_image_ids": str(image.id),
                "outfit-name": outfit.name,
                "outfit-short_description": "",
                "outfit-mood_description": "",
                "outfit-styling_tips": "",
                "outfit-bundle_price": "",
                "outfit-status": Outfit.STATUS_ACTIVE,
                "outfit-seo_title": "",
                "outfit-seo_description": "",
                "items-TOTAL_FORMS": "0",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "images-TOTAL_FORMS": "1",
                "images-INITIAL_FORMS": "1",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "images-0-id": str(image.id),
                "images-0-sort_order": "0",
                "images-0-DELETE": "on",
                "hotspots-TOTAL_FORMS": "0",
                "hotspots-INITIAL_FORMS": "0",
                "hotspots-MIN_NUM_FORMS": "0",
                "hotspots-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(OutfitImage.objects.filter(id=image.id).exists())

    def test_article_list_uses_custom_layout(self):
        category = BlogCategory.objects.create(name="Stylizacje", slug="stylizacje")
        article = Article.objects.create(
            title="Jak nosić chokery",
            slug="jak-nosic-chokery",
            category=category,
            intro="Krótki poradnik o dodatkach.",
            body="Body",
            cover_image="articles/chokery.webp",
            status=Article.STATUS_PUBLISHED,
            is_featured=True,
        )
        analytics_session = AnalyticsSession.objects.create(session_key="article-view-test")
        AnalyticsEvent.objects.create(
            session=analytics_session,
            event_type=AnalyticsEvent.EVENT_ARTICLE_VIEW,
            path=article.get_absolute_url(),
            article=article,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["articles"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/article_list.html")
        self.assertContains(response, "Jak nosić chokery")
        self.assertContains(response, "Opublikowane")
        self.assertContains(response, "Z okładką")
        self.assertContains(response, "Krótki poradnik o dodatkach.")
        self.assertContains(response, "Wyświetlenia")
        self.assertEqual(response.context["rows"][0]["view_count"], 1)

    def test_staff_user_can_create_article_workspace(self):
        category = BlogCategory.objects.create(name="SEO", slug="seo")
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:article_create_workspace"),
            {
                "article-title": "Dark coquette w praktyce",
                "article-intro": "Krótki opis poradnika.",
                "article-body": "## Wstęp\n\nNoś chokery z koronką.",
                "article-category": str(category.id),
                "article-status": Article.STATUS_DRAFT,
                "article-published_at": "",
                "article-seo_title": "",
                "article-seo_description": "",
            },
        )

        article = Article.objects.get(title="Dark coquette w praktyce")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(article.slug, "dark-coquette-w-praktyce")
        self.assertEqual(article.category, category)

    def test_article_workspace_shows_rich_editor_and_preview(self):
        article = Article.objects.create(
            title="Rich Article",
            slug="rich-article",
            intro="Intro",
            body="## Nagłówek\n\nTreść",
            status=Article.STATUS_DRAFT,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:article_workspace", args=[article.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/article_workspace.html")
        self.assertContains(response, "Treść poradnika")
        self.assertContains(response, "Podgląd końcowy")
        self.assertContains(response, "data-rich-action=\"heading2\"")

    def test_blog_category_list_uses_taxonomy_layout_with_article_copy(self):
        category = BlogCategory.objects.create(
            name="Stylizacje",
            slug="stylizacje",
            description="Poradniki o gotowych zestawach.",
            sort_order=2,
            is_active=True,
        )
        Article.objects.create(
            title="Jak nosić chokery",
            slug="jak-nosic-chokery",
            category=category,
            body="Body",
            status=Article.STATUS_PUBLISHED,
            is_featured=True,
        )
        Article.objects.create(
            title="Szkic stylizacji",
            slug="szkic-stylizacji",
            category=category,
            body="Body",
            status=Article.STATUS_DRAFT,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["blog-categories"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_list.html")
        self.assertContains(response, "Kategorie poradników")
        self.assertContains(response, "Poradniki")
        self.assertContains(response, "Opublikowane")
        self.assertContains(response, "Wyróżnione")
        self.assertContains(response, "Poradniki o gotowych zestawach.")
        self.assertEqual(response.context["rows"][0]["article_count"], 2)
        self.assertEqual(response.context["rows"][0]["published_article_count"], 1)

    def test_blog_category_form_uses_article_copy_and_regenerates_slug(self):
        category = BlogCategory.objects.create(name="Old SEO", slug="old-seo", sort_order=4)
        Article.objects.create(
            title="Powiązany poradnik",
            slug="powiazany-poradnik",
            category=category,
            body="Body",
            status=Article.STATUS_PUBLISHED,
        )
        self.client.login(username="staff", password="pass")

        get_response = self.client.get(reverse("dashboard:model_edit", args=["blog-categories", category.id]))
        post_response = self.client.post(
            reverse("dashboard:model_edit", args=["blog-categories", category.id]),
            {
                "name": "Nowe poradniki SEO",
                "description": "Kategoria dla poradników.",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        category.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, "dashboard/taxonomy_form.html")
        self.assertContains(get_response, "Poradniki w kategorii")
        self.assertContains(get_response, "To dane używane przy poradnikach")
        self.assertContains(get_response, "Powiązany poradnik")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(category.slug, "nowe-poradniki-seo")

    def test_newsletter_list_uses_marketing_workspace(self):
        active_subscriber = NewsletterSubscriber.objects.create(
            email="active@example.com",
            source=NewsletterSubscriber.SOURCE_HOME,
            consent_text="Zgoda na newsletter Spooky Strawberry.",
        )
        inactive_subscriber = NewsletterSubscriber.objects.create(
            email="inactive@example.com",
            source=NewsletterSubscriber.SOURCE_FOOTER,
            is_active=False,
            consent_text="Zgoda historyczna.",
            unsubscribed_at=timezone.now(),
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["newsletter-subscribers"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/newsletter_list.html")
        self.assertContains(response, "Marketing")
        self.assertContains(response, "dashboard-newsletter-toolbar")
        self.assertContains(response, "Lista do wysyłki")
        self.assertContains(response, "Źródła zapisów")
        self.assertContains(response, "active@example.com")
        self.assertContains(response, "inactive@example.com")
        self.assertContains(response, "Strona główna")
        self.assertEqual(response.context["newsletter_summary"]["active_count"], 1)
        self.assertIn(active_subscriber.email, response.context["newsletter_active_emails"])
        self.assertNotIn(inactive_subscriber.email, response.context["newsletter_active_emails"])

    def test_newsletter_list_filters_by_status_source_and_period(self):
        NewsletterSubscriber.objects.create(
            email="home@example.com",
            source=NewsletterSubscriber.SOURCE_HOME,
            consent_text="Zgoda.",
        )
        NewsletterSubscriber.objects.create(
            email="footer@example.com",
            source=NewsletterSubscriber.SOURCE_FOOTER,
            is_active=False,
            consent_text="Zgoda.",
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(
            reverse("dashboard:model_list", args=["newsletter-subscribers"]),
            {
                "status": "active",
                "source": NewsletterSubscriber.SOURCE_HOME,
                "period": "30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "home@example.com")
        self.assertNotContains(response, "footer@example.com")
        self.assertEqual([row["email"] for row in response.context["rows"]], ["home@example.com"])

    def test_newsletter_subscriber_detail_uses_custom_workspace(self):
        subscriber = NewsletterSubscriber.objects.create(
            email="detail@example.com",
            source=NewsletterSubscriber.SOURCE_POPUP,
            consent_text="Zgoda z popupu.",
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_edit", args=["newsletter-subscribers", subscriber.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/newsletter_form.html")
        self.assertContains(response, "Marketing · Newsletter")
        self.assertContains(response, "Do wysyłki")
        self.assertContains(response, "Zgoda z popupu.")
        self.assertEqual(response.context["newsletter_detail"]["source_label"], "Popup")

    def test_order_list_uses_custom_workspace(self):
        product = self.create_product("Order Choker", "order-choker")
        order = self.create_order("SS-001", "order@example.com", status=Order.STATUS_PLACED, grand_total="59.00")
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=2,
            unit_price="29.50",
            line_total="59.00",
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["orders"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/order_list.html")
        self.assertContains(response, "SS-001")
        self.assertContains(response, "Order Choker")
        self.assertContains(response, "Złożone")
        self.assertContains(response, "Przychód")
        self.assertEqual(response.context["order_summary"]["open_count"], 1)
        self.assertEqual(response.context["rows"][0]["quantity_count"], 2)

    def test_order_summary_and_statuses_exclude_test_orders(self):
        self.create_order(
            "SS-TEST-OPEN",
            "test-open@example.com",
            status=Order.STATUS_PLACED,
            grand_total="59.00",
            is_test=True,
        )
        self.create_order(
            "SS-TEST-CANCELLED",
            "test-cancelled@example.com",
            status=Order.STATUS_CANCELLED,
            grand_total="29.00",
            is_test=True,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["orders"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SS-TEST-OPEN")
        self.assertEqual(response.context["order_summary"], {
            "total_count": 0,
            "open_count": 0,
            "new_30_count": 0,
            "cancelled_count": 0,
            "revenue_total": 0,
        })
        status_counts = {row["value"]: row["count"] for row in response.context["order_status_rows"]}
        self.assertEqual(status_counts[Order.STATUS_PLACED], 0)
        self.assertEqual(status_counts[Order.STATUS_CANCELLED], 0)

    def test_order_workspace_shows_items_and_updates_status(self):
        product = self.create_product("Workspace Order Choker", "workspace-order-choker")
        shipping_method = ShippingMethod.objects.create(name="InPost", code="inpost", price="12.99")
        order = self.create_order(
            "SS-002",
            "workspace-order@example.com",
            status=Order.STATUS_PLACED,
            grand_total="41.99",
            shipping_method=shipping_method,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            variant_name="Midnight Black",
            sku="CHOKER-BLK",
            quantity=1,
            unit_price="29.00",
            line_total="29.00",
        )
        self.client.login(username="staff", password="pass")

        get_response = self.client.get(reverse("dashboard:order_workspace", args=[order.id]))
        post_response = self.client.post(
            reverse("dashboard:order_workspace", args=[order.id]),
            {
                "order-order_number": order.order_number,
                "order-status": Order.STATUS_CONFIRMED,
                "order-placed_at": "",
                "order-email": order.email,
                "order-phone": order.phone,
                "order-first_name": order.first_name,
                "order-last_name": order.last_name,
                "order-shipping_address_line_1": order.shipping_address_line_1,
                "order-shipping_address_line_2": order.shipping_address_line_2,
                "order-shipping_postal_code": order.shipping_postal_code,
                "order-shipping_city": order.shipping_city,
                "order-shipping_country": order.shipping_country,
                "order-shipping_method": str(shipping_method.id),
                "order-discount_code": "",
                "order-subtotal": "29.00",
                "order-discount_total": "0.00",
                "order-shipping_total": "12.99",
                "order-grand_total": "41.99",
                "order-customer_note": "Zapakować na prezent.",
                "order-source_session_key": "test-session",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-id": str(order.items.first().id),
                "items-0-product": str(product.id),
                "items-0-variant": "",
                "items-0-product_name": product.name,
                "items-0-variant_name": "Midnight Black",
                "items-0-sku": "CHOKER-BLK",
                "items-0-quantity": "1",
                "items-0-unit_price": "29.00",
                "items-0-line_total": "29.00",
            },
        )

        order.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, "dashboard/order_workspace.html")
        self.assertContains(get_response, "Pozycje zamówienia")
        self.assertContains(get_response, "Workspace Order Choker")
        self.assertContains(get_response, "Midnight Black")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)
        self.assertEqual(order.customer_note, "Zapakować na prezent.")

    def test_order_workspace_manages_items_with_snapshot_and_image(self):
        product = self.create_product("Snapshot Choker", "snapshot-choker")
        ProductImage.objects.create(product=product, image="products/snapshot/main.webp", is_main=True)
        order = self.create_order("SS-003", "snapshot@example.com", status=Order.STATUS_PLACED, grand_total="0.00")
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:order_workspace", args=[order.id]),
            {
                "order-order_number": order.order_number,
                "order-status": Order.STATUS_PLACED,
                "order-placed_at": "",
                "order-email": order.email,
                "order-phone": order.phone,
                "order-first_name": order.first_name,
                "order-last_name": order.last_name,
                "order-shipping_address_line_1": order.shipping_address_line_1,
                "order-shipping_address_line_2": order.shipping_address_line_2,
                "order-shipping_postal_code": order.shipping_postal_code,
                "order-shipping_city": order.shipping_city,
                "order-shipping_country": order.shipping_country,
                "order-shipping_method": "",
                "order-discount_code": "",
                "order-subtotal": "0.00",
                "order-discount_total": "0.00",
                "order-shipping_total": "12.00",
                "order-grand_total": "12.00",
                "order-customer_note": "",
                "order-source_session_key": "",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-product": str(product.id),
                "items-0-variant": "",
                "items-0-product_name": "",
                "items-0-variant_name": "",
                "items-0-sku": "",
                "items-0-quantity": "2",
                "items-0-unit_price": "29.00",
                "items-0-line_total": "",
            },
        )

        order.refresh_from_db()
        item = order.items.get()
        get_response = self.client.get(reverse("dashboard:order_workspace", args=[order.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.product_name, "Snapshot Choker")
        self.assertEqual(item.line_total, Decimal("58.00"))
        self.assertEqual(order.subtotal, Decimal("58.00"))
        self.assertEqual(order.grand_total, Decimal("70.00"))
        self.assertContains(get_response, "products/snapshot/main.webp")
        self.assertContains(get_response, "Snapshot Choker")

    def test_order_item_list_and_detail_are_readable(self):
        product = self.create_product("Checked Choker", "checked-choker")
        ProductImage.objects.create(product=product, image="products/checked/main.webp", is_main=True)
        order = self.create_order("SS-004", "checked@example.com", status=Order.STATUS_CONFIRMED, grand_total="29.00")
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name="Historyczna nazwa chokera",
            variant_name="Black / One Size",
            sku="OLD-SKU",
            quantity=1,
            unit_price="29.00",
            line_total="29.00",
        )
        product.name = "Nowa nazwa w katalogu"
        product.save(update_fields=["name"])
        self.client.login(username="staff", password="pass")

        list_response = self.client.get(reverse("dashboard:model_list", args=["order-items"]))
        detail_response = self.client.get(reverse("dashboard:order_item_detail", args=[item.id]))

        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "dashboard/order_item_list.html")
        self.assertContains(list_response, "Historyczna nazwa chokera")
        self.assertContains(list_response, "products/checked/main.webp")
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "dashboard/order_item_detail.html")
        self.assertContains(detail_response, "Snapshot z zamówienia")
        self.assertContains(detail_response, "Historyczna nazwa chokera")
        self.assertNotContains(detail_response, "Nowa nazwa w katalogu")

    def test_shipping_method_list_and_detail_use_custom_workspace(self):
        ShippingMethod.objects.all().delete()
        shipping_method = ShippingMethod.objects.create(
            name="Paczkomat InPost",
            code="paczkomat-inpost",
            description="Dostawa do paczkomatu.",
            price="12.99",
            free_from_amount="150.00",
            is_active=True,
        )
        self.create_order(
            "SS-SHIP",
            "shipping@example.com",
            status=Order.STATUS_PLACED,
            grand_total="41.99",
            shipping_method=shipping_method,
        )
        self.client.login(username="staff", password="pass")

        list_response = self.client.get(reverse("dashboard:model_list", args=["shipping-methods"]))
        detail_response = self.client.get(reverse("dashboard:model_edit", args=["shipping-methods", shipping_method.id]))
        post_response = self.client.post(
            reverse("dashboard:model_edit", args=["shipping-methods", shipping_method.id]),
            {
                "name": "Paczkomat InPost 24/7",
                "code": "",
                "description": "Dostawa do paczkomatu w 1-3 dni robocze.",
                "price": "12.99",
                "free_from_amount": "150.00",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        shipping_method.refresh_from_db()
        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "dashboard/shipping_method_list.html")
        self.assertContains(list_response, "Metody dostawy")
        self.assertContains(list_response, "Paczkomat InPost")
        self.assertContains(list_response, "12,99")
        self.assertEqual(list_response.context["shipping_summary"]["active_count"], 1)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "dashboard/shipping_method_form.html")
        self.assertContains(detail_response, "Cena dostawy")
        self.assertContains(detail_response, "Dane techniczne")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(shipping_method.name, "Paczkomat InPost 24/7")
        self.assertEqual(shipping_method.code, "paczkomat-inpost-247")

    def test_discount_code_list_and_detail_use_custom_workspace(self):
        discount_code = DiscountCode.objects.create(
            code="SPOOKY10",
            discount_type=DiscountCode.TYPE_PERCENT,
            value="10.00",
            minimum_order_amount="50.00",
            max_uses=5,
            used_count=1,
            is_active=True,
        )
        order = self.create_order("SS-DISCOUNT", "discount@example.com", status=Order.STATUS_PLACED, grand_total="49.00")
        order.discount_code = discount_code
        order.save(update_fields=["discount_code"])
        self.client.login(username="staff", password="pass")

        list_response = self.client.get(reverse("dashboard:model_list", args=["discount-codes"]))
        detail_response = self.client.get(reverse("dashboard:model_edit", args=["discount-codes", discount_code.id]))
        post_response = self.client.post(
            reverse("dashboard:model_edit", args=["discount-codes", discount_code.id]),
            {
                "code": "spooky15",
                "discount_type": DiscountCode.TYPE_FIXED,
                "value": "15.00",
                "minimum_order_amount": "60.00",
                "max_uses": "10",
                "used_count": "1",
                "starts_at": "",
                "ends_at": "",
                "is_active": "on",
            },
        )

        discount_code.refresh_from_db()
        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "dashboard/discount_code_list.html")
        self.assertContains(list_response, "Kody rabatowe")
        self.assertContains(list_response, "SPOOKY10")
        self.assertContains(list_response, "10%")
        self.assertEqual(list_response.context["discount_summary"]["active_count"], 1)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "dashboard/discount_code_form.html")
        self.assertContains(detail_response, "Wartość rabatu")
        self.assertContains(detail_response, "Kontrola")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(discount_code.code, "SPOOKY15")
        self.assertEqual(discount_code.discount_type, DiscountCode.TYPE_FIXED)

    def test_quality_refresh_creates_product_issue(self):
        product = self.create_product("Incomplete Product", "incomplete-product")
        self.client.login(username="staff", password="pass")

        response = self.client.post(reverse("dashboard:refresh_quality"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(DataQualityIssue.objects.filter(product=product, status=DataQualityIssue.STATUS_OPEN).exists())

    def test_category_list_uses_taxonomy_layout(self):
        category = Category.objects.create(name="Podwiązki", slug="podwiazki", description="Akcesoria do stylizacji.")
        Product.objects.create(
            name="Harness Heart",
            slug="harness-heart",
            category=category,
            regular_price="39.00",
            status=Product.STATUS_ACTIVE,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["categories"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_list.html")
        self.assertContains(response, "Podwiązki")
        self.assertContains(response, "Produkty")
        self.assertContains(response, "Podkategorie")
        self.assertEqual(response.context["rows"][0]["product_count"], 1)

    def test_aesthetic_list_uses_taxonomy_layout(self):
        aesthetic = Aesthetic.objects.create(name="Dark coquette", slug="dark-coquette", sort_order=2)
        product = self.create_product("Coquette Choker", "coquette-choker")
        product.aesthetics.add(aesthetic)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["aesthetics"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_list.html")
        self.assertContains(response, "Dark coquette")
        self.assertContains(response, "Estetyka #2")
        self.assertNotContains(response, "Klimat / kolekcja")
        self.assertEqual(response.context["rows"][0]["active_product_count"], 1)

    def test_color_list_uses_taxonomy_layout(self):
        color = Color.objects.create(name="Midnight Black", slug="midnight-black", hex_code="#000000")
        product = self.create_product("Black Choker", "black-choker")
        ProductVariant.objects.create(product=product, color=color, stock_quantity=4, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["colors"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_list.html")
        self.assertContains(response, "Midnight Black")
        self.assertContains(response, "#000000")
        self.assertContains(response, "Warianty")
        self.assertEqual(response.context["rows"][0]["active_product_count"], 1)

    def test_size_list_uses_taxonomy_layout(self):
        size = Size.objects.create(name="One Size", slug="one-size", sort_order=1)
        product = self.create_product("Sized Choker", "sized-choker")
        ProductVariant.objects.create(product=product, size=size, stock_quantity=4, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["sizes"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/taxonomy_list.html")
        self.assertContains(response, "One Size")
        self.assertContains(response, "Rozmiar #1")
        self.assertContains(response, "Kolejność")
        self.assertEqual(response.context["rows"][0]["active_product_count"], 1)

    def test_taxonomy_form_regenerates_slug_from_name(self):
        aesthetic = Aesthetic.objects.create(name="Old Style", slug="old-style", sort_order=3)
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:model_edit", args=["aesthetics", aesthetic.id]),
            {
                "name": "Soft Goth",
                "description": "Delikatny gotycki klimat.",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        aesthetic.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(aesthetic.slug, "soft-goth")

    def test_color_form_regenerates_slug_from_name(self):
        color = Color.objects.create(name="Old Black", slug="old-black", hex_code="#111111")
        self.client.login(username="staff", password="pass")

        response = self.client.post(
            reverse("dashboard:model_edit", args=["colors", color.id]),
            {
                "name": "Midnight Black",
                "hex_code": "#000000",
                "is_active": "on",
            },
        )

        color.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(color.slug, "midnight-black")
        self.assertEqual(color.hex_code, "#000000")

    def create_product(self, name, slug):
        category, _ = Category.objects.get_or_create(name="Chokery", slug="chokery")
        return Product.objects.create(
            name=name,
            slug=slug,
            category=category,
            regular_price="29.00",
            status=Product.STATUS_ACTIVE,
        )

    def create_order(
        self,
        order_number,
        email,
        status=Order.STATUS_PLACED,
        grand_total="29.00",
        shipping_method=None,
        is_test=False,
    ):
        return Order.objects.create(
            order_number=order_number,
            email=email,
            phone="123456789",
            first_name="Ada",
            last_name="Test",
            shipping_address_line_1="Testowa 1",
            shipping_postal_code="00-000",
            shipping_city="Warszawa",
            shipping_country="Polska",
            is_test=is_test,
            status=status,
            shipping_method=shipping_method,
            subtotal=grand_total,
            discount_total="0.00",
            shipping_total="0.00",
            grand_total=grand_total,
        )


class WarehouseViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(username="whstaff", password="pass", is_staff=True)
        self.regular_user = user_model.objects.create_user(username="whregular", password="pass", is_staff=False)
        self.category = Category.objects.create(name="Magazynowa")
        self.product = Product.objects.create(name="Choker", category=self.category, regular_price=Decimal("59.00"))
        self.variant = ProductVariant.objects.create(product=self.product, stock_quantity=0, is_active=True)

    def test_warehouse_requires_staff(self):
        self.client.login(username="whregular", password="pass")
        response = self.client.get(reverse("dashboard:warehouse"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response["Location"])

    def test_warehouse_renders_products(self):
        self.client.login(username="whstaff", password="pass")
        response = self.client.get(reverse("dashboard:warehouse"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/warehouse.html")
        self.assertContains(response, "Choker")

    def test_add_entry_increases_stock(self):
        from inventory.models import StockEntry

        self.client.login(username="whstaff", password="pass")
        response = self.client.post(
            reverse("dashboard:warehouse_add_entry", args=[self.variant.pk]),
            {
                "source": StockEntry.SOURCE_PURCHASE,
                "quantity": "5",
                "occurred_at": timezone.localdate().isoformat(),
                "unit_price_net": "10.00",
                "vat_rate": "23",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 5)
        entry = StockEntry.objects.get(variant=self.variant)
        self.assertEqual(entry.direction, StockEntry.DIRECTION_IN)
        self.assertEqual(entry.created_by, self.staff_user)
        # brutto wyliczone serwerowo z netto + VAT
        self.assertEqual(entry.unit_price_gross, Decimal("12.30"))

    def test_delete_entry_recalculates_stock(self):
        from inventory.models import StockEntry
        from inventory.services import recalculate_variant_stock

        entry = StockEntry.objects.create(
            variant=self.variant, direction=StockEntry.DIRECTION_IN,
            source=StockEntry.SOURCE_PURCHASE, quantity=7,
        )
        recalculate_variant_stock(self.variant)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 7)

        self.client.login(username="whstaff", password="pass")
        response = self.client.post(reverse("dashboard:warehouse_delete_entry", args=[entry.pk]))
        self.assertEqual(response.status_code, 302)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 0)

    def test_new_variant_in_workspace_creates_opening_entry(self):
        from inventory.models import StockEntry

        product = Product.objects.create(name="Kolczyki", category=self.category, regular_price=Decimal("39.00"))
        self.client.login(username="whstaff", password="pass")
        response = self.client.post(
            reverse("dashboard:product_workspace", args=[product.pk]),
            {
                "product-name": product.name,
                "product-category": self.category.pk,
                "product-regular_price": "39.00",
                "product-status": Product.STATUS_DRAFT,
                "product-low_stock_threshold": "3",
                "variants-TOTAL_FORMS": "1",
                "variants-INITIAL_FORMS": "0",
                "variants-MIN_NUM_FORMS": "0",
                "variants-MAX_NUM_FORMS": "1000",
                "variants-0-stock_quantity": "8",
                "variants-0-sort_order": "0",
                "variants-0-is_active": "on",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_variant = product.variants.get()
        opening = StockEntry.objects.get(variant=new_variant, source=StockEntry.SOURCE_OPENING)
        self.assertEqual(opening.quantity, 8)
        new_variant.refresh_from_db()
        self.assertEqual(new_variant.stock_quantity, 8)


class InboxAndOrderStatusTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username="inboxstaff", password="pass", is_staff=True)
        self.client.login(username="inboxstaff", password="pass")

    def _inbound(self, read=False):
        from core.models import Message
        return Message.objects.create(
            direction=Message.DIRECTION_INBOUND,
            status=Message.STATUS_RECEIVED,
            subject="Pytanie",
            from_email="klient@example.pl",
            received_at=timezone.now(),
            read_at=timezone.now() if read else None,
        )

    def test_opening_message_marks_read(self):
        msg = self._inbound(read=False)
        response = self.client.get(reverse("dashboard:message_detail", args=[msg.pk]))
        self.assertEqual(response.status_code, 200)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)

    def test_bulk_mark_read_and_unread(self):
        from core.models import Message
        m1 = self._inbound(read=False)
        m2 = self._inbound(read=False)
        url = reverse("dashboard:bulk_message_action")

        self.client.post(url, {"message_ids": [m1.pk, m2.pk], "bulk_action": "read"})
        self.assertEqual(Message.objects.filter(read_at__isnull=True).count(), 0)

        self.client.post(url, {"message_ids": [m1.pk], "bulk_action": "unread"})
        m1.refresh_from_db()
        self.assertIsNone(m1.read_at)

    def test_order_status_label_is_polish(self):
        from dashboard.views import get_order_status_label
        from orders.models import Order
        self.assertEqual(get_order_status_label(Order.STATUS_AWAITING_PAYMENT), "Oczekuje na płatność")
        self.assertEqual(get_order_status_label(Order.STATUS_PLACED), "Złożone")
        # etykieta modelu też po polsku
        self.assertEqual(dict(Order.STATUS_CHOICES)[Order.STATUS_PLACED], "Złożone")
