import json

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.models import Order

from . import social
from .forms import AddressForm, ConsentsForm, EmailLoginForm, PersonalDataForm, RegistrationForm
from .models import CustomerAddress, CustomerProfile

User = get_user_model()


def send_verification_email(request, user):
    """Wysyła link weryfikacyjny e-mail (systemowy szablon `account-verification`)."""
    if not user.email:
        return
    from core.emails import send_account_verification

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(reverse("accounts:verify_email", args=[uid, token]))
    send_account_verification(user.email, user.first_name, link)


def verify_email(request, uidb64, token):
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
        messages.success(request, "E-mail potwierdzony — dziękujemy! Możesz się teraz zalogować. 🍓")
    else:
        messages.error(request, "Link weryfikacyjny jest nieprawidłowy lub wygasł.")
    return redirect("accounts:account" if request.user.is_authenticated else "accounts:login")


def _subscribe_newsletter(email):
    from core.emails import send_newsletter_welcome
    from core.models import NewsletterSubscriber

    email = (email or "").strip().lower()
    if not email:
        return
    _, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "source": NewsletterSubscriber.SOURCE_FOOTER,
            "consent_text": "Zgoda marketingowa przy koncie Spooky Strawberry.",
        },
    )
    if created:
        send_newsletter_welcome(email)


def _safe_next(request, fallback="accounts:account"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(fallback)


def _auth_context(**extra):
    context = {
        "social_google": social.google_enabled(),
        "social_apple": social.apple_enabled(),
    }
    context.update(extra)
    return context


def auth_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:account")
    return render(
        request,
        "accounts/auth.html",
        _auth_context(
            login_form=EmailLoginForm(request=request),
            register_form=RegistrationForm(),
            next=request.GET.get("next", ""),
        ),
    )


@require_POST
def login_view(request):
    form = EmailLoginForm(request.POST, request=request)
    if form.is_valid():
        user = form.user
        # Konta zakładane e-mailem muszą najpierw potwierdzić adres. Konta social
        # (bez hasła) są już potwierdzone przez dostawcę i nie przechodzą tą bramką.
        profile = getattr(user, "customer_profile", None)
        if user.has_usable_password() and profile is not None and not profile.email_verified:
            send_verification_email(request, user)
            messages.warning(
                request,
                "Twój adres e-mail nie został jeszcze potwierdzony. Wysłaliśmy nowy link "
                "aktywacyjny — sprawdź skrzynkę (także folder spam).",
            )
            return redirect("accounts:login")
        login(request, user)
        messages.success(request, f"Cześć, {user.first_name or 'witaj z powrotem'}! 🍓")
        return redirect(_safe_next(request))
    return render(
        request,
        "accounts/auth.html",
        _auth_context(
            login_form=form,
            register_form=RegistrationForm(),
            next=request.POST.get("next", ""),
            active="login",
        ),
    )


@require_POST
def register_view(request):
    form = RegistrationForm(request.POST)
    if form.is_valid():
        user = form.save()
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        if form.cleaned_data.get("accepts_marketing"):
            profile.accepts_marketing = True
            profile.save(update_fields=["accepts_marketing"])
            _subscribe_newsletter(user.email)
        send_verification_email(request, user)
        messages.success(
            request,
            "Konto założone! 🍓 Wysłaliśmy na Twój e-mail link aktywacyjny — "
            "kliknij go, aby potwierdzić adres, a potem zaloguj się.",
        )
        return redirect("accounts:login")
    return render(
        request,
        "accounts/auth.html",
        _auth_context(
            login_form=EmailLoginForm(request=request),
            register_form=form,
            next=request.POST.get("next", ""),
            active="register",
        ),
    )


# --- Logowanie przez Google / Apple (szczegóły flow: accounts/social.py) ---


def social_start(request, provider):
    if provider == "google" and social.google_enabled():
        authorize_url = social.google_authorize_url
    elif provider == "apple" and social.apple_enabled():
        authorize_url = social.apple_authorize_url
    else:
        messages.error(request, "To logowanie jest chwilowo niedostępne.")
        return redirect("accounts:login")

    state, nonce = social.make_state(request.GET.get("next", ""))
    request.session[social.STATE_SESSION_KEY] = nonce
    response = redirect(authorize_url(request, state))
    # Ciasteczko-kopia nonce'a: callback Apple przychodzi POST-em z innej domeny,
    # więc ciasteczko sesji (SameSite=Lax) nie zostanie wysłane — to musi mieć None.
    response.set_cookie(
        social.STATE_COOKIE,
        nonce,
        max_age=social.STATE_MAX_AGE,
        httponly=True,
        secure=request.is_secure(),
        samesite="None" if request.is_secure() else "Lax",
    )
    return response


def _social_finish(request, provider, data, first_name="", last_name=""):
    if data.get("error") or not data.get("code"):
        messages.info(request, "Logowanie anulowane.")
        return redirect("accounts:login")

    exchange = social.exchange_google_code if provider == "google" else social.exchange_apple_code
    try:
        payload = social.read_state(
            data.get("state", ""),
            [request.session.pop(social.STATE_SESSION_KEY, ""), request.COOKIES.get(social.STATE_COOKIE, "")],
        )
        claims = exchange(request, data["code"])
        user, created = social.get_or_create_user(provider, claims, first_name, last_name)
    except social.SocialAuthError as exc:
        messages.error(request, str(exc))
        return redirect("accounts:login")

    login(request, user)
    if created:
        messages.success(request, "Konto założone! 🍓 Miło Cię widzieć.")
    else:
        messages.success(request, f"Cześć, {user.first_name or 'witaj z powrotem'}! 🍓")

    next_url = payload.get("next", "")
    if not (
        next_url
        and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    ):
        next_url = reverse("accounts:account")
    response = redirect(next_url)
    response.delete_cookie(social.STATE_COOKIE)
    return response


def social_google_callback(request):
    return _social_finish(request, "google", request.GET)


@csrf_exempt
@require_POST
def social_apple_callback(request):
    # Apple przy pierwszym logowaniu dosyła imię/nazwisko osobnym polem `user`
    # (JSON) — tylko ten jeden raz, więc od razu je zapisujemy.
    first_name = last_name = ""
    try:
        name = json.loads(request.POST.get("user", "") or "{}").get("name") or {}
        first_name = name.get("firstName", "") or ""
        last_name = name.get("lastName", "") or ""
    except ValueError:
        pass
    return _social_finish(request, "apple", request.POST, first_name, last_name)


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Wylogowano. Do zobaczenia! 🦇")
    return redirect("core:home")


@login_required
def account_view(request):
    user = request.user
    profile, _ = CustomerProfile.objects.get_or_create(user=user)

    form = PersonalDataForm(
        user=user,
        initial={
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": profile.order_email_or_login,
            "phone": profile.phone,
        },
    )
    consents_form = ConsentsForm(initial={"accepts_marketing": profile.accepts_marketing})
    address = profile.default_shipping_address()
    address_form = AddressForm(instance=address)

    if request.method == "POST":
        form_kind = request.POST.get("form_kind")
        if form_kind == "consents":
            consents_form = ConsentsForm(request.POST)
            if consents_form.is_valid():
                profile.accepts_marketing = consents_form.cleaned_data["accepts_marketing"]
                profile.save(update_fields=["accepts_marketing"])
                if profile.accepts_marketing:
                    _subscribe_newsletter(user.email)
                messages.success(request, "Zapisano zgody.")
                return redirect(reverse("accounts:account") + "#zgody")
        elif form_kind == "address":
            address_form = AddressForm(request.POST, instance=address)
            if address_form.is_valid():
                new_address = address_form.save(commit=False)
                new_address.profile = profile
                new_address.address_type = CustomerAddress.TYPE_SHIPPING
                new_address.is_default = True
                # Imię/nazwisko/telefon do zamówienia bierzemy z danych osobowych konta,
                # więc tu tylko kopiujemy je w tle (adres = ulica/kod/miasto).
                new_address.first_name = user.first_name
                new_address.last_name = user.last_name
                new_address.phone = profile.phone
                new_address.save()
                messages.success(request, "Zapisano adres dostawy.")
                return redirect(reverse("accounts:account") + "#adresy")
        else:
            form = PersonalDataForm(request.POST, user=user)
            if form.is_valid():
                user.first_name = form.cleaned_data["first_name"]
                user.last_name = form.cleaned_data["last_name"]
                user.save(update_fields=["first_name", "last_name"])
                # E-mail z tego formularza to adres do zamówień — adres logowania (user.email) zostaje.
                profile.order_email = form.cleaned_data["email"]
                profile.phone = form.cleaned_data["phone"]
                profile.save(update_fields=["order_email", "phone"])
                messages.success(request, "Zapisano zmiany.")
                return redirect("accounts:account")

    orders = (
        Order.objects.filter(Q(user=user) | Q(email__iexact=user.email))
        .exclude(status=Order.STATUS_DRAFT)
        .select_related("shipping_method")
        .prefetch_related("items__product__images")
        .order_by("-created_at")
    )

    return render(
        request,
        "accounts/account.html",
        {
            "profile": profile,
            "form": form,
            "consents_form": consents_form,
            "address_form": address_form,
            "orders": orders,
        },
    )
