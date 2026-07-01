from django.core.management.base import BaseCommand, CommandError

from core.mailbox import MailboxConfigurationError, sync_mailbox


class Command(BaseCommand):
    help = "Synchronizuje wiadomości przychodzące z IMAP do panelowej skrzynki."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Maksymalna liczba najnowszych wiadomości do sprawdzenia.")

    def handle(self, *args, **options):
        try:
            imported = sync_mailbox(limit=options["limit"])
        except MailboxConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Nie udało się zsynchronizować skrzynki: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Pobrano {len(imported)} nowych wiadomości."))
