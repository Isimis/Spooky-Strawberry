from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMessageAttachmentStorage(FileSystemStorage):
    """Storage poza publicznym /media, dostępny wyłącznie przez widok dla administracji."""

    def __init__(self):
        super().__init__(
            file_permissions_mode=0o640,
            directory_permissions_mode=0o750,
        )

    @property
    def base_location(self):
        return str(settings.MESSAGE_ATTACHMENT_ROOT)
