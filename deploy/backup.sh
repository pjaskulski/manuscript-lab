#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTANCE_DIR="${PROJECT_DIR}/instance"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
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
FILES_ARCHIVE_PATH="${BACKUP_DIR}/files-${TIMESTAMP}.tar.gz"

echo "Tworzenie kopii bazy SQLite..."
sqlite3 "${DB_PATH}" ".backup '${DB_BACKUP_PATH}'"

echo "Pakowanie uploadow i konfiguracji..."
if [[ -f "${ENV_PATH}" ]]; then
    tar -czf "${FILES_ARCHIVE_PATH}" -C "${PROJECT_DIR}" instance/uploads .env
else
    tar -czf "${FILES_ARCHIVE_PATH}" -C "${PROJECT_DIR}" instance/uploads
fi

echo "Usuwanie backupow starszych niz ${RETENTION_DAYS} dni..."
find "${BACKUP_DIR}" -maxdepth 1 -type f \( -name "app-*.db" -o -name "files-*.tar.gz" \) -mtime +"${RETENTION_DAYS}" -delete

echo "Backup gotowy:"
echo "  ${DB_BACKUP_PATH}"
echo "  ${FILES_ARCHIVE_PATH}"
