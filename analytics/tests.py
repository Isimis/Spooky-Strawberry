from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import AnalyticsEvent, AnalyticsSession
from .services import VISITOR_COOKIE_NAME


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

    def test_visitor_cookie_is_reused_across_django_sessions(self):
        first_response = self.client.get(reverse("core:home"))
        visitor_id = first_response.cookies[VISITOR_COOKIE_NAME].value

        if settings.SESSION_COOKIE_NAME in self.client.cookies:
            del self.client.cookies[settings.SESSION_COOKIE_NAME]
        second_response = self.client.get(reverse("core:home"))

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            AnalyticsSession.objects.values("visitor_id").distinct().count(),
            1,
        )
        self.assertEqual(
            AnalyticsSession.objects.values_list("visitor_id", flat=True).first(),
            visitor_id,
        )

    def test_new_event_refreshes_session_last_seen_at(self):
        self.client.get(reverse("core:home"))
        session = AnalyticsSession.objects.get()
        old_last_seen = timezone.now() - timedelta(hours=2)
        AnalyticsSession.objects.filter(pk=session.pk).update(last_seen_at=old_last_seen)

        self.client.get(reverse("catalog:product_list"))

        session.refresh_from_db()
        self.assertGreater(session.last_seen_at, old_last_seen)
