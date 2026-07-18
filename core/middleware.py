from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    """Przekierowuje ruch na jedną kanoniczną domenę (np. www → goła domena).

    Włączane przez ``CANONICAL_HOST`` (np. ``spookystrawberry.pl``). Puste = wyłączone,
    więc lokalnie i w testach nic nie robi. Porządkuje rozjazd www/apex - istotne m.in.
    dla spójności sesji płatności i tokenu Geowidget przypiętego do jednej domeny.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical = (getattr(settings, "CANONICAL_HOST", "") or "").strip()

    def __call__(self, request):
        if self.canonical and not request.path.startswith("/.well-known/"):
            try:
                host = request.get_host()
            except Exception:
                host = ""
            if host and host != self.canonical:
                target = f"{request.scheme}://{self.canonical}{request.get_full_path()}"
                return HttpResponsePermanentRedirect(target)
        return self.get_response(request)
