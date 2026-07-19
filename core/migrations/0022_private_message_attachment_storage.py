import core.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_message_attachments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="messageattachment",
            name="file",
            field=models.FileField(storage=core.storage.PrivateMessageAttachmentStorage(), upload_to="message_attachments/%Y/%m/%d/"),
        ),
    ]
