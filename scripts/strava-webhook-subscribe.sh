#!/usr/bin/env bash
# Engångsregistrering av Stravas webhook-prenumeration (en per app).
# Kräver att .env är ifylld och att appen är nåbar via PUBLIC_BASE_URL.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env; set +a

echo "→ Registrerar webhook mot Strava…"
curl -sS -X POST "https://www.strava.com/api/v3/push_subscriptions" \
  -F client_id="$STRAVA_CLIENT_ID" \
  -F client_secret="$STRAVA_CLIENT_SECRET" \
  -F callback_url="$PUBLIC_BASE_URL/api/webhooks/strava" \
  -F verify_token="${STRAVA_VERIFY_TOKEN:-bodify-strava}"
echo
echo "✓ Klart — Strava validerar callback-URL:en direkt (GET med hub.challenge)."
echo "  Kontrollera status: curl -G https://www.strava.com/api/v3/push_subscriptions \\"
echo "    -d client_id=\$STRAVA_CLIENT_ID -d client_secret=\$STRAVA_CLIENT_SECRET"
