from decimal import Decimal

from django.db import migrations


ANNOUNCEMENT = "🦇 Darmowa dostawa od 100 zł · 14 dni na zwrot"
RETURN_ADDRESS = "ul. Mazowiecka 20/68, 05-077 Warszawa, Polska"


def apply_store_information(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    DiscountCode = apps.get_model("orders", "DiscountCode")

    SiteSettings.objects.update_or_create(
        pk=1,
        defaults={"announcement_is_active": True, "announcement_text": ANNOUNCEMENT},
    )

    ShippingMethod.objects.filter(code__in=["paczkomat", "inpost", "paczkomaty"]).update(
        free_from_amount=Decimal("100.00"),
        description="Nadanie do Paczkomatu InPost w ciągu maksymalnie 48 godzin w dni robocze.",
    )
    ShippingMethod.objects.filter(code="kurier").update(
        free_from_amount=Decimal("100.00"),
        description="Nadanie przesyłki kurierskiej w ciągu maksymalnie 48 godzin w dni robocze.",
    )

    # Nie tworzymy kodu w migracji: migracje są uruchamiane również na pustej
    # bazie testowej. Produkcyjny kod zapewnia polecenie sync_store_information.
    DiscountCode.objects.filter(code="SPOOKY10").update(
        discount_type="percent",
        value=Decimal("10.00"),
        is_active=True,
        once_per_user=True,
        first_order_only=True,
    )

    MessageTemplate.objects.filter(system_key="newsletter-welcome").update(
        subject="Witaj w klubie Spooky 🦇 Twój kod -10%",
        body_html=(
            "<h1>Witaj w klubie Spooky 🦇</h1>"
            "<p>Dzięki za zapis! Od teraz wcześniej dowiadujesz się o nowościach, restockach i kodach rabatowych.</p>"
            "<p>Oto Twój kod na pierwsze opłacone zakupy:</p>"
            "<p><strong>SPOOKY10</strong></p>"
            "<p><strong>-10%</strong> na pierwsze opłacone zamówienie.</p>"
            '<p><a href="https://spookystrawberry.pl/sklep/">Zacznij zakupy</a></p>'
        ),
    )
    MessageTemplate.objects.filter(system_key="reply-return-howto").update(
        body_html=(
            "<p>Cześć{% if first_name %} {{ first_name }}{% endif %}! 🍓</p>"
            "<p>Masz 14 dni od otrzymania paczki na złożenie oświadczenia o odstąpieniu od umowy. "
            "Po jego wysłaniu masz kolejne 14 dni na odesłanie produktu.</p>"
            "<ol><li>Zapakuj produkt(y) i dołącz numer zamówienia: <strong>[NUMER ZAMÓWIENIA]</strong>.</li>"
            f"<li>Odeślij paczkę na adres: <strong>Wizards &amp; Strawberries Patryk Lewandowski, {RETURN_ADDRESS}</strong>.</li></ol>"
            "<p>Zwrot płatności wykonamy zgodnie z zasadami opisanymi na stronie Zwroty i reklamacje.</p>"
            "<p>Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤</p>"
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_simplify_admin_shipped_templates"),
        ("orders", "0013_discountcode_first_order_only"),
    ]

    operations = [
        migrations.RunPython(apply_store_information, migrations.RunPython.noop),
    ]
