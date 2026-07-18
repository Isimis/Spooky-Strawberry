"""Logowanie społecznościowe - Google i Apple (OAuth 2.0 / OpenID Connect).

Ręczna integracja w stylu reszty projektu (jak payments/przelewy24.py) - bez
django-allauth. Standardowy flow "authorization code":

1. /konto/social/<provider>/start/ przekierowuje do ekranu logowania dostawcy,
2. dostawca odsyła użytkownika na nasz callback z jednorazowym kodem,
3. wymieniamy kod na id_token bezpośrednio na endpointcie tokenów dostawcy,
4. z id_tokenu bierzemy e-mail i stały identyfikator (sub) → logujemy/zakładamy konto.

Nie weryfikujemy podpisu id_tokenu, bo dostajemy go bezpośrednio z serwera
Google/Apple po TLS - zaufanie wynika z połączenia, nie z podpisu.

Parametr `state` jest podpisany (django.core.signing) i dodatkowo związany
z przeglądarką przez nonce w sesji ORAZ w osobnym ciasteczku. Samo związanie
z sesją nie wystarcza, bo Apple odsyła użytkownika POST-em z innej domeny
(response_mode=form_post), a przeglądarka nie wysyła wtedy ciasteczka sesji
(SameSite=Lax) - dlatego ciasteczko stanu ma SameSite=None na HTTPS.
"""

import base64
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse

from .models import CustomerProfile, SocialIdentity

logger = logging.getLogger(__name__)

User = get_user_model()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"

STATE_SALT = "accounts.social.state"
STATE_MAX_AGE = 600  # 10 minut na przejście przez ekran logowania dostawcy
STATE_SESSION_KEY = "social_login_nonce"
STATE_COOKIE = "spooky_social_state"

GENERIC_ERROR = "Logowanie się nie powiodło - spróbuj ponownie lub użyj e-maila i hasła."


class SocialAuthError(Exception):
    """Błąd logowania społecznościowego - komunikat nadaje się do pokazania użytkownikowi."""


def google_enabled():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def apple_enabled():
    return bool(
        settings.APPLE_OAUTH_CLIENT_ID
        and settings.APPLE_OAUTH_TEAM_ID
        and settings.APPLE_OAUTH_KEY_ID
        and _apple_private_key()
    )


# --- Parametr state (ochrona przed CSRF na callbacku) ---


def make_state(next_url):
    """Zwraca (state, nonce): podpisany state do URL-a + nonce do sesji/ciasteczka."""
    nonce = secrets.token_urlsafe(16)
    state = signing.dumps({"next": next_url or "", "nonce": nonce}, salt=STATE_SALT)
    return state, nonce


def read_state(state, expected_nonces):
    """Waliduje state z callbacku; zwraca payload ({"next": ...}).

    `expected_nonces` to wartości z sesji i ciasteczka - wystarczy zgodność
    z jedną z nich (Google wraca GET-em z sesją, Apple POST-em z ciasteczkiem).
    """
    try:
        payload = signing.loads(state or "", salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.SignatureExpired:
        raise SocialAuthError("Logowanie trwało zbyt długo - spróbuj ponownie.")
    except signing.BadSignature:
        raise SocialAuthError(GENERIC_ERROR)
    nonce = payload.get("nonce", "")
    if not nonce or nonce not in [n for n in expected_nonces if n]:
        raise SocialAuthError("Sesja logowania wygasła - spróbuj ponownie.")
    return payload


# --- Budowa URL-i autoryzacji ---


def google_authorize_url(request, state):
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": request.build_absolute_uri(reverse("accounts:social_google_callback")),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def apple_authorize_url(request, state):
    params = {
        "client_id": settings.APPLE_OAUTH_CLIENT_ID,
        "redirect_uri": request.build_absolute_uri(reverse("accounts:social_apple_callback")),
        "response_type": "code",
        "scope": "name email",
        # Przy scope Apple wymaga form_post - callback przychodzi POST-em.
        "response_mode": "form_post",
        "state": state,
    }
    return f"{APPLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


# --- Wymiana kodu na id_token ---


def exchange_google_code(request, code):
    data = _post_form(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": request.build_absolute_uri(reverse("accounts:social_google_callback")),
            "grant_type": "authorization_code",
        },
    )
    return _id_token_claims(data.get("id_token", ""))


def exchange_apple_code(request, code):
    data = _post_form(
        APPLE_TOKEN_URL,
        {
            "code": code,
            "client_id": settings.APPLE_OAUTH_CLIENT_ID,
            "client_secret": _apple_client_secret(),
            "redirect_uri": request.build_absolute_uri(reverse("accounts:social_apple_callback")),
            "grant_type": "authorization_code",
        },
    )
    return _id_token_claims(data.get("id_token", ""))


def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        logger.warning("Social login: %s odpowiedział %s: %s", url, exc.code, detail)
        raise SocialAuthError(GENERIC_ERROR)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Social login: błąd połączenia z %s: %s", url, exc)
        raise SocialAuthError(GENERIC_ERROR)


def _id_token_claims(id_token):
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        logger.warning("Social login: nie udało się odczytać id_tokenu")
        raise SocialAuthError(GENERIC_ERROR)


def _apple_private_key():
    """Klucz .p8 z env - wprost (APPLE_OAUTH_PRIVATE_KEY) albo ze ścieżki do pliku."""
    key = settings.APPLE_OAUTH_PRIVATE_KEY
    if key:
        return key
    path = settings.APPLE_OAUTH_PRIVATE_KEY_FILE
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            logger.warning("Social login: nie można odczytać klucza Apple z %s", path)
    return ""


def _apple_client_secret():
    """Apple nie ma stałego client_secret - jest nim krótkotrwały JWT podpisany kluczem .p8."""
    import jwt  # PyJWT - import lokalnie, by Google działał nawet bez tej paczki

    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.APPLE_OAUTH_TEAM_ID,
            "iat": now,
            "exp": now + 600,
            "aud": "https://appleid.apple.com",
            "sub": settings.APPLE_OAUTH_CLIENT_ID,
        },
        _apple_private_key(),
        algorithm="ES256",
        headers={"kid": settings.APPLE_OAUTH_KEY_ID},
    )


# --- Dopasowanie / założenie konta ---


def get_or_create_user(provider, claims, first_name="", last_name=""):
    """Zwraca (user, created) dla zalogowanego u dostawcy użytkownika.

    Kolejność: znana tożsamość (provider+sub) → istniejące konto po e-mailu
    (tylko gdy dostawca potwierdził e-mail - inaczej dałoby się przejąć cudze
    konto) → nowe konto bez hasła (logowanie tylko przez dostawcę, dopóki
    użytkownik nie ustawi hasła).
    """
    sub = str(claims.get("sub") or "")
    email = (claims.get("email") or "").strip().lower()
    email_verified = claims.get("email_verified")
    if isinstance(email_verified, str):
        email_verified = email_verified.lower() == "true"

    if not sub:
        raise SocialAuthError(GENERIC_ERROR)

    identity = (
        SocialIdentity.objects.filter(provider=provider, subject=sub).select_related("user").first()
    )
    if identity is not None:
        if not identity.user.is_active:
            raise SocialAuthError("To konto jest nieaktywne.")
        return identity.user, False

    if not email:
        raise SocialAuthError(
            "Dostawca nie udostępnił adresu e-mail. Załóż konto e-mailem i hasłem."
        )

    user = (
        User.objects.filter(email__iexact=email).first()
        or User.objects.filter(username__iexact=email).first()
    )
    created = False
    if user is not None:
        if not email_verified:
            raise SocialAuthError(
                "Nie możemy połączyć tego logowania z istniejącym kontem, "
                "bo dostawca nie potwierdził adresu e-mail. Zaloguj się hasłem."
            )
        if not user.is_active:
            raise SocialAuthError("To konto jest nieaktywne.")
    else:
        user = User.objects.create_user(
            username=email,
            email=email,
            password=None,  # brak hasła - logowanie przez dostawcę
            first_name=(first_name or claims.get("given_name") or "")[:80],
            last_name=(last_name or claims.get("family_name") or "")[:80],
        )
        created = True

    SocialIdentity.objects.get_or_create(user=user, provider=provider, subject=sub)
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    if email_verified and not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    return user, created
