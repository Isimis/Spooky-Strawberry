from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import restore_cart_for_user, save_cart_for_user


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """Po zalogowaniu odtwórz zapisany koszyk i zsynchronizuj go z sesją."""
    if request is None:
        return
    restore_cart_for_user(request)
    save_cart_for_user(request)
