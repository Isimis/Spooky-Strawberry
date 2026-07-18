from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_discountcode_once_per_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountcode",
            name="first_order_only",
            field=models.BooleanField(default=False),
        ),
    ]
