from django.db import migrations
from django.utils import timezone


def create_opening_balances(apps, schema_editor):
    """Dla istniejących wariantów ze stanem > 0 tworzy wpis 'stan początkowy',
    aby magazyn stał się źródłem prawdy bez utraty bieżących stanów."""
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    StockEntry = apps.get_model("inventory", "StockEntry")
    today = timezone.localdate()

    entries = [
        StockEntry(
            variant=variant,
            direction="in",
            source="opening",
            quantity=variant.stock_quantity,
            occurred_at=today,
        )
        for variant in ProductVariant.objects.filter(stock_quantity__gt=0)
    ]
    StockEntry.objects.bulk_create(entries)


def remove_opening_balances(apps, schema_editor):
    StockEntry = apps.get_model("inventory", "StockEntry")
    StockEntry.objects.filter(source="opening").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_opening_balances, remove_opening_balances),
    ]
