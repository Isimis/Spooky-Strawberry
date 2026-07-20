from decimal import Decimal

from django.db import migrations


def update_shipping_prices(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    price = Decimal("18.99")
    ShippingMethod.objects.filter(code__in=["paczkomat", "inpost", "paczkomaty"]).update(price=price)
    ShippingMethod.objects.filter(code="kurier").update(price=price)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_private_message_attachment_storage"),
        ("orders", "0013_discountcode_first_order_only"),
    ]

    operations = [migrations.RunPython(update_shipping_prices, migrations.RunPython.noop)]
