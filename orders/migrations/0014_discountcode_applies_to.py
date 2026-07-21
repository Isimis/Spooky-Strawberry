from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0013_discountcode_first_order_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountcode",
            name="applies_to",
            field=models.CharField(
                choices=[
                    ("products", "Produkty"),
                    ("shipping", "Dostawa"),
                    ("order", "Zamówienie"),
                ],
                default="products",
                max_length=20,
            ),
        ),
    ]
