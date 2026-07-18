from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.urls import reverse

from .models import CustomerAddress

User = get_user_model()


class SpookyPasswordResetForm(PasswordResetForm):
    """Reset hasła wysyłany przez panelowy mailer — mail ląduje w skrzynce panelu
    i (na produkcji) w folderze „Sent" IMAP, więc jest widoczny i tu, i w webmailu."""

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        from core.mailer import send_message

        reset_url = "{protocol}://{domain}{path}".format(
            protocol=context.get("protocol", "https"),
            domain=context.get("domain", ""),
            path=reverse(
                "accounts:password_reset_confirm",
                kwargs={"uidb64": context["uid"], "token": context["token"]},
            ),
        )
        user = context.get("user")
        greeting = f" {user.first_name}" if user and user.first_name else ""
        body_html = (
            f"<p>Cześć{greeting}!</p>"
            "<p>Otrzymujesz tę wiadomość, bo poproszono o reset hasła do konta w "
            "Spooky Strawberry. Ustaw nowe hasło, klikając w przycisk:</p>"
            f'<p style="margin:24px 0"><a href="{reset_url}" '
            'style="display:inline-block;background:#c2185b;color:#fff;text-decoration:none;'
            'padding:12px 22px;border-radius:999px;font-weight:600">Ustaw nowe hasło →</a></p>'
            f'<p style="font-size:12px;color:#777">Gdyby przycisk nie działał, skopiuj ten link '
            f'do przeglądarki:<br><a href="{reset_url}" style="color:#c2185b">{reset_url}</a></p>'
            "<p>Jeśli to nie Ty prosiłaś o zmianę hasła, zignoruj tę wiadomość — "
            "Twoje obecne hasło pozostanie bez zmian.</p>"
        )
        send_message(
            subject="Reset hasła — Spooky Strawberry 🍓",
            body_html=body_html,
            to_email=to_email,
            fail_silently=False,
        )


class RegistrationForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(min_length=8)
    accepts_marketing = forms.BooleanField(required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Konto z tym adresem e-mail już istnieje. Zaloguj się.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password"],
        )
        return user


class EmailLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField()

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        password = cleaned.get("password")
        if email and password:
            user = authenticate(self.request, username=email, password=password)
            if user is None:
                # Fall back to resolving the username from a matching e-mail.
                match = User.objects.filter(email__iexact=email).first()
                if match is not None:
                    user = authenticate(self.request, username=match.get_username(), password=password)
            if user is None:
                raise forms.ValidationError("Nieprawidłowy e-mail lub hasło.")
            if not user.is_active:
                raise forms.ValidationError("To konto jest nieaktywne.")
            self.user = user
        return cleaned


class PersonalDataForm(forms.Form):
    first_name = forms.CharField(max_length=80, required=False)
    last_name = forms.CharField(max_length=80, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.user is not None:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("Ten adres e-mail jest już używany przez inne konto.")
        return email


class ConsentsForm(forms.Form):
    accepts_marketing = forms.BooleanField(required=False)


class AddressForm(forms.ModelForm):
    """Jeden domyślny adres dostawy klienta — edytowalny z poziomu konta."""

    class Meta:
        model = CustomerAddress
        fields = [
            "address_line_1",
            "address_line_2",
            "postal_code",
            "city",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "input")
            if name == "address_line_2":
                field.required = False
