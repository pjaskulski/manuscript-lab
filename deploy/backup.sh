#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTANCE_DIR="${PROJECT_DIR}/instance"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
INCLUDE_UPLOADS="${INCLUDE_UPLOADS:-0}"
INCLUDE_ENV="${INCLUDE_ENV:-0}"
TIMESTAMP="$(date +%F-%H%M%S)"

DB_PATH="${INSTANCE_DIR}/app.db"
ENV_PATH="${PROJECT_DIR}/.env"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
    echo "Brak bazy SQLite: ${DB_PATH}" >&2
    exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "Brak polecenia sqlite3. Zainstaluj pakiet sqlite3." >&2
    exit 1
fi

DB_BACKUP_PATH="${BACKUP_DIR}/app-${TIMESTAMP}.db"

echo "Tworzenie kopii bazy SQLite..."
sqlite3 "${DB_PATH}" ".backup '${DB_BACKUP_PATH}'"

FILES_ARCHIVE_PATH=""

if [[ "${INCLUDE_UPLOADS}" == "1" || "${INCLUDE_ENV}" == "1" ]]; then
    archive_items=()
    if [[ "${INCLUDE_UPLOADS}" == "1" ]]; then
        archive_items+=("instance/uploads")
    fi
    if [[ "${INCLUDE_ENV}" == "1" && -f "${ENV_PATH}" ]]; then
        archive_items+=(".env")
    fi
    if [[ ${#archive_items[@]} -gt 0 ]]; then
        FILES_ARCHIVE_PATH="${BACKUP_DIR}/files-${TIMESTAMP}.tar.gz"
        echo "Pakowanie dodatkowych plikow: ${archive_items[*]}..."
        tar -czf "${FILES_ARCHIVE_PATH}" -C "${PROJECT_DIR}" "${archive_items[@]}"
    fi
else
    echo "Pomijam backup uploadow i .env (domyslnie kopiowana jest tylko baza danych)."
fi

echo "Usuwanie backupow starszych niz ${RETENTION_DAYS} dni..."
find "${BACKUP_DIR}" -maxdepth 1 -type f \( -name "app-*.db" -o -name "files-*.tar.gz" \) -mtime +"${RETENTION_DAYS}" -delete

echo "Backup gotowy:"
echo "  ${DB_BACKUP_PATH}"
if [[ -n "${FILES_ARCHIVE_PATH}" ]]; then
    echo "  ${FILES_ARCHIVE_PATH}"
fi
