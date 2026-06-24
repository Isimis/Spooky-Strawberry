from django.test import TestCase
from django.urls import reverse

from .models import NewsletterSubscriber


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
