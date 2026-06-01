from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_remove_product_cat_product_new_drop_idx_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="mood_description",
            new_name="description",
        ),
        migrations.RenameField(
            model_name="product",
            old_name="base_price",
            new_name="regular_price",
        ),
        migrations.RenameField(
            model_name="product",
            old_name="compare_at_price",
            new_name="sale_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="short_description",
        ),
        migrations.RemoveField(
            model_name="product",
            name="details",
        ),
    ]
