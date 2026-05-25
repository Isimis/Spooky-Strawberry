from django.test import TestCase
from django.urls import reverse

from .models import Article, BlogCategory


class ArticleViewTests(TestCase):
    def setUp(self):
        category = BlogCategory.objects.create(name="Stylizacje", slug="stylizacje")
        self.article = Article.objects.create(
            title="Test Article",
            slug="test-article",
            category=category,
            intro="Intro",
            body="Body",
            status=Article.STATUS_PUBLISHED,
        )

    def test_article_list_and_detail_render(self):
        list_response = self.client.get(reverse("blog:list"))
        detail_response = self.client.get(self.article.get_absolute_url())

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Test Article")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Body")
