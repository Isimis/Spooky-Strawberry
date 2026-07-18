from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import MessageTemplate, SiteSettings
from orders.models import DiscountCode, ShippingMethod


class Command(BaseCommand):
    help = "Ujednolica zapisane w bazie zasady dostawy, newsletter i kod SPOOKY10."

    def handle(self, *args, **options):
        settings_obj = SiteSettings.load()
        settings_obj.announcement_is_active = True
        settings_obj.announcement_text = "Darmowa dostawa od 100 zł 🍓"
        settings_obj.save(update_fields=["announcement_is_active", "announcement_text", "updated_at"])

        paczkomat_count = ShippingMethod.objects.filter(code__in=["paczkomat", "inpost", "paczkomaty"]).update(
            free_from_amount=Decimal("100.00"),
            description="Nadanie do Paczkomatu InPost w ciągu maksymalnie 48 godzin w dni robocze.",
        )
        kurier_count = ShippingMethod.objects.filter(code="kurier").update(
            free_from_amount=Decimal("100.00"),
            description="Nadanie przesyłki kurierskiej w ciągu maksymalnie 48 godzin w dni robocze.",
        )

        code, created = DiscountCode.objects.update_or_create(
            code="SPOOKY10",
            defaults={
                "discount_type": DiscountCode.TYPE_PERCENT,
                "value": Decimal("10.00"),
                "is_active": True,
                "once_per_user": True,
                "first_order_only": True,
            },
        )

        MessageTemplate.objects.filter(system_key="newsletter-welcome").update(
            body_html=(
                "<h1>Witaj w klubie Spooky 🦇</h1>"
                "<p>Dzięki za zapis! Od teraz wcześniej dowiadujesz się o nowościach, restockach i kodach rabatowych.</p>"
                "<p>Oto Twój kod na pierwsze opłacone zakupy: <strong>SPOOKY10</strong>.</p>"
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
                "<li>Odeślij paczkę na adres: <strong>Wizards &amp; Strawberries Patryk Lewandowski, "
                "ul. Mazowiecka 20/68, 05-077 Warszawa, Polska</strong>.</li></ol>"
                "<p>Zwrot płatności wykonamy zgodnie z zasadami opisanymi na stronie Zwroty i reklamacje.</p>"
                "<p>Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤</p>"
            ),
        )

        action = "utworzono" if created else "zaktualizowano"
        self.stdout.write(
            self.style.SUCCESS(
                f"Ujednolicono dane sklepu; {action} kod {code.code}; metody dostawy: {paczkomat_count + kurier_count}."
            )
        )
