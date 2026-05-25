# Generated for the first Spooky Strawberry catalog model pass.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="StyleTag",
            new_name="Aesthetic",
        ),
        migrations.RenameField(
            model_name="product",
            old_name="style_tags",
            new_name="aesthetics",
        ),
        migrations.AlterModelOptions(
            name="aesthetic",
            options={
                "ordering": ["sort_order", "name"],
                "verbose_name": "Aesthetic",
                "verbose_name_plural": "Aesthetics",
            },
        ),
        migrations.AddField(
            model_name="aesthetic",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="aesthetic",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="aesthetic",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="aesthetic",
            name="slug",
            field=models.SlugField(blank=True, max_length=140, unique=True),
        ),
        migrations.AddField(
            model_name="category",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="category",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="catalog.category",
            ),
        ),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(blank=True, max_length=140, unique=True),
        ),
        migrations.AddField(
            model_name="color",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="color",
            name="slug",
            field=models.SlugField(blank=True, max_length=100, unique=True),
        ),
        migrations.AddField(
            model_name="size",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="size",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="size",
            name="slug",
            field=models.SlugField(blank=True, max_length=70, unique=True),
        ),
        migrations.AlterModelOptions(
            name="size",
            options={
                "ordering": ["sort_order", "name"],
                "verbose_name": "Size",
                "verbose_name_plural": "Sizes",
            },
        ),
        migrations.AddField(
            model_name="product",
            name="compare_at_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="product",
            name="base_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterModelOptions(
            name="product",
            options={"ordering": ["sort_order", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["status", "created_at"],
                name="cat_product_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["is_featured"],
                name="cat_product_featured_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["is_new_drop"],
                name="cat_product_new_drop_idx",
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="price_override",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="sku",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.AlterModelOptions(
            name="productvariant",
            options={"ordering": ["product__name", "sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(
                fields=("product", "color", "size"),
                name="unique_variant_options_per_product",
            ),
        ),
        migrations.AddField(
            model_name="productimage",
            name="caption",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_main", True)),
                fields=("product",),
                name="unique_main_image_per_product",
            ),
        ),
    ]
