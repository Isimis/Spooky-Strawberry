from django.db import migrations, models


OLD_ANNOUNCEMENTS = {
    "🦇 Darmowa dostawa od 50 zł · 30 dni na zwrot",
    "đź¦‡ Darmowa dostawa od 50 zĹ‚ Â· 30 dni na zwrot",
}
NEW_ANNOUNCEMENT = "🦇 Darmowa dostawa od 60 zł · 30 dni na zwrot"


def update_shipping_announcement(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(announcement_text__in=OLD_ANNOUNCEMENTS).update(
        announcement_text=NEW_ANNOUNCEMENT
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_seed_base_email_layout"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="announcement_text",
            field=models.CharField(
                blank=True,
                default=NEW_ANNOUNCEMENT,
                max_length=255,
            ),
        ),
        migrations.RunPython(update_shipping_announcement, migrations.RunPython.noop),
    ]
