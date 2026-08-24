#!/usr/bin/env bash
set -euo pipefail

# Overwrites the "cadmus_dev" database with a fresh copy of the production
# "cadmus" database. Both live in the same shared Postgres container (the
# "postgres" service in this repo's compose.yaml; the sibling
# cadmus-dictionary-studio-dev checkout joins it over the external
# "cadmus-dictionary-studio_cadmus" network), so the dump is streamed
# directly between pg_dump and pg_restore inside that container — nothing
# touches host disk and no cross-host transfer is needed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

PROD_DB="${CADMUS_PROD_DATABASE_NAME:-cadmus}"
DEV_DB="${CADMUS_DEV_DATABASE_NAME:-cadmus_dev}"
DB_USER="${CADMUS_DATABASE_USER:-cadmus}"
ASSUME_YES=0

usage() {
  echo "Usage: $0 [-y|--yes]"
  echo
  echo "Dumps the production '$PROD_DB' database and restores it over the"
  echo "'$DEV_DB' database, replacing all data currently in dev."
  echo
  echo "  -y, --yes   Skip the confirmation prompt (for non-interactive use)."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  echo "error: the shared 'postgres' service is not running here (run from the prod repo with the stack up)" >&2
  exit 1
fi

if [[ "$ASSUME_YES" != "1" ]]; then
  cat <<EOF
This will REPLACE all data in '$DEV_DB' with a fresh copy of production data
from '$PROD_DB', including real user accounts and content. This cannot be
undone.
EOF
  if [[ -t 0 ]]; then
    read -r -p "Continue? [y/N] " reply
  elif [[ -r /dev/tty ]]; then
    read -r -p "Continue? [y/N] " reply < /dev/tty
  else
    echo "error: no interactive terminal to confirm on; re-run with -y/--yes to skip the prompt" >&2
    exit 1
  fi
  [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

echo "==> Terminating other connections to '$DEV_DB'..."
echo "    (if this hangs, stop the dev api/worker containers and re-run)"
docker compose exec -T postgres psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DEV_DB' AND pid <> pg_backend_pid();" >/dev/null

echo "==> Dumping '$PROD_DB' and restoring into '$DEV_DB'..."
docker compose exec -T postgres pg_dump -U "$DB_USER" --format=custom "$PROD_DB" \
  | docker compose exec -T postgres pg_restore -U "$DB_USER" -d "$DEV_DB" \
      --clean --if-exists --no-owner --no-privileges --single-transaction

echo "==> Done. '$DEV_DB' now mirrors '$PROD_DB'."
