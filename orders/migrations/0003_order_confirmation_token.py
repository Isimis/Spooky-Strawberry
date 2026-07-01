import secrets

import orders.models
from django.db import migrations, models


def populate_confirmation_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    used_tokens = set(
        Order.objects.exclude(confirmation_token__isnull=True)
        .exclude(confirmation_token="")
        .values_list("confirmation_token", flat=True)
    )

    for order in Order.objects.filter(models.Q(confirmation_token__isnull=True) | models.Q(confirmation_token="")):
        token = secrets.token_urlsafe(32)
        while token in used_tokens:
            token = secrets.token_urlsafe(32)
        used_tokens.add(token)
        order.confirmation_token = token
        order.save(update_fields=["confirmation_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_order_order_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="confirmation_token",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.RunPython(populate_confirmation_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="confirmation_token",
            field=models.CharField(
                blank=True,
                default=orders.models.generate_order_confirmation_token,
                max_length=80,
                unique=True,
            ),
        ),
    ]
