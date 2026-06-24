from django.db import migrations


SYSTEM_TEMPLATES = [
    {
        "system_key": "account-verification",
        "name": "Rejestracja — potwierdzenie e-mail",
        "subject": "Potwierdź swój adres e-mail — Spooky Strawberry 🍓",
        "description": "Wysyłany po założeniu konta przy użyciu adresu e-mail.",
        "body_html": (
            "<p>Cześć!</p>"
            "<p>Dzięki za założenie konta w <strong>Spooky Strawberry</strong>. "
            "Potwierdź swój adres e-mail, klikając w przycisk poniżej.</p>"
            "<p><a href=\"{{ link }}\">Potwierdzam adres</a></p>"
            "<p>Jeśli to nie Ty zakładałaś konto, zignoruj tę wiadomość.</p>"
        ),
    },
    {
        "system_key": "newsletter-welcome",
        "name": "Newsletter — powitanie i kod",
        "subject": "Witaj w klubie Spooky 🍓 — Twój kod -10%",
        "description": "Wysyłany po zapisaniu adresu do newslettera.",
        "body_html": (
            "<p>Witaj w klubie Spooky! 🦇</p>"
            "<p>Dziękujemy za zapis. Oto Twój kod na pierwsze zakupy:</p>"
            "<p><strong>SPOOKY10</strong> — -10% na pierwsze zamówienie.</p>"
        ),
    },
    {
        "system_key": "order-confirmation",
        "name": "Zamówienie — potwierdzenie",
        "subject": "Potwierdzenie zamówienia {{ order_number }} — Spooky Strawberry",
        "description": "Wysyłany po złożeniu zamówienia.",
        "body_html": (
            "<p>Dziękujemy za zamówienie! 🍓</p>"
            "<p>Numer zamówienia: <strong>{{ order_number }}</strong>.</p>"
            "<p>Pakujemy z sercem i wyślemy w 24h. O wysyłce damy znać osobnym mailem.</p>"
        ),
    },
    {
        "system_key": "order-shipped",
        "name": "Zamówienie — wysłane",
        "subject": "Twoje zamówienie {{ order_number }} jest w drodze 🦇",
        "description": "Wysyłany, gdy zamówienie zostaje nadane.",
        "body_html": (
            "<p>Dobre wieści — Twoje zamówienie <strong>{{ order_number }}</strong> jest w drodze!</p>"
            "<p>Numer przesyłki: {{ tracking_number }}.</p>"
        ),
    },
    {
        "system_key": "password-reset",
        "name": "Reset hasła",
        "subject": "Reset hasła — Spooky Strawberry",
        "description": "Wysyłany po prośbie o zresetowanie hasła.",
        "body_html": (
            "<p>Otrzymaliśmy prośbę o zmianę hasła do Twojego konta.</p>"
            "<p><a href=\"{{ link }}\">Ustaw nowe hasło</a></p>"
            "<p>Jeśli to nie Ty, zignoruj tę wiadomość — hasło pozostanie bez zmian.</p>"
        ),
    },
    {
        "system_key": "contact-reply",
        "name": "Odpowiedź na wiadomość kontaktową",
        "subject": "Re: Twoja wiadomość do Spooky Strawberry",
        "description": "Szablon ręcznej odpowiedzi na wiadomość z formularza kontaktowego.",
        "body_html": (
            "<p>Cześć!</p>"
            "<p>Dzięki za wiadomość. {{ reply }}</p>"
            "<p>Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤</p>"
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
                "is_system": True,
                "is_active": True,
            },
        )


def unseed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    MessageTemplate.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_messagetemplate_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
