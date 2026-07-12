from django.db import migrations


def mark_pickup(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    ShippingMethod.objects.filter(code__in=["paczkomat", "inpost", "paczkomaty"]).update(is_pickup_point=True)


def unmark_pickup(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    ShippingMethod.objects.update(is_pickup_point=False)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_pickup_point_address_order_pickup_point_code_and_more"),
    ]

    operations = [
        migrations.RunPython(mark_pickup, unmark_pickup),
    ]
