#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "Defina DATABASE_URL para aplicar as migrações." >&2
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for migration in "$ROOT_DIR"/db/migrations/*.sql; do
    [[ -f "$migration" ]] || continue
    psql "$DATABASE_URL" --set ON_ERROR_STOP=1 --file "$migration"
done
