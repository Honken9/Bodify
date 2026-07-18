#!/usr/bin/env bash
# Auto-deploy: kolla om GitHub har nya commits och bygg om vid behov.
# Körs med jämna mellanrum på servern (Macen) via cron — se README.
# Bevakar den branch som är utcheckad, eller DEPLOY_BRANCH om satt.
set -euo pipefail

# cron kör med minimal PATH — docker och git ligger i /usr/local/bin
# (Docker Desktop) resp. /opt/homebrew/bin på Apple Silicon.
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

cd "$(dirname "$0")/.."

BRANCH=${DEPLOY_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}

git fetch origin "$BRANCH" --quiet

REMOTE=$(git rev-parse "origin/$BRANCH")

# Jämför mot senast LYCKADE deploy — inte mot git HEAD. Annars: om bygget
# kraschar efter git reset ser nästa körning "inget nytt" och ger upp,
# och servern blir stående på gammal kod fast repot är uppdaterat.
MARKER=.git/shapiqo-deployed-rev
DEPLOYED=$(cat "$MARKER" 2>/dev/null || echo "")

if [ "$REMOTE" = "$DEPLOYED" ]; then
  exit 0  # inget nytt — tyst
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Ny version på $BRANCH: ${REMOTE:0:9} — deployar…"
git reset --hard "origin/$BRANCH" --quiet
docker compose --profile tunnel up -d --build
echo "$REMOTE" > "$MARKER"
echo "[$(date '+%Y-%m-%d %H:%M')] ✓ Deploy klar: ${REMOTE:0:9}"
