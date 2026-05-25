from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from analytics.models import AnalyticsEvent, AnalyticsSession
from catalog.models import Category, Color, Product, ProductVariant
from dashboard.models import DataQualityIssue


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
        self.assertEqual(list_response.status_code, 200)

    def test_dashboard_shows_analytics_summary(self):
        session = AnalyticsSession.objects.create(
            session_key="test-session",
            referrer="https://www.instagram.com/spookystrawberry",
            device_type="desktop",
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
        self.assertContains(response, "desktop")

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

    def test_staff_user_can_open_product_workspace(self):
        product = self.create_product("Workspace Product", "workspace-product")
        ProductVariant.objects.create(product=product, stock_quantity=3, is_active=True)
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:product_workspace", args=[product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace Product")
        self.assertContains(response, "Warianty")

    def test_quality_refresh_creates_product_issue(self):
        product = self.create_product("Incomplete Product", "incomplete-product")
        self.client.login(username="staff", password="pass")

        response = self.client.post(reverse("dashboard:refresh_quality"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(DataQualityIssue.objects.filter(product=product, status=DataQualityIssue.STATUS_OPEN).exists())

    def create_product(self, name, slug):
        category, _ = Category.objects.get_or_create(name="Chokery", slug="chokery")
        return Product.objects.create(
            name=name,
            slug=slug,
            category=category,
            base_price="29.00",
            status=Product.STATUS_ACTIVE,
        )
