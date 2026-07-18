from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Replace


def replace_long_dashes(apps, schema_editor):
    targets = [
        ("catalog", "Category", ["name", "description"]),
        ("catalog", "Aesthetic", ["name", "tagline", "description"]),
        ("catalog", "Product", ["name", "description", "styling_tips", "seo_title", "seo_description"]),
        ("blog", "BlogCategory", ["name", "description"]),
        ("blog", "Article", ["title", "intro", "body", "seo_title", "seo_description"]),
        ("outfits", "Outfit", ["name", "short_description", "mood_description", "styling_tips", "seo_title", "seo_description"]),
        ("orders", "ShippingMethod", ["name", "description"]),
        ("orders", "Order", ["customer_note", "admin_note"]),
        ("core", "SiteSettings", ["announcement_text"]),
        ("core", "SitePage", ["title", "intro", "body", "seo_title", "seo_description"]),
        ("core", "HomepageSection", ["name", "eyebrow", "heading", "body", "cta_label"]),
        ("core", "MessageTemplate", ["name", "subject", "body_html", "description"]),
        ("core", "Message", ["subject", "body_html"]),
    ]
    for app_label, model_name, fields in targets:
        model = apps.get_model(app_label, model_name)
        for field in fields:
            replacement = Replace(Replace(F(field), Value("—"), Value("-")), Value("–"), Value("-"))
            model.objects.filter(**{f"{field}__contains": "—"}).update(**{field: replacement})
            model.objects.filter(**{f"{field}__contains": "–"}).update(**{field: replacement})


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_update_announcement_and_order_test_labels"),
        ("catalog", "0009_seed_collection_descriptions"),
        ("blog", "0003_article_cover_image"),
        ("outfits", "0003_outfithotspot"),
        ("orders", "0013_discountcode_first_order_only"),
    ]

    operations = [migrations.RunPython(replace_long_dashes, migrations.RunPython.noop)]
