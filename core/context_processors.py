from .models import SiteSettings


def site_settings(request):
    """Udostępnia globalne ustawienia treści (pasek, drop, progi) we wszystkich szablonach."""
    return {"site_settings": SiteSettings.load()}
