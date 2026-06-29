from django.db import migrations


BASE_LAYOUT = {
    "system_key": "base-layout",
    "name": "Szablon bazowy maili (wzór)",
    "subject": "",
    "description": "Wspólny wygląd wszystkich maili — nagłówek, ramka i stopka. {{ content }} to miejsce na treść.",
    "body_html": (
        '<div style="margin:0;padding:24px 0;background:#f4f1ec;font-family:Arial,Helvetica,sans-serif;color:#1c1620;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="width:600px;max-width:600px;border-collapse:collapse;background:#ffffff;border-radius:16px;overflow:hidden;'
        'box-shadow:0 6px 24px rgba(28,22,32,0.08);">'
        # Nagłówek z logo / nazwą marki
        '<tr><td style="background:#1c1620;padding:28px 32px;text-align:center;">'
        '<span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:0.04em;">Spooky Strawberry 🍓</span>'
        '</td></tr>'
        # Treść maila
        '<tr><td style="padding:32px;font-size:15px;line-height:1.6;color:#1c1620;">'
        "{{ content }}"
        '</td></tr>'
        # Stopka
        '<tr><td style="background:#f4f1ec;padding:24px 32px;text-align:center;font-size:12px;line-height:1.6;color:#6c6470;">'
        'Spooky Strawberry · Wysłano z miłością 🖤<br>'
        'kontakt@spookystrawberry.pl · <a href="https://spookystrawberry.pl" style="color:#6c6470;">spookystrawberry.pl</a>'
        '</td></tr>'
        '</table>'
        '</td></tr>'
        '</table>'
        '</div>'
    ),
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    MessageTemplate.objects.update_or_create(
        system_key=BASE_LAYOUT["system_key"],
        defaults={
            "name": BASE_LAYOUT["name"],
            "subject": BASE_LAYOUT["subject"],
            "description": BASE_LAYOUT["description"],
            "body_html": BASE_LAYOUT["body_html"],
            "is_system": True,
            "is_active": True,
        },
    )


def unseed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    MessageTemplate.objects.filter(system_key=BASE_LAYOUT["system_key"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_seed_system_email_templates"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
