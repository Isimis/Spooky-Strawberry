from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_seed_collection_descriptions"),
        ("core", "0023_update_shipping_prices"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="hero_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hero_settings",
                to="catalog.product",
            ),
        ),
    ]
