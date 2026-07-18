from django.db import migrations


def mark_existing_verified(apps, schema_editor):
    """Konta istniejące przed wprowadzeniem twardej weryfikacji e-maila oznaczamy
    jako potwierdzone — inaczej brama logowania zablokowałaby dotychczasowych
    użytkowników, którzy nigdy nie klikali linku aktywacyjnego."""
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    CustomerProfile.objects.filter(email_verified=False).update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_socialidentity"),
    ]

    operations = [
        migrations.RunPython(mark_existing_verified, migrations.RunPython.noop),
    ]
