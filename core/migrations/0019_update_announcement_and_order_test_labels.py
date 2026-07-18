from django.db import migrations


ANNOUNCEMENT = "Darmowa dostawa od 100 zł 🍓"
TEST_NOTE_MARKERS = {"test", "testowe", "sandbox", "test (sandbox)", "zamówienie testowe"}


def update_store_copy(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Order = apps.get_model("orders", "Order")

    SiteSettings.objects.update_or_create(
        pk=1,
        defaults={"announcement_is_active": True, "announcement_text": ANNOUNCEMENT},
    )

    # Starsze testowe zamówienia bywały dodatkowo opisywane w notatce jako
    # „Test”. Usuwamy wyłącznie takie techniczne, samodzielne oznaczenia.
    for order in Order.objects.filter(is_test=True).exclude(admin_note=""):
        if order.admin_note.strip().casefold() in TEST_NOTE_MARKERS:
            order.admin_note = ""
            order.save(update_fields=["admin_note", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0018_unify_store_information")]

    operations = [migrations.RunPython(update_store_copy, migrations.RunPython.noop)]
