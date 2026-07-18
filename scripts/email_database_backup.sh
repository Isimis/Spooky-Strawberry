#!/usr/bin/env bash
# Wysyła raz dziennie zaszyfrowaną kopię bazy na prywatny adres właściciela.
set -euo pipefail

project_dir="/var/www/spooky-strawberry"
python_bin="${project_dir}/venv/bin/python"
daily_dir="/var/backups/spooky-strawberry/database/daily"
today="$(date +%Y-%m-%d)"

umask 077
command -v openssl >/dev/null

readarray -t backup_settings < <("${python_bin}" - <<'PY'
from dotenv import dotenv_values

settings = dotenv_values("/var/www/spooky-strawberry/.env")
print(settings.get("BACKUP_EMAIL_ENCRYPTION_PASSWORD", ""))
print(settings.get("BACKUP_EMAIL_RECIPIENT", "kontakt@spookystrawberry.pl"))
PY
)

encryption_password="${backup_settings[0]:-}"
recipient="${backup_settings[1]:-kontakt@spookystrawberry.pl}"

if [[ -z "${encryption_password}" ]]; then
    echo "BACKUP_EMAIL_ENCRYPTION_PASSWORD is not configured." >&2
    exit 1
fi

backup_file="$(find "${daily_dir}" -maxdepth 1 -type f -name "spooky_${today}.*" -print -quit)"
if [[ -z "${backup_file}" ]]; then
    echo "Daily database backup for ${today} is missing." >&2
    exit 1
fi

encrypted_file="$(mktemp "/tmp/spooky_database_${today}_XXXXXX.enc")"
cleanup() {
    rm -f "${encrypted_file}"
}
trap cleanup EXIT

printf '%s' "${encryption_password}" | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -in "${backup_file}" \
    -out "${encrypted_file}" \
    -pass stdin

BACKUP_ATTACHMENT="${encrypted_file}" \
BACKUP_RECIPIENT="${recipient}" \
BACKUP_DATE="${today}" \
DJANGO_SETTINGS_MODULE=config.settings \
"${python_bin}" - <<'PY'
import os
from pathlib import Path

import django

django.setup()

from django.conf import settings
from django.core.mail import EmailMessage

attachment = Path(os.environ["BACKUP_ATTACHMENT"])
backup_date = os.environ["BACKUP_DATE"]
message = EmailMessage(
    subject=f"Zaszyfrowany backup bazy danych: {backup_date}",
    body=(
        "W załączniku znajduje się zaszyfrowana kopia bazy danych Spooky Strawberry.\n\n"
        "Do odszyfrowania potrzebne jest osobne hasło backupów.\n"
        "Nie przekazuj załącznika ani hasła innym osobom."
    ),
    from_email=settings.DEFAULT_FROM_EMAIL,
    to=[os.environ["BACKUP_RECIPIENT"]],
)
message.attach(attachment.name, attachment.read_bytes(), "application/octet-stream")
message.send(fail_silently=False)
PY

printf 'Encrypted database backup sent for %s.\n' "${today}"
