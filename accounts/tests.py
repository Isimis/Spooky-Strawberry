from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from . import social
from .models import CustomerProfile, SocialIdentity

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_register_creates_user_but_requires_verification(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "Zofia@Example.PL",
                "password": "spookypass123",
                "accepts_marketing": "on",
            },
        )
        # Nowe konto nie loguje się od razu - najpierw trzeba potwierdzić e-mail.
        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(email__iexact="zofia@example.pl")
        self.assertEqual(user.username, "zofia@example.pl")
        self.assertTrue(CustomerProfile.objects.filter(user=user, accepts_marketing=True).exists())
        self.assertFalse(user.customer_profile.email_verified)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="taken@example.pl", email="taken@example.pl", password="x")
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "taken@example.pl", "password": "spookypass123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "już istnieje")

    def test_login_with_email(self):
        User.objects.create_user(username="kasia@example.pl", email="kasia@example.pl", password="spookypass123")
        response = self.client.post(
            reverse("accounts:login_submit"),
            {"email": "kasia@example.pl", "password": "spookypass123"},
        )
        self.assertRedirects(response, reverse("accounts:account"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_invalid_shows_error(self):
        response = self.client.post(
            reverse("accounts:login_submit"),
            {"email": "nobody@example.pl", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nieprawidłowy e-mail lub hasło")

    def test_login_blocked_until_email_verified(self):
        from django.core import mail

        user = User.objects.create_user(
            username="nowa@example.pl", email="nowa@example.pl", password="spookypass123"
        )
        CustomerProfile.objects.create(user=user, email_verified=False)
        response = self.client.post(
            reverse("accounts:login_submit"),
            {"email": "nowa@example.pl", "password": "spookypass123"},
        )
        # Niepotwierdzony e-mail: brak logowania, a link aktywacyjny leci ponownie.
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)

    def test_login_succeeds_after_verification(self):
        user = User.objects.create_user(
            username="ok@example.pl", email="ok@example.pl", password="spookypass123"
        )
        CustomerProfile.objects.create(user=user, email_verified=True)
        response = self.client.post(
            reverse("accounts:login_submit"),
            {"email": "ok@example.pl", "password": "spookypass123"},
        )
        self.assertRedirects(response, reverse("accounts:account"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_password_reset_sends_link_and_sets_new_password(self):
        from django.core import mail

        user = User.objects.create_user(
            username="zapominalska@example.pl",
            email="zapominalska@example.pl",
            password="starehaslo123",
        )
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "zapominalska@example.pl"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_url = reverse("accounts:password_reset_confirm", args=[uid, token])
        # Pierwsze wejście przekierowuje na URL z tokenem w sesji (wzorzec Django).
        self.client.get(confirm_url)
        set_url = reverse(
            "accounts:password_reset_confirm", args=[uid, "set-password"]
        )
        response = self.client.post(
            set_url,
            {"new_password1": "nowehaslo123", "new_password2": "nowehaslo123"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("nowehaslo123"))

    def test_account_requires_login(self):
        response = self.client.get(reverse("accounts:account"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_account_renders_for_logged_in_user(self):
        User.objects.create_user(username="ola@example.pl", email="ola@example.pl", password="spookypass123")
        self.client.login(username="ola@example.pl", password="spookypass123")
        response = self.client.get(reverse("accounts:account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Moje konto")

    def test_register_sends_verification_and_verify_link_works(self):
        from django.core import mail
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from .models import CustomerProfile

        response = self.client.post(
            reverse("accounts:register"),
            {"email": "verify@example.pl", "password": "spookypass123"},
        )
        # Rejestracja nie loguje - odsyła na logowanie i wysyła link aktywacyjny.
        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(email="verify@example.pl")
        # E-mail weryfikacyjny został wysłany; konto jeszcze niepotwierdzone.
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(user.customer_profile.email_verified)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify = self.client.get(reverse("accounts:verify_email", args=[uid, token]))
        self.assertRedirects(verify, reverse("accounts:login"))
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.email_verified)

    def test_register_ignores_first_name_from_request(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"first_name": "Nie zapisuj", "email": "noname@example.pl", "password": "spookypass123"},
        )
        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(email="noname@example.pl")
        self.assertEqual(user.first_name, "")

    def test_verification_email_is_recorded_in_panel_mailbox(self):
        from core.models import Message

        self.client.post(
            reverse("accounts:register"),
            {"email": "panel@example.pl", "password": "spookypass123"},
        )
        # Mail weryfikacyjny jest zapisany jako wiadomość wychodząca w skrzynce panelu.
        self.assertTrue(
            Message.objects.filter(
                direction=Message.DIRECTION_OUTBOUND,
                to_email="panel@example.pl",
                subject__icontains="Potwierdź",
            ).exists()
        )

    def test_personal_data_saves_phone_to_profile(self):
        from .models import CustomerProfile

        User.objects.create_user(username="tel@example.pl", email="tel@example.pl", password="spookypass123")
        self.client.login(username="tel@example.pl", password="spookypass123")
        response = self.client.post(
            reverse("accounts:account"),
            {"form_kind": "personal", "first_name": "Ada", "last_name": "Nowak", "email": "tel@example.pl", "phone": "500600700"},
        )
        self.assertRedirects(response, reverse("accounts:account"))
        profile = CustomerProfile.objects.get(user__email="tel@example.pl")
        self.assertEqual(profile.phone, "500600700")

    def test_personal_data_email_sets_order_email_not_login(self):
        from .models import CustomerProfile

        user = User.objects.create_user(username="log@example.pl", email="log@example.pl", password="spookypass123")
        self.client.login(username="log@example.pl", password="spookypass123")
        response = self.client.post(
            reverse("accounts:account"),
            {"form_kind": "personal", "first_name": "Ada", "last_name": "Nowak", "email": "zamowienia@example.pl", "phone": ""},
        )
        self.assertRedirects(response, reverse("accounts:account"))
        user.refresh_from_db()
        # Adres logowania niezmienny; e-mail do zamówień zapisany osobno.
        self.assertEqual(user.email, "log@example.pl")
        self.assertEqual(CustomerProfile.objects.get(user=user).order_email, "zamowienia@example.pl")

    def test_account_saves_default_shipping_address(self):
        from .models import CustomerAddress, CustomerProfile

        User.objects.create_user(username="adr@example.pl", email="adr@example.pl", password="spookypass123")
        self.client.login(username="adr@example.pl", password="spookypass123")
        response = self.client.post(
            reverse("accounts:account"),
            {
                "form_kind": "address",
                "first_name": "Ada",
                "last_name": "Nowak",
                "address_line_1": "Ciemna 13",
                "address_line_2": "",
                "postal_code": "00-001",
                "city": "Warszawa",
                "phone": "",
            },
        )
        self.assertRedirects(response, reverse("accounts:account") + "#adresy")
        profile = CustomerProfile.objects.get(user__email="adr@example.pl")
        address = profile.default_shipping_address()
        self.assertIsNotNone(address)
        self.assertEqual(address.address_line_1, "Ciemna 13")
        self.assertEqual(address.address_type, CustomerAddress.TYPE_SHIPPING)
        self.assertTrue(address.is_default)

    def test_logout(self):
        User.objects.create_user(username="out@example.pl", email="out@example.pl", password="spookypass123")
        self.client.login(username="out@example.pl", password="spookypass123")
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(GOOGLE_OAUTH_CLIENT_ID="cid", GOOGLE_OAUTH_CLIENT_SECRET="secret")
class SocialLoginTests(TestCase):
    def _state(self, next_url="", via="session"):
        """Przygotowuje state jak widok startowy: nonce w sesji albo w ciasteczku."""
        state, nonce = social.make_state(next_url)
        if via == "session":
            from django.conf import settings as dj_settings

            session = self.client.session
            session[social.STATE_SESSION_KEY] = nonce
            session.save()
            # Po wylogowaniu klient testowy ma puste ciasteczko sesji - trzeba je
            # ręcznie podmienić na klucz świeżo zapisanej sesji.
            self.client.cookies[dj_settings.SESSION_COOKIE_NAME] = session.session_key
        else:
            self.client.cookies[social.STATE_COOKIE] = nonce
        return state

    def _google_claims(self, **extra):
        claims = {
            "sub": "g-123",
            "email": "gosia@example.pl",
            "email_verified": True,
            "given_name": "Gosia",
            "family_name": "Nowak",
        }
        claims.update(extra)
        return claims

    def test_start_redirects_to_google(self):
        response = self.client.get(reverse("accounts:social_start", args=["google"]) + "?next=/koszyk/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(social.GOOGLE_AUTH_URL))
        self.assertIn("client_id=cid", response.url)
        self.assertIn(social.STATE_SESSION_KEY, self.client.session)
        self.assertIn(social.STATE_COOKIE, response.cookies)

    def test_start_disabled_provider_redirects_with_error(self):
        response = self.client.get(reverse("accounts:social_start", args=["apple"]))
        self.assertRedirects(response, reverse("accounts:login"))

    @mock.patch("accounts.social.exchange_google_code")
    def test_google_callback_creates_account(self, exchange):
        exchange.return_value = self._google_claims()
        state = self._state()
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"code": "abc", "state": state}
        )
        self.assertRedirects(response, reverse("accounts:account"))
        user = User.objects.get(email="gosia@example.pl")
        self.assertEqual(user.first_name, "Gosia")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.customer_profile.email_verified)
        self.assertTrue(SocialIdentity.objects.filter(user=user, provider="google", subject="g-123").exists())
        self.assertIn("_auth_user_id", self.client.session)

    @mock.patch("accounts.social.exchange_google_code")
    def test_google_callback_second_login_reuses_account(self, exchange):
        exchange.return_value = self._google_claims()
        self.client.get(reverse("accounts:social_google_callback"), {"code": "a", "state": self._state()})
        self.client.post(reverse("accounts:logout"))
        self.client.get(reverse("accounts:social_google_callback"), {"code": "b", "state": self._state()})
        self.assertEqual(User.objects.filter(email="gosia@example.pl").count(), 1)
        self.assertEqual(SocialIdentity.objects.count(), 1)
        self.assertIn("_auth_user_id", self.client.session)

    @mock.patch("accounts.social.exchange_google_code")
    def test_google_callback_links_existing_account_by_email(self, exchange):
        user = User.objects.create_user(
            username="gosia@example.pl", email="gosia@example.pl", password="spookypass123"
        )
        exchange.return_value = self._google_claims()
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"code": "abc", "state": self._state()}
        )
        self.assertRedirects(response, reverse("accounts:account"))
        self.assertEqual(User.objects.filter(email__iexact="gosia@example.pl").count(), 1)
        self.assertTrue(SocialIdentity.objects.filter(user=user, provider="google").exists())

    @mock.patch("accounts.social.exchange_google_code")
    def test_google_callback_refuses_unverified_email_link(self, exchange):
        User.objects.create_user(
            username="gosia@example.pl", email="gosia@example.pl", password="spookypass123"
        )
        exchange.return_value = self._google_claims(email_verified=False)
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"code": "abc", "state": self._state()}
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(SocialIdentity.objects.exists())

    def test_google_callback_rejects_bad_state(self):
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"code": "abc", "state": "podrobiony"}
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    @mock.patch("accounts.social.exchange_google_code")
    def test_google_callback_rejects_state_without_nonce_match(self, exchange):
        exchange.return_value = self._google_claims()
        state, _ = social.make_state("")  # nonce nie trafia do sesji ani ciasteczka
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"code": "abc", "state": state}
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_google_callback_cancelled(self):
        response = self.client.get(
            reverse("accounts:social_google_callback"), {"error": "access_denied"}
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(User.objects.exists())

    @mock.patch("accounts.social.exchange_apple_code")
    def test_apple_callback_post_creates_account_with_name(self, exchange):
        exchange.return_value = {"sub": "apple-9", "email": "jan@privaterelay.appleid.com", "email_verified": "true"}
        # Apple wraca POST-em bez ciasteczka sesji - nonce weryfikowany z ciasteczka.
        state = self._state(via="cookie")
        response = self.client.post(
            reverse("accounts:social_apple_callback"),
            {
                "code": "abc",
                "state": state,
                "user": '{"name": {"firstName": "Jan", "lastName": "Kowalski"}}',
            },
        )
        self.assertRedirects(response, reverse("accounts:account"))
        user = User.objects.get(email="jan@privaterelay.appleid.com")
        self.assertEqual(user.first_name, "Jan")
        self.assertEqual(user.last_name, "Kowalski")
        self.assertTrue(SocialIdentity.objects.filter(user=user, provider="apple", subject="apple-9").exists())
        self.assertIn("_auth_user_id", self.client.session)

    @mock.patch("accounts.social.exchange_google_code")
    def test_callback_respects_safe_next(self, exchange):
        exchange.return_value = self._google_claims()
        response = self.client.get(
            reverse("accounts:social_google_callback"),
            {"code": "abc", "state": self._state(next_url="https://zlo.example/")},
        )
        # Zewnętrzny adres w next jest odrzucany - lądujemy na koncie.
        self.assertRedirects(response, reverse("accounts:account"))
