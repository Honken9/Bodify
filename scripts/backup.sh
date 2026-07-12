#!/usr/bin/env bash
# Backup av Bodify: databas (pg_dump) + uppladdade filer (foton).
# Användning: ./scripts/backup.sh [målkatalog]   (default ./backups)
set -euo pipefail

cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=${1:-./backups}
mkdir -p "$OUT"

echo "→ Dumpar databasen…"
docker compose exec -T db pg_dump -U bodify bodify | gzip \
  > "$OUT/bodify-db-$STAMP.sql.gz"

echo "→ Packar datavolymen (foton m.m.)…"
docker compose cp api:/srv/data "$OUT/bodify-data-$STAMP" >/dev/null
tar -czf "$OUT/bodify-data-$STAMP.tar.gz" -C "$OUT" "bodify-data-$STAMP"
rm -rf "$OUT/bodify-data-$STAMP"

echo "✓ Klart:"
echo "  $OUT/bodify-db-$STAMP.sql.gz"
echo "  $OUT/bodify-data-$STAMP.tar.gz"
echo
echo "Återställning: gunzip -c bodify-db-*.sql.gz | docker compose exec -T db psql -U bodify bodify"
