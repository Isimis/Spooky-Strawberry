from django.conf import settings
from django.db import models


class SavedCart(models.Model):
    """Koszyk zapisany per użytkownik — zostaje między sesjami i urządzeniami."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_cart",
    )
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SavedCart({self.user})"
