from django.db import migrations, models
from django.utils import timezone


def mark_existing_inbound_as_read(apps, schema_editor):
    Message = apps.get_model("core", "Message")
    Message.objects.filter(direction="inbound", read_at__isnull=True).update(read_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_message_external_id_message_received_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["direction", "read_at"], name="message_dir_read_idx"),
        ),
        migrations.RunPython(mark_existing_inbound_as_read, migrations.RunPython.noop),
    ]
