from decimal import Decimal

from django.db import migrations


DEFAULT_METHODS = (
    {
        "code": "paczkomat",
        "name": "Paczkomat",
        "description": "Dostawa do paczkomatu InPost w 1-2 dni robocze.",
        "price": Decimal("10.99"),
        "free_from_amount": Decimal("60.00"),
        "sort_order": 10,
    },
    {
        "code": "kurier",
        "name": "Kurier",
        "description": "Dostawa kurierem pod wskazany adres w 1-2 dni robocze.",
        "price": Decimal("13.99"),
        "free_from_amount": Decimal("60.00"),
        "sort_order": 20,
    },
)


def configure_shipping_methods(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    active_codes = [method["code"] for method in DEFAULT_METHODS]

    for method in DEFAULT_METHODS:
        ShippingMethod.objects.update_or_create(
            code=method["code"],
            defaults={
                "name": method["name"],
                "description": method["description"],
                "price": method["price"],
                "free_from_amount": method["free_from_amount"],
                "sort_order": method["sort_order"],
                "is_active": True,
            },
        )

    ShippingMethod.objects.exclude(code__in=active_codes).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_confirmation_token"),
    ]

    operations = [
        migrations.RunPython(configure_shipping_methods, migrations.RunPython.noop),
    ]
