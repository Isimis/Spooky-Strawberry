from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_analyticssession_visitor_id"),
        ("blog", "0003_article_cover_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="analyticsevent",
            name="article",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="analytics_events",
                to="blog.article",
            ),
        ),
    ]
