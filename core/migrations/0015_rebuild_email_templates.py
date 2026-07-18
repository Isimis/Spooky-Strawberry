from django.db import migrations

# Przebudowa szablonów maili "z głową":
# - CAŁA treść (teksty, przyciski, kod rabatowy) jest wpisana wprost w szablonie
#   i widoczna/edytowalna w panelu - nic nie jest doklejane z kodu w tajemnicy.
# - Placeholdery zostają tylko dla danych zmiennych per wysyłka (imię, numer
#   zamówienia, lista produktów, adres, linki z tokenami).
# - "Odpowiedź na wiadomość kontaktową" przestaje być systemowa - to szablon do
#   RĘCZNYCH odpowiedzi ze Skrzynki, stąd miejsce "[Tutaj wpisz odpowiedź]".

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


def button(url, label):
    """Przycisk "bulletproof" (tabela + inline CSS) - działa też w Outlooku.
    Wpisany wprost w treść szablonu, więc etykietę można edytować w panelu."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0;">'
        '<tr><td align="center" bgcolor="#c2185b" style="border-radius:999px;">'
        '<a href="' + url + '" style="display:inline-block;padding:14px 32px;'
        "font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;"
        'color:#ffffff;text-decoration:none;border-radius:999px;">' + label + "</a>"
        "</td></tr></table>"
    )


def fallback(url):
    return (
        '<p style="margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        'line-height:1.6;color:#6c6470;">Gdyby przycisk nie działał, skopiuj ten link do przeglądarki:<br>'
        '<a href="' + url + '" style="color:#c2185b;word-break:break-all;">' + url + "</a></p>"
    )


GREETING = "Cześć{% if first_name %} {{ first_name }}{% endif %}! 🍓"

# Kod rabatowy wpisany WPROST (bez placeholdera) - zmieniasz go po prostu w treści.
CODE_BOX = (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 20px;">'
    '<tr><td align="center" style="background:#241019;border-radius:14px;padding:22px;">'
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:2px;'
    'text-transform:uppercase;color:#b79aa8;margin-bottom:8px;">Twój kod</div>'
    "<div style=\"font-family:Georgia,'Times New Roman',serif;font-size:30px;font-weight:700;"
    'letter-spacing:3px;color:#ffffff;">SPOOKY10</div>'
    "</td></tr></table>"
)

INFO_BOX_OPEN = (
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0 18px;">'
    '<tr><td style="background:#faf3f7;border-radius:12px;padding:16px 18px;'
    'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.55;color:#1c1620;">'
)
INFO_BOX_CLOSE = "</td></tr></table>"


SYSTEM_TEMPLATES = [
    {
        "system_key": "account-verification",
        "name": "Rejestracja - potwierdzenie e-mail",
        "subject": "Potwierdź swój adres e-mail - Spooky Strawberry 🍓",
        "description": "Wysyłany automatycznie po założeniu konta e-mailem.",
        "is_system": True,
        "body_html": (
            h1("Potwierdź swój e-mail")
            + p(GREETING)
            + p("Dzięki za założenie konta w <strong>Spooky Strawberry</strong>. "
                "Kliknij przycisk poniżej, aby potwierdzić adres i aktywować konto. "
                "Po potwierdzeniu możesz się już logować.")
            + button("{{ link }}", "Potwierdź adres e-mail")
            + fallback("{{ link }}")
            + pm("Jeśli to nie Ty zakładasz konto, po prostu zignoruj tę wiadomość.")
        ),
    },
    {
        "system_key": "password-reset",
        "name": "Reset hasła",
        "subject": "Reset hasła - Spooky Strawberry 🍓",
        "description": "Wysyłany automatycznie po prośbie o reset hasła.",
        "is_system": True,
        "body_html": (
            h1("Reset hasła")
            + p(GREETING)
            + p("Dostaliśmy prośbę o zmianę hasła do Twojego konta. "
                "Kliknij przycisk, aby ustawić nowe hasło.")
            + button("{{ link }}", "Ustaw nowe hasło")
            + fallback("{{ link }}")
            + pm("Jeśli to nie Ty prosisz o zmianę, zignoruj tę wiadomość. "
                 "Twoje obecne hasło pozostanie bez zmian.")
        ),
    },
    {
        "system_key": "newsletter-welcome",
        "name": "Newsletter - powitanie i kod",
        "subject": "Witaj w klubie Spooky 🦇 Twój kod -10%",
        "description": "Wysyłany automatycznie po zapisie do newslettera. Cała treść (kod i przycisk) jest stała - edytujesz ją wprost tutaj.",
        "is_system": True,
        "body_html": (
            h1("Witaj w klubie Spooky 🦇")
            + p("Dzięki za zapis! Od teraz wcześniej dowiadujesz się o nowościach, "
                "restockach i kodach rabatowych.")
            + p("Oto Twój kod na pierwsze zakupy:")
            + CODE_BOX
            + p("<strong>-10%</strong> na pierwsze zamówienie.")
            + button("https://spookystrawberry.pl/sklep/", "Zacznij zakupy")
        ),
    },
    {
        "system_key": "order-confirmation",
        "name": "Zamówienie - potwierdzenie",
        "subject": "Potwierdzenie zamówienia {{ order_number }} - Spooky Strawberry",
        "description": "Wysyłany automatycznie po opłaceniu zamówienia.",
        "is_system": True,
        "body_html": (
            h1("Dziękujemy za zamówienie! 🍓")
            + p("Cześć{% if first_name %} {{ first_name }}{% endif %}, mamy Twoje zamówienie "
                "<strong>{{ order_number }}</strong> i pakujemy je z sercem.")
            + "{{ items }}"
            + p("<strong>Dostawa:</strong> {{ delivery }}")
            + button("{{ status_url }}", "Śledź zamówienie")
            + pm("O wysyłce damy znać osobnym mailem. 🦇")
        ),
    },
    {
        "system_key": "order-shipped",
        "name": "Zamówienie - wysłane",
        "subject": "Twoje zamówienie {{ order_number }} jest w drodze 🦇",
        "description": "Wysyłany automatycznie, gdy zamówienie dostaje status „Wysłane”.",
        "is_system": True,
        "body_html": (
            h1("Twoja paczka jest w drodze! 🦇")
            + p("Cześć{% if first_name %} {{ first_name }}{% endif %}, dobre wieści: "
                "zamówienie <strong>{{ order_number }}</strong> jedzie już do Ciebie.")
            + "{% if tracking_number %}"
            + INFO_BOX_OPEN
            + '<span style="color:#6c6470;">Numer przesyłki:</span> <strong>{{ tracking_number }}</strong>'
            + INFO_BOX_CLOSE
            + "{% if tracking_url %}"
            + button("{{ tracking_url }}", "Śledź przesyłkę")
            + "{% endif %}{% endif %}"
            + button("{{ status_url }}", "Zobacz status zamówienia")
            + pm("Dziękujemy, że jesteś z nami. 🖤")
        ),
    },
    {
        "system_key": "order-admin-notification",
        "name": "Powiadomienie obsługi - nowe zamówienie",
        "subject": "🛎️ Nowe zamówienie {{ order_number }} na {{ total }}",
        "description": "Wysyłany automatycznie do obsługi (adres z ORDER_NOTIFICATION_EMAIL) po opłaceniu zamówienia.",
        "is_system": True,
        "body_html": (
            h1("Nowe zamówienie {{ order_number }}")
            + p("Wpłynęło nowe, opłacone zamówienie na kwotę <strong>{{ total }}</strong>.")
            + INFO_BOX_OPEN
            + '<div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6c6470;margin-bottom:8px;">Dane klienta</div>'
            + '<div style="margin:3px 0;"><span style="color:#6c6470;">Klient:</span> {{ customer_name }}</div>'
            + '<div style="margin:3px 0;"><span style="color:#6c6470;">E-mail:</span> {{ customer_email }}</div>'
            + "{% if customer_phone %}"
            + '<div style="margin:3px 0;"><span style="color:#6c6470;">Telefon:</span> {{ customer_phone }}</div>'
            + "{% endif %}"
            + INFO_BOX_CLOSE
            + "{{ items }}"
            + p("<strong>Dostawa:</strong> {{ delivery }}")
            + button("{{ panel_url }}", "Otwórz w panelu")
        ),
    },
    {
        # Szablon do RĘCZNEGO użycia w Skrzynce (Napisz wiadomość / odpowiedź) -
        # nie jest wysyłany automatycznie, dlatego przestaje być "systemowy".
        "system_key": "contact-reply",
        "name": "Odpowiedź na wiadomość kontaktową",
        "subject": "Re: Twoja wiadomość do Spooky Strawberry 🍓",
        "description": "Gotowiec do ręcznej odpowiedzi ze Skrzynki. Wybierz go przy pisaniu wiadomości i uzupełnij treść w miejscu [Tutaj wpisz odpowiedź].",
        "is_system": False,
        "body_html": (
            p(GREETING)
            + p("Dzięki za wiadomość!")
            + p("[Tutaj wpisz odpowiedź]")
            + pm("Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤")
        ),
    },
]


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    for data in SYSTEM_TEMPLATES:
        MessageTemplate.objects.update_or_create(
            system_key=data["system_key"],
            defaults={
                "name": data["name"],
                "subject": data["subject"],
                "description": data["description"],
                "body_html": data["body_html"],
                "is_system": data["is_system"],
                "is_active": True,
            },
        )


def unseed(apps, schema_editor):
    # Poprzednie wersje treści zostały nadpisane - brak sensownego rollbacku.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_cleanup_email_text"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
