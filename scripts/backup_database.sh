#!/usr/bin/env bash
# Tworzy kopie bazy produkcyjnej bez zapisywania sekretów w repozytorium.
set -euo pipefail

project_dir="/var/www/spooky-strawberry"
python_bin="${project_dir}/venv/bin/python"
backup_root="/var/backups/spooky-strawberry/database"
hourly_dir="${backup_root}/hourly"
daily_dir="${backup_root}/daily"
timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
today="$(date +%Y-%m-%d)"

umask 077
mkdir -p "${hourly_dir}" "${daily_dir}"

# Plik .env może zawierać znaki poprawne dla python-dotenv, ale nie dla Bash.
# Czytamy wyłącznie adres bazy przez ten sam parser, bez logowania sekretu.
database_url="$("${python_bin}" - <<'PY'
from dotenv import dotenv_values

print(dotenv_values("/var/www/spooky-strawberry/.env").get("DATABASE_URL", ""))
PY
)"

if [[ "${database_url}" == postgres://* || "${database_url}" == postgresql://* ]]; then
    command -v pg_dump >/dev/null
    backup_file="${hourly_dir}/spooky_${timestamp}.dump"
    temporary_file="${backup_file}.tmp"
    pg_dump --format=custom --no-owner --no-acl --file="${temporary_file}" "${database_url}"
    mv "${temporary_file}" "${backup_file}"
else
    backup_file="${hourly_dir}/spooky_${timestamp}.sqlite3"
    temporary_file="${backup_file}.tmp"
    DJANGO_SETTINGS_MODULE=config.settings "${python_bin}" - "${temporary_file}" <<'PY'
import sqlite3
import sys

import django

django.setup()

from django.conf import settings

database_name = settings.DATABASES["default"]["NAME"]
source = sqlite3.connect(database_name)
target = sqlite3.connect(sys.argv[1])
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY
    mv "${temporary_file}" "${backup_file}"
fi

# Zachowujemy gęste kopie na ostatnie 3 dni i po jednej kopii dziennej przez 30 dni.
daily_file="${daily_dir}/spooky_${today}.${backup_file##*.}"
if [[ ! -e "${daily_file}" ]]; then
    cp --reflink=auto "${backup_file}" "${daily_file}"
fi
find "${hourly_dir}" -type f -mtime +3 -delete
find "${daily_dir}" -type f -mtime +30 -delete

printf 'Database backup created: %s\n' "${backup_file}"
