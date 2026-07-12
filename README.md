# Bodify

Self-hosted plattform för kost- och träningsuppföljning — träningsloggbok,
kostregistrering, Strava/Withings/Apple Health-synk, utmaningar med vänner
och lokala AI-funktioner. Allt driftat på din egen maskin via Docker.

📐 **[Arkitektur & genomförandeplan](docs/ARKITEKTUR.md)**

## Status

| Fas | Innehåll | Status |
|---|---|---|
| 0 | Fundament: Docker, Cloudflare Access-auth, databas, worker | ✅ Klar |
| 1 | Träningsloggbok (program, rullande split, vilotimer) | ✅ Klar |
| 2 | Kost (streckkodsläsare, måltidsmallar) | ⏳ Nästa |
| 3 | Integrationer (Withings, Strava, Apple Health) | – |
| 4 | Dashboard & PWA-polish | – |
| 5 | Socialt & utmaningar | – |
| 6 | AI (gym-vision, passgenerator, coach) | – |

## Kom igång (drift)

1. **Cloudflare Zero Trust** (engångssetup):
   - Skapa en **Tunnel** (Networks → Tunnels) och koppla ditt hostname
     (t.ex. `bodify.dindomän.se`) till `http://caddy:80`. Kopiera tunnel-token.
   - Skapa en **Access-applikation** för samma hostname med en policy som
     vitlistar godkända e-postadresser. Kopiera applikationens **AUD-tag**.
   - Lägg till en bypass-policy för `/api/webhooks/*` (behövs först i Fas 3).
2. Konfigurera miljön:

   ```bash
   cp .env.example .env   # fyll i CF_TEAM_DOMAIN, CF_ACCESS_AUD, TUNNEL_TOKEN
   ```

3. Starta:

   ```bash
   docker compose --profile tunnel up -d --build
   ```

4. Surfa till ditt hostname, logga in via Cloudflare → "Hej Daniel! 👋".
   Adressen i `BOOTSTRAP_ADMIN_EMAIL` blir admin vid första inloggningen.

AI-tjänsterna (Ollama) startas separat när Fas 6 byggs:
`docker compose --profile ai up -d ollama`

## Lokal utveckling (utan Cloudflare)

```bash
# Databas + Redis
docker compose up -d db redis

# API — DEV_AUTH_EMAIL hoppar över Cloudflare-verifieringen lokalt
cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
DEV_AUTH_EMAIL=dev@example.com AUTO_PROVISION_USERS=true \
  .venv/bin/alembic upgrade head
DEV_AUTH_EMAIL=dev@example.com AUTO_PROVISION_USERS=true \
  .venv/bin/uvicorn app.main:app --reload

# Webb (i en annan terminal) — proxar /api till :8000
cd apps/web
npm install
npm run dev
```

Tester: `cd apps/api && .venv/bin/python -m pytest`

## Struktur

```
├── apps/
│   ├── api/    # FastAPI: auth, REST-API, ARQ-worker, Alembic-migrationer
│   └── web/    # Next.js 15 PWA (Tailwind CSS)
├── docs/       # Arkitektur & plan
├── Caddyfile   # Intern routing: /api → api, övrigt → web
└── docker-compose.yml
```

## Säkerhetsmodell i korthet

- Ingen öppen port — all trafik går via Cloudflare Tunnel.
- Cloudflare Access sköter inloggning mot e-post-vitlistan; appen har
  **inga egna lösenord**.
- Backend verifierar `Cf-Access-Jwt-Assertion`-JWT:n (signatur, `aud`, `iss`)
  på varje request — se `apps/api/app/auth.py`.
- Dataisolering per användare med PostgreSQL Row Level Security
  (nyckeln `app.user_id` sätts per transaktion).
