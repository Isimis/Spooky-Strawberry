from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import SpookyPasswordResetForm

app_name = "accounts"

urlpatterns = [
    path("konto/", views.account_view, name="account"),
    path("konto/zaloguj/", views.auth_view, name="login"),
    path("konto/zaloguj/wyslij/", views.login_view, name="login_submit"),
    path("konto/rejestracja/", views.register_view, name="register"),
    path("konto/wyloguj/", views.logout_view, name="logout"),
    path("konto/social/<slug:provider>/start/", views.social_start, name="social_start"),
    path("konto/social/google/callback/", views.social_google_callback, name="social_google_callback"),
    path("konto/social/apple/callback/", views.social_apple_callback, name="social_apple_callback"),
    path("konto/potwierdz/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    # Reset hasła - wbudowane widoki Django z naszymi szablonami i treścią maila.
    path(
        "konto/reset-hasla/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            form_class=SpookyPasswordResetForm,
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "konto/reset-hasla/wyslany/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "konto/reset-hasla/ustaw/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "konto/reset-hasla/gotowe/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
