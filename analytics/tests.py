from django.test import TestCase
from django.urls import reverse

from .models import AnalyticsEvent


class AnalyticsMiddlewareTests(TestCase):
    def test_get_request_creates_page_view_event(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AnalyticsEvent.objects.filter(
                event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
                path="/",
            ).exists()
        )
