from django.db import migrations

# Zamiany w treści istniejących szablonów maili (żywa baza): długie myślniki na krótki,
# formy żeńskie na neutralne, słowo „drop” na „nowości”.
BODY_REPLACEMENTS = [
    ("nie Ty zakładałaś konto", "nie Ty zakładasz konto"),
    ("nie Ty prosiłaś o zmianę", "nie Ty prosisz o zmianę"),
    ("Od teraz pierwsza dowiadujesz się o dropach", "Od teraz wcześniej dowiadujesz się o nowościach"),
    ("że dałaś nam znać", "że dajesz nam znać"),
    ("o dropach i restockach", "o nowościach i restockach"),
    ("o dropach", "o nowościach"),
    ("dropy", "nowości"),
]


def _clean(text):
    if not text:
        return text
    text = text.replace("—", "-").replace("–", "-")
    for old, new in BODY_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def cleanup(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    for tpl in MessageTemplate.objects.all():
        name = _clean(tpl.name)
        subject = _clean(tpl.subject)
        body = _clean(tpl.body_html)
        description = _clean(tpl.description)
        if (name, subject, body, description) != (tpl.name, tpl.subject, tpl.body_html, tpl.description):
            tpl.name = name
            tpl.subject = subject
            tpl.body_html = body
            tpl.description = description
            tpl.save(update_fields=["name", "subject", "body_html", "description"])

    SiteSettings = apps.get_model("core", "SiteSettings")
    for settings_obj in SiteSettings.objects.all():
        changed = []
        if settings_obj.drop_eyebrow in ("Najnowszy drop", ""):
            settings_obj.drop_eyebrow = "Nowości"
            changed.append("drop_eyebrow")
        if settings_obj.drop_heading in ("Najnowszy drop", ""):
            settings_obj.drop_heading = "Nowości"
            changed.append("drop_heading")
        if changed:
            settings_obj.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_alter_sitesettings_drop_eyebrow_and_more"),
    ]

    operations = [
        migrations.RunPython(cleanup, migrations.RunPython.noop),
    ]
