from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Article, BlogCategory


class ArticleViewTests(TestCase):
    def setUp(self):
        category = BlogCategory.objects.create(name="Stylizacje", slug="stylizacje")
        self.article = Article.objects.create(
            title="Test Article",
            slug="test-article",
            category=category,
            intro="Intro",
            body="## Body\n\n- Point\n\n> Quote",
            cover_image="articles/test.webp",
            status=Article.STATUS_PUBLISHED,
        )

    def test_article_list_and_detail_render(self):
        list_response = self.client.get(reverse("blog:list"))
        detail_response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Test Article")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "articles/test.webp")
        self.assertContains(detail_response, "<h2>Body</h2>", html=True)
        self.assertContains(detail_response, "<li>Point</li>", html=True)
        self.assertContains(detail_response, "<blockquote>Quote</blockquote>", html=True)

    def test_featured_article_is_used_for_the_main_card(self):
        newest = Article.objects.create(
            title="Najnowszy wpis",
            slug="najnowszy-wpis",
            body="Treść",
            status=Article.STATUS_PUBLISHED,
            published_at=timezone.now(),
        )
        featured = Article.objects.create(
            title="Wyróżniony wpis",
            slug="wyrozniony-wpis",
            body="Treść",
            status=Article.STATUS_PUBLISHED,
            is_featured=True,
            published_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(reverse("blog:list"))

        self.assertEqual(response.context["featured_article"], featured)
        self.assertContains(response, featured.title)
        self.assertContains(response, newest.title)
