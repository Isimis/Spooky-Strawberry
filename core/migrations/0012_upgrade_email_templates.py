from django.db import migrations

# Wspólne style treści (spójne w każdym mailu). Trzymamy je jako stałe i sklejamy
# przez konkatenację, żeby nie kolidowały z placeholderami Django ({{ ... }}).
H1 = ("margin:0 0 14px;font-family:Georgia,'Times New Roman',serif;font-size:23px;"
      "line-height:1.3;color:#1c1620;font-weight:700;")
P = "margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.65;color:#1c1620;"
PM = "margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.6;color:#6c6470;"


def h1(text):
    return '<h1 style="' + H1 + '">' + text + "</h1>"


def p(text):
    return '<p style="' + P + '">' + text + "</p>"


def pm(text):
    return '<p style="' + PM + '">' + text + "</p>"


# Responsywny szablon bazowy (pełny dokument HTML, tabele + inline CSS, media query).
BASE_LAYOUT_BODY = """<!DOCTYPE html>
<html lang="pl" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light">
<title>Spooky Strawberry</title>
<style>
  body{margin:0;padding:0;background:#f4f1ec;}
  a{color:#c2185b;}
  img{border:0;line-height:100%;outline:none;text-decoration:none;}
  table{border-collapse:collapse;}
  @media only screen and (max-width:600px){
    .ss-container{width:100% !important;}
    .ss-px{padding-left:22px !important;padding-right:22px !important;}
    .ss-h1{font-size:21px !important;}
  }
</style>
</head>
<body style="margin:0;padding:0;background:#f4f1ec;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#f4f1ec;">{{ preheader }}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1ec;">
  <tr><td align="center" style="padding:28px 12px;">
    <table role="presentation" width="600" class="ss-container" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:#ffffff;border-radius:18px;overflow:hidden;box-shadow:0 8px 30px rgba(28,22,32,0.10);">
      <tr><td class="ss-px" style="background:#241019;padding:30px 32px;text-align:center;">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:0.5px;">Spooky <span style="color:#ff5fa2;">Strawberry</span> &#127827;</div>
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#b79aa8;margin-top:6px;">akcesoria alternatywne</div>
      </td></tr>
      <tr><td class="ss-px" style="padding:34px 36px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.65;color:#1c1620;">
        {{ content }}
      </td></tr>
      <tr><td class="ss-px" style="background:#faf6f2;padding:26px 36px;text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.7;color:#8a8290;">
        <div style="margin-bottom:8px;">
          <a href="https://spookystrawberry.pl" style="color:#8a8290;text-decoration:none;">Sklep</a> &nbsp;&middot;&nbsp;
          <a href="https://spookystrawberry.pl/status-zamowienia/" style="color:#8a8290;text-decoration:none;">Status zam&oacute;wienia</a> &nbsp;&middot;&nbsp;
          <a href="https://spookystrawberry.pl/kontakt/" style="color:#8a8290;text-decoration:none;">Kontakt</a>
        </div>
        Spooky Strawberry &middot; Wizards &amp; Strawberries<br>
        <a href="mailto:kontakt@spookystrawberry.pl" style="color:#8a8290;">kontakt@spookystrawberry.pl</a> &middot; spookystrawberry.pl<br>
        <span style="color:#b7b0be;">Wys&#322;ano z &#128156; w Polsce</span>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


CODE_BOX = (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 20px;">'
    '<tr><td align="center" style="background:#241019;border-radius:14px;padding:22px;">'
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:2px;'
    'text-transform:uppercase;color:#b79aa8;margin-bottom:8px;">Twój kod</div>'
    '<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:30px;font-weight:700;'
    'letter-spacing:3px;color:#ffffff;">{{ discount_code }}</div>'
    "</td></tr></table>"
)

GREETING = "Cześć{% if first_name %} {{ first_name }}{% endif %}! 🍓"


SYSTEM_TEMPLATES = [
    {
        "system_key": "account-verification",
        "name": "Rejestracja — potwierdzenie e-mail",
        "subject": "Potwierdź swój adres e-mail — Spooky Strawberry 🍓",
        "description": "Wysyłany automatycznie po założeniu konta e-mailem. Pola: {{ first_name }}, {{ link }}.",
        "body_html": (
            h1("Potwierdź swój e-mail")
            + p(GREETING)
            + p("Dzięki za założenie konta w <strong>Spooky Strawberry</strong>. "
                "Kliknij przycisk poniżej, aby potwierdzić adres i aktywować konto — "
                "potem możesz się już zalogować.")
            + "{{ cta }}"
            + "{{ fallback }}"
            + pm("Jeśli to nie Ty zakładałaś konto, po prostu zignoruj tę wiadomość.")
        ),
    },
    {
        "system_key": "password-reset",
        "name": "Reset hasła",
        "subject": "Reset hasła — Spooky Strawberry 🍓",
        "description": "Wysyłany automatycznie po prośbie o reset hasła. Pola: {{ first_name }}, {{ link }}.",
        "body_html": (
            h1("Reset hasła")
            + p(GREETING)
            + p("Otrzymaliśmy prośbę o zmianę hasła do Twojego konta. "
                "Kliknij przycisk, aby ustawić nowe hasło.")
            + "{{ cta }}"
            + "{{ fallback }}"
            + pm("Jeśli to nie Ty prosiłaś o zmianę — zignoruj tę wiadomość, "
                 "Twoje obecne hasło pozostanie bez zmian.")
        ),
    },
    {
        "system_key": "newsletter-welcome",
        "name": "Newsletter — powitanie i kod",
        "subject": "Witaj w klubie Spooky 🦇 — Twój kod -10%",
        "description": "Wysyłany automatycznie po zapisie do newslettera. Pola: {{ discount_code }}.",
        "body_html": (
            h1("Witaj w klubie Spooky 🦇")
            + p("Dzięki za zapis! Od teraz pierwsza dowiadujesz się o dropach, "
                "restockach i kodach rabatowych.")
            + p("Oto Twój kod na pierwsze zakupy:")
            + CODE_BOX
            + p("<strong>-10%</strong> na pierwsze zamówienie.")
            + "{{ cta }}"
        ),
    },
    {
        "system_key": "order-confirmation",
        "name": "Zamówienie — potwierdzenie",
        "subject": "Potwierdzenie zamówienia {{ order_number }} — Spooky Strawberry",
        "description": "Wysyłany automatycznie po opłaceniu zamówienia. Pola: {{ first_name }}, {{ order_number }}, {{ items }}, {{ delivery }}.",
        "body_html": (
            h1("Dziękujemy za zamówienie! 🍓")
            + p("Cześć{% if first_name %} {{ first_name }}{% endif %}, mamy Twoje zamówienie "
                "<strong>{{ order_number }}</strong> i już pakujemy je z sercem.")
            + "{{ items }}"
            + p("<strong>Dostawa:</strong> {{ delivery }}")
            + "{{ cta }}"
            + pm("O wysyłce damy znać osobnym mailem. 🦇")
        ),
    },
    {
        "system_key": "order-shipped",
        "name": "Zamówienie — wysłane",
        "subject": "Twoje zamówienie {{ order_number }} jest w drodze 🦇",
        "description": "Wysyłany automatycznie, gdy zamówienie dostaje status „Wysłane”. Pola: {{ first_name }}, {{ order_number }}, {{ tracking }}.",
        "body_html": (
            h1("Twoja paczka jest w drodze! 🦇")
            + p("Cześć{% if first_name %} {{ first_name }}{% endif %}, dobre wieści — "
                "zamówienie <strong>{{ order_number }}</strong> właśnie do Ciebie jedzie.")
            + "{{ tracking }}"
            + "{{ cta }}"
            + pm("Dziękujemy, że jesteś z nami. 🖤")
        ),
    },
    {
        "system_key": "order-admin-notification",
        "name": "Powiadomienie obsługi — nowe zamówienie",
        "subject": "🛎️ Nowe zamówienie {{ order_number }} — {{ total }}",
        "description": "Wysyłany automatycznie do obsługi (ORDER_NOTIFICATION_EMAIL) po opłaceniu zamówienia.",
        "body_html": (
            h1("Nowe zamówienie {{ order_number }}")
            + p("Wpłynęło nowe, opłacone zamówienie na kwotę <strong>{{ total }}</strong>.")
            + "{{ customer }}"
            + "{{ items }}"
            + p("<strong>Dostawa:</strong> {{ delivery }}")
            + "{{ cta }}"
        ),
    },
    {
        "system_key": "contact-reply",
        "name": "Odpowiedź na wiadomość kontaktową",
        "subject": "Re: Twoja wiadomość do Spooky Strawberry 🍓",
        "description": "Szablon do ręcznej odpowiedzi na wiadomość z formularza kontaktowego. Pole: {{ first_name }}.",
        "body_html": (
            p(GREETING)
            + p("Dzięki za wiadomość! ")
            + p("[Tutaj wpisz odpowiedź]")
            + pm("Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤")
        ),
    },
]


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    MessageTemplate.objects.update_or_create(
        system_key="base-layout",
        defaults={
            "name": "Szablon bazowy maili (wygląd)",
            "subject": "",
            "description": "Wspólny wygląd wszystkich maili — nagłówek, ramka i stopka. "
                           "{{ content }} to miejsce na treść, {{ preheader }} to tekst podglądu.",
            "body_html": BASE_LAYOUT_BODY,
            "is_system": True,
            "is_active": True,
        },
    )
    for data in SYSTEM_TEMPLATES:
        MessageTemplate.objects.update_or_create(
            system_key=data["system_key"],
            defaults={
                "name": data["name"],
                "subject": data["subject"],
                "description": data["description"],
                "body_html": data["body_html"],
                "is_system": True,
                "is_active": True,
            },
        )


def unseed(apps, schema_editor):
    # Wstecz nic nie usuwamy — poprzednie treści zostały nadpisane; brak sensownego rollbacku.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_sitesettings_payments_sandbox"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
