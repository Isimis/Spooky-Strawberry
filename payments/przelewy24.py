"""Klient REST API Przelewy24 (bez zewnętrznych zależności — stdlib urllib).

Przepływ:
1. ``register`` — rejestrujemy transakcję, dostajemy ``token``.
2. Klient płaci na hostowanej stronie P24 (``gateway_url``) — tam jest BLIK, karta, przelew.
3. P24 woła nasz webhook (urlStatus). Podpis webhooka weryfikujemy ``verify_notification_sign``.
4. ``verify`` — potwierdzamy transakcję u P24 (dopiero to oznacza realne opłacenie).

Podpisy: SHA-384 z JSON-a o ustalonej kolejności kluczy + klucz CRC.
Dokumentacja: https://developers.przelewy24.pl/
"""

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request

from django.conf import settings

SANDBOX_BASE = "https://sandbox.przelewy24.pl"
PRODUCTION_BASE = "https://secure.przelewy24.pl"


class Przelewy24Error(Exception):
    """Błąd komunikacji lub odpowiedź negatywna z P24."""


def _config():
    return {
        "merchant_id": int(settings.P24_MERCHANT_ID or 0),
        "pos_id": int(settings.P24_POS_ID or settings.P24_MERCHANT_ID or 0),
        "crc": settings.P24_CRC or "",
        "api_key": settings.P24_API_KEY or "",
        "sandbox": bool(settings.P24_SANDBOX),
    }


def base_url():
    return SANDBOX_BASE if _config()["sandbox"] else PRODUCTION_BASE


def _sign(ordered_fields):
    """SHA-384 z JSON-a o ściśle ustalonej kolejności kluczy (wymóg P24)."""
    payload = json.dumps(ordered_fields, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha384(payload.encode("utf-8")).hexdigest()


def _request(path, body):
    cfg = _config()
    url = f"{base_url()}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    auth = base64.b64encode(f"{cfg['pos_id']}:{cfg['api_key']}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise Przelewy24Error(f"P24 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise Przelewy24Error(f"P24 połączenie nieudane: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Przelewy24Error(f"P24 nieczytelna odpowiedź: {raw[:200]}") from exc


def _get(path):
    cfg = _config()
    url = f"{base_url()}{path}"
    auth = base64.b64encode(f"{cfg['pos_id']}:{cfg['api_key']}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(url, method="GET", headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 404 = brak takiej transakcji (np. jeszcze nieopłacona) — traktujemy jako brak danych.
        if exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", "replace")
        raise Przelewy24Error(f"P24 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise Przelewy24Error(f"P24 połączenie nieudane: {exc.reason}") from exc


def by_session_id(session_id):
    """Zwraca dane transakcji po naszym sessionId (m.in. orderId, status) albo None.

    Pozwala stronie powrotu ustalić orderId bez czekania na webhook.
    """
    result = _get(f"/api/v1/transaction/by/sessionId/{session_id}")
    if not result:
        return None
    return result.get("data") or None


def register(*, session_id, amount_grosze, email, description, url_return, url_status, currency="PLN"):
    """Rejestruje transakcję. Zwraca token do przekierowania klienta."""
    cfg = _config()
    sign = _sign(
        {
            "sessionId": session_id,
            "merchantId": cfg["merchant_id"],
            "amount": amount_grosze,
            "currency": currency,
            "crc": cfg["crc"],
        }
    )
    body = {
        "merchantId": cfg["merchant_id"],
        "posId": cfg["pos_id"],
        "sessionId": session_id,
        "amount": amount_grosze,
        "currency": currency,
        "description": description,
        "email": email,
        "country": "PL",
        "language": "pl",
        "urlReturn": url_return,
        "urlStatus": url_status,
        "sign": sign,
        "encoding": "UTF-8",
    }
    result = _request("/api/v1/transaction/register", body)
    token = (result.get("data") or {}).get("token")
    if not token:
        raise Przelewy24Error(f"P24 nie zwróciło tokenu: {result}")
    return token, result


def gateway_url(token):
    """Adres hostowanej strony płatności, na którą przekierowujemy klienta."""
    return f"{base_url()}/trnRequest/{token}"


def verify_notification_sign(data):
    """Weryfikuje podpis przychodzącego webhooka (urlStatus)."""
    cfg = _config()
    expected = _sign(
        {
            "merchantId": cfg["merchant_id"],
            "posId": cfg["pos_id"],
            "sessionId": data.get("sessionId"),
            "amount": data.get("amount"),
            "originAmount": data.get("originAmount"),
            "currency": data.get("currency"),
            "orderId": data.get("orderId"),
            "methodId": data.get("methodId"),
            "statement": data.get("statement"),
            "crc": cfg["crc"],
        }
    )
    provided = str(data.get("sign", ""))
    # porównanie odporne na timing; na bajtach — nie wywróci się na nie-ASCII w podpisie
    return hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


def verify(*, session_id, amount_grosze, order_id, currency="PLN"):
    """Potwierdza transakcję u P24 (źródło prawdy o opłaceniu)."""
    cfg = _config()
    sign = _sign(
        {
            "sessionId": session_id,
            "orderId": int(order_id),
            "amount": amount_grosze,
            "currency": currency,
            "crc": cfg["crc"],
        }
    )
    body = {
        "merchantId": cfg["merchant_id"],
        "posId": cfg["pos_id"],
        "sessionId": session_id,
        "amount": amount_grosze,
        "currency": currency,
        "orderId": int(order_id),
        "sign": sign,
    }
    result = _request("/api/v1/transaction/verify", body)
    status = (result.get("data") or {}).get("status")
    return status == "success", result
