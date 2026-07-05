import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import handle_notification


@csrf_exempt
@require_POST
def przelewy24_webhook(request):
    """Odbiera powiadomienie P24 (urlStatus). Zawsze weryfikujemy podpis i verify."""
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid payload")

    # Zwracamy 200 nawet gdy nie potwierdzono — P24 nie ma wtedy nic ponawiać po naszej stronie,
    # a właściwym źródłem prawdy jest nasz verify. Błędny podpis/kwota = po prostu brak finalizacji.
    handle_notification(data)
    return HttpResponse("OK")
