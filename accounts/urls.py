from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("konto/", views.account_view, name="account"),
    path("konto/zaloguj/", views.auth_view, name="login"),
    path("konto/zaloguj/wyslij/", views.login_view, name="login_submit"),
    path("konto/rejestracja/", views.register_view, name="register"),
    path("konto/wyloguj/", views.logout_view, name="logout"),
    path("konto/potwierdz/<uidb64>/<token>/", views.verify_email, name="verify_email"),
]
