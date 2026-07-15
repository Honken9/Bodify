#!/usr/bin/env bash
# Interaktiv ifyllnad av .env — kör: ./scripts/setup-env.sh
# Tryck bara Enter för att acceptera förslaget inom [hakparenteser].
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  read -rp ".env finns redan — skriva över? [j/N] " svar
  case "$svar" in j|J|ja|Ja) ;; *) echo "Avbryter."; exit 0 ;; esac
fi

echo
echo "── Cloudflare ──────────────────────────────────────────"

read -rp "Team-domän [shapiqo.cloudflareaccess.com]: " CF_TEAM_DOMAIN
CF_TEAM_DOMAIN=${CF_TEAM_DOMAIN:-shapiqo.cloudflareaccess.com}

DEFAULT_AUD="fad3b76da876da8443bbcb306bb6fbe57c1b30a82278176b9213de7c9f324ce7"
read -rp "Access AUD-tag [${DEFAULT_AUD:0:12}…]: " CF_ACCESS_AUD
CF_ACCESS_AUD=${CF_ACCESS_AUD:-$DEFAULT_AUD}

TUNNEL_TOKEN=""
while [ -z "$TUNNEL_TOKEN" ]; do
  read -rp "Tunnel-token (börjar med eyJ, klistra in): " TUNNEL_TOKEN
done

echo
echo "Valfritt — för 'Bjud in testare' i admin (Enter för att hoppa över):"
read -rp "  CF API-token: " CF_API_TOKEN
read -rp "  CF Account-ID: " CF_ACCOUNT_ID
read -rp "  CF Access App-ID: " CF_ACCESS_APP_ID

echo
echo "── App ─────────────────────────────────────────────────"

read -rp "Publik URL [https://shapiqo.com]: " PUBLIC_BASE_URL
PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-https://shapiqo.com}

read -rp "Admin-e-post [daniel.holmkvist@gmail.com]: " BOOTSTRAP_ADMIN_EMAIL
BOOTSTRAP_ADMIN_EMAIL=${BOOTSTRAP_ADMIN_EMAIL:-daniel.holmkvist@gmail.com}

rand_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

SECRET_KEY=$(rand_hex 32)
DB_PASSWORD=$(rand_hex 16)
echo
echo "SECRET_KEY och DB_PASSWORD genererades automatiskt."

cat > .env <<EOF
# Genererad av scripts/setup-env.sh $(date +%Y-%m-%d)

# ── Cloudflare ────────────────────────────────────────────────
CF_TEAM_DOMAIN=$CF_TEAM_DOMAIN
CF_ACCESS_AUD=$CF_ACCESS_AUD
TUNNEL_TOKEN=$TUNNEL_TOKEN
CF_API_TOKEN=$CF_API_TOKEN
CF_ACCOUNT_ID=$CF_ACCOUNT_ID
CF_ACCESS_APP_ID=$CF_ACCESS_APP_ID

# ── Databas ───────────────────────────────────────────────────
DB_PASSWORD=$DB_PASSWORD

# ── Användare ─────────────────────────────────────────────────
BOOTSTRAP_ADMIN_EMAIL=$BOOTSTRAP_ADMIN_EMAIL
AUTO_PROVISION_USERS=true

# ── App ───────────────────────────────────────────────────────
SECRET_KEY=$SECRET_KEY
PUBLIC_BASE_URL=$PUBLIC_BASE_URL

# ── Strava (fylls i senare vid behov) ────────────────────────
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_VERIFY_TOKEN=bodify-strava

# ── Withings (fylls i senare vid behov) ──────────────────────
WITHINGS_CLIENT_ID=
WITHINGS_CLIENT_SECRET=

# ── Web Push (npx web-push generate-vapid-keys) ──────────────
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:$BOOTSTRAP_ADMIN_EMAIL
EOF

chmod 600 .env

echo
echo "✓ .env skapad!"
echo
echo "Nästa steg:"
echo "  docker compose --profile tunnel up -d --build"
echo "  docker compose logs -f api    # vänta på 'Application startup complete'"
echo
echo "Sedan: surfa till $PUBLIC_BASE_URL 🎉"
