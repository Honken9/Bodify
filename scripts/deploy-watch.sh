#!/usr/bin/env bash
# Auto-deploy: kolla om GitHub har nya commits och bygg om vid behov.
# Körs med jämna mellanrum på servern (Macen) via cron — se README.
# Bevakar den branch som är utcheckad, eller DEPLOY_BRANCH om satt.
set -euo pipefail

cd "$(dirname "$0")/.."

BRANCH=${DEPLOY_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}

git fetch origin "$BRANCH" --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0  # inget nytt — tyst
fi

echo "[$(date '+%Y-%m-%d %H:%M')] Ny version på $BRANCH: ${REMOTE:0:9} — deployar…"
git reset --hard "origin/$BRANCH" --quiet
docker compose --profile tunnel up -d --build
echo "[$(date '+%Y-%m-%d %H:%M')] ✓ Deploy klar: ${REMOTE:0:9}"
