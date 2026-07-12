from django.core.management.base import BaseCommand

from orders.services import DEFAULT_PENDING_TTL_MINUTES, expire_stale_pending_orders


class Command(BaseCommand):
    help = "Anuluje porzucone, nieopłacone zamówienia (status „Oczekuje na płatność")."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=DEFAULT_PENDING_TTL_MINUTES,
            help="Po ilu minutach uznać nieopłacone zamówienie za porzucone (domyślnie %(default)s).",
        )

    def handle(self, *args, **options):
        count = expire_stale_pending_orders(older_than_minutes=options["minutes"])
        self.stdout.write(self.style.SUCCESS(f"Wygaszono nieopłaconych zamówień: {count}."))
