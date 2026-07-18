from django.db import migrations

from core.email_seed import seed_templates


def apply(apps, schema_editor):
    seed_templates(apps.get_model("core", "MessageTemplate"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_rebuild_email_templates"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
