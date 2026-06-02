from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from decimal import Decimal

from analytics.models import AnalyticsEvent, AnalyticsSession
from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size
from dashboard.models import DataQualityIssue
from dashboard.services import get_dashboard_analytics
from dashboard.views import filter_product_image_files, sync_product_main_image
from orders.models import Order, OrderItem
from outfits.models import Outfit, OutfitImage, OutfitItem


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
        self.assertNotContains(response, "Produkty w kreacjach")
        self.assertNotContains(response, "Zdjęcia kreacji")

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
            },
        )

        outfit.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(outfit.status, Outfit.STATUS_ACTIVE)
        self.assertEqual(outfit.bundle_price, Decimal("39.00"))
        self.assertTrue(OutfitItem.objects.filter(outfit=outfit, product=product, quantity=2).exists())

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
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(OutfitImage.objects.filter(id=image.id).exists())

    def test_article_list_uses_custom_layout(self):
        category = BlogCategory.objects.create(name="Stylizacje", slug="stylizacje")
        Article.objects.create(
            title="Jak nosić chokery",
            slug="jak-nosic-chokery",
            category=category,
            intro="Krótki poradnik o dodatkach.",
            body="Body",
            cover_image="articles/chokery.webp",
            status=Article.STATUS_PUBLISHED,
            is_featured=True,
        )
        self.client.login(username="staff", password="pass")

        response = self.client.get(reverse("dashboard:model_list", args=["articles"]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/article_list.html")
        self.assertContains(response, "Jak nosić chokery")
        self.assertContains(response, "Opublikowane")
        self.assertContains(response, "Z okładką")
        self.assertContains(response, "Krótki poradnik o dodatkach.")

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
