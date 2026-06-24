from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CustomerProfile

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Zofia",
                "email": "Zofia@Example.PL",
                "password": "spookypass123",
                "accepts_marketing": "on",
            },
        )
        self.assertRedirects(response, reverse("accounts:account"))
        user = User.objects.get(email__iexact="zofia@example.pl")
        self.assertEqual(user.username, "zofia@example.pl")
        self.assertTrue(CustomerProfile.objects.filter(user=user, accepts_marketing=True).exists())
        self.assertIn("_auth_user_id", self.client.session)

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
        self.assertRedirects(response, reverse("accounts:account"))
        user = User.objects.get(email="verify@example.pl")
        # E-mail weryfikacyjny został wysłany; konto jeszcze niepotwierdzone.
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(user.customer_profile.email_verified)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify = self.client.get(reverse("accounts:verify_email", args=[uid, token]))
        self.assertEqual(verify.status_code, 302)
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.email_verified)

    def test_register_without_first_name_succeeds(self):
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "noname@example.pl", "password": "spookypass123"},
        )
        self.assertRedirects(response, reverse("accounts:account"))
        self.assertTrue(User.objects.filter(email="noname@example.pl").exists())

    def test_logout(self):
        User.objects.create_user(username="out@example.pl", email="out@example.pl", password="spookypass123")
        self.client.login(username="out@example.pl", password="spookypass123")
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)
