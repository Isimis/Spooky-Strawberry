from django.test import TestCase
from django.urls import reverse

from .models import NewsletterSubscriber


class NewsletterTests(TestCase):
    def test_newsletter_subscribe_creates_subscriber(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "test@example.com", "next": reverse("core:home")},
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(NewsletterSubscriber.objects.filter(email="test@example.com").exists())
