from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from orders.models import Order

from .forms import EmailLoginForm, PersonalDataForm, RegistrationForm
from .models import CustomerProfile

User = get_user_model()


def send_verification_email(request, user):
    """Wysyła link weryfikacyjny e-mail (w dev trafia na konsolę)."""
    if not user.email:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(reverse("accounts:verify_email", args=[uid, token]))
    send_mail(
        "Potwierdź swój adres e-mail — Spooky Strawberry 🍓",
        (
            f"Cześć{(' ' + user.first_name) if user.first_name else ''}!\n\n"
            "Dzięki za założenie konta w Spooky Strawberry. "
            "Potwierdź swój adres e-mail, klikając w link:\n\n"
            f"{link}\n\n"
            "Jeśli to nie Ty zakładałaś konto, zignoruj tę wiadomość.\n\n"
            "🦇 Spooky Strawberry"
        ),
        None,
        [user.email],
        fail_silently=True,
    )


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
        messages.success(request, "E-mail potwierdzony — dziękujemy! 🍓")
    else:
        messages.error(request, "Link weryfikacyjny jest nieprawidłowy lub wygasł.")
    return redirect("accounts:account" if request.user.is_authenticated else "core:home")


def _subscribe_newsletter(email):
    from core.models import NewsletterSubscriber

    email = (email or "").strip().lower()
    if not email:
        return
    NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "source": NewsletterSubscriber.SOURCE_FOOTER,
            "consent_text": "Zgoda marketingowa przy koncie Spooky Strawberry.",
        },
    )


def _safe_next(request, fallback="accounts:account"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(fallback)


def auth_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:account")
    return render(
        request,
        "accounts/auth.html",
        {
            "login_form": EmailLoginForm(request=request),
            "register_form": RegistrationForm(),
            "next": request.GET.get("next", ""),
        },
    )


@require_POST
def login_view(request):
    form = EmailLoginForm(request.POST, request=request)
    if form.is_valid():
        login(request, form.user)
        messages.success(request, f"Cześć, {form.user.first_name or 'witaj z powrotem'}! 🍓")
        return redirect(_safe_next(request))
    return render(
        request,
        "accounts/auth.html",
        {
            "login_form": form,
            "register_form": RegistrationForm(),
            "next": request.POST.get("next", ""),
            "active": "login",
        },
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
        login(request, user)
        send_verification_email(request, user)
        messages.success(request, "Konto założone! 🍓 Wysłaliśmy e-mail z linkiem potwierdzającym adres.")
        return redirect(_safe_next(request))
    return render(
        request,
        "accounts/auth.html",
        {
            "login_form": EmailLoginForm(request=request),
            "register_form": form,
            "next": request.POST.get("next", ""),
            "active": "register",
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Wylogowano. Do zobaczenia! 🦇")
    return redirect("core:home")


@login_required
def account_view(request):
    user = request.user
    profile, _ = CustomerProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        form = PersonalDataForm(request.POST, user=user)
        if form.is_valid():
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.email = form.cleaned_data["email"]
            user.save(update_fields=["first_name", "last_name", "email"])
            profile.accepts_marketing = form.cleaned_data["accepts_marketing"]
            profile.save(update_fields=["accepts_marketing"])
            if form.cleaned_data["accepts_marketing"]:
                _subscribe_newsletter(user.email)
            messages.success(request, "Zapisano zmiany.")
            return redirect("accounts:account")
    else:
        form = PersonalDataForm(
            user=user,
            initial={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "accepts_marketing": profile.accepts_marketing,
            },
        )

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
            "orders": orders,
            "addresses": profile.addresses.all(),
        },
    )
