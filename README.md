# Bodify

Self-hosted plattform för kost- och träningsuppföljning — träningsloggbok med
rullande program, kostregistrering med streckkodsläsare, Strava/Withings/
Apple Health-synk, mål och utmaningar med vänner samt lokala AI-funktioner.
Allt driftat på din egen maskin via Docker, med inloggning via Cloudflare
Zero Trust.

📐 **[Arkitektur & genomförandeplan](docs/ARKITEKTUR.md)**

## Status

| Fas | Innehåll | Status |
|---|---|---|
| 0 | Fundament: Docker, Cloudflare Access-auth, databas, worker | ✅ |
| 1 | Träningsloggbok: program, rullande split, vilotimer, "föregående pass" | ✅ |
| 2 | Kost: streckkodsläsare (Open Food Facts), måltidsmallar, makromål | ✅ |
| 3 | Integrationer: Withings, Strava, Apple Health, mål ("10 km på 45 min") | ✅ |
| 4 | Dashboard, progressfoton, PWA + Web Push | ✅ |
| 5 | Socialt: vänner, utmaningar, leaderboard, "gick om dig"-notiser | ✅ |
| 6 | AI: passgenerator, readiness-coach, gym-vision (Ollama) | ✅ |
| 7 | Färdiga program (5 st), backup, driftdokumentation | ✅ |

## Kom igång (drift)

### 1. Cloudflare Zero Trust (engångssetup)

1. Skapa en **Tunnel** (Zero Trust → Networks → Tunnels), koppla ditt
   hostname (t.ex. `bodify.dindomän.se`) till `http://caddy:80` och kopiera
   tunnel-token.
2. Skapa en **Access-applikation** för samma hostname med en policy som
   vitlistar godkända e-postadresser. Kopiera applikationens **AUD-tag**.
3. Lägg till en **bypass-policy** för sökvägen `/api/webhooks/*`
   (webhooks skyddas istället av egna hemligheter).

### 2. Konfigurera & starta

```bash
cp .env.example .env    # fyll i Cloudflare-värdena + SECRET_KEY
docker compose --profile tunnel up -d --build
```

Surfa till ditt hostname och logga in — adressen i `BOOTSTRAP_ADMIN_EMAIL`
blir admin vid första inloggningen. Med `AUTO_PROVISION_USERS=true` får alla
vitlistade vänner konto automatiskt vid sin första inloggning.

**På mobilen:** öppna sidan i Safari/Chrome → *Lägg till på hemskärmen*.
Då blir Bodify en fullskärmsapp med kamera (streckkoder, foton) och
push-notiser (iOS 16.4+).

### 3. Integrationer (valfritt, per tjänst)

**Withings** — skapa en app på [developer.withings.com]
(callback: `https://<host>/api/integrations/withings/callback`), fyll i
`WITHINGS_CLIENT_ID/SECRET` i `.env`. Varje användare kopplar sedan sitt
konto under **⚙️ Kopplingar**. Vikt, fett-%, muskelmassa, vatten och PWV
synkas automatiskt via webhooks.

**Strava** — skapa en app på [strava.com/settings/api], fyll i
`STRAVA_CLIENT_ID/SECRET`, låt användarna koppla sina konton, och registrera
appens webhook **en gång**:

```bash
./scripts/strava-webhook-subscribe.sh
```

**Apple Health** — ingen Apple-utvecklarlicens behövs. Varje användare:
1. Installerar **Health Auto Export** på sin iPhone.
2. Skapar en token under **⚙️ Kopplingar** i Bodify.
3. Skapar en REST API-automation i HAE mot
   `https://<host>/api/webhooks/apple-health` med headern
   `Authorization: Bearer <token>` och väljer sömn, HRV, vilopuls, steg
   och träningspass.

Pass som kommer både via Strava och Apple Health dedupliceras automatiskt.

**Push-notiser** — generera VAPID-nycklar och lägg i `.env`:

```bash
npx web-push generate-vapid-keys
```

Användare aktiverar sedan push under **⚙️ Kopplingar**.

### 4. AI-funktioner (valfritt)

```bash
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull llama3.1     # passgenerator + coach
docker compose exec ollama ollama pull qwen2.5vl    # gym-vision (kräver GPU för vettig fart)
```

Utan Ollama fungerar allt utom passgeneratorn och gym-vision — readiness-
coachen använder en deterministisk regelmotor och ger råd ändå.

### 5. Backup

```bash
./scripts/backup.sh            # → ./backups/ (DB-dump + foton)
```

Lägg den i cron på värdmaskinen för nattliga backuper.

## Lokal utveckling (utan Cloudflare)

```bash
docker compose up -d db redis

cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export DEV_AUTH_EMAIL=dev@example.com AUTO_PROVISION_USERS=true
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload      # API på :8000

cd apps/web && npm install && npm run dev    # webb på :3000, proxar /api
```

Tester: `cd apps/api && .venv/bin/python -m pytest` (56 st)

## Struktur

```
├── apps/
│   ├── api/            # FastAPI: auth, domän-API:er, webhooks, AI, worker
│   │   ├── app/
│   │   │   ├── ai/             # Ollama-klient (abstraktionspunkt)
│   │   │   ├── integrations/   # strava, withings, apple_health, openfoodfacts
│   │   │   ├── models/         # SQLAlchemy per domän
│   │   │   ├── routers/        # REST-endpoints per domän
│   │   │   ├── services/       # utmaningslogik, readiness-regler
│   │   │   └── workers/        # ARQ-cronjobb (snapshots, heartbeat)
│   │   └── alembic/            # migrationer inkl. seed-data
│   └── web/            # Next.js 15 PWA (Tailwind, service worker)
├── scripts/            # backup, Strava-webhookregistrering
├── docs/               # arkitektur & plan
├── Caddyfile           # intern routing: /api → api, övrigt → web
└── docker-compose.yml  # caddy, cloudflared, web, api, worker, db, redis, ollama
```

## Säkerhetsmodell i korthet

- **Ingen öppen port** — all trafik går via Cloudflare Tunnel.
- **Inga egna lösenord** — Cloudflare Access sköter inloggning mot
  e-post-vitlistan; backend verifierar `Cf-Access-Jwt-Assertion`-JWT:ns
  signatur, audience och issuer på varje request (`apps/api/app/auth.py`).
- **Webhooks** är undantagna från Access men skyddas av egna hemligheter
  (Strava verify-token, personliga Bearer-tokens för Apple Health).
- **Dataisolering**: alla frågor filtreras på användar-id och testas med
  isoleringstester; PostgreSQL Row Level Security-policies ligger som
  grund för ett framtida byte till icke-ägande databasroll.
- **OAuth-tokens krypteras i vila** (Fernet via `SECRET_KEY`); Apple
  Health-tokens lagras endast som SHA-256-hashar.

## Framtida idéer

- Skrivning tillbaka till Apple Health (via Shortcuts eller companion-app)
- Egen programbyggare i UI:t (API:t stödjer det redan: `POST /api/programs`)
- Intervallpass-editor med måltempo per intervall
- Moln-LLM som opt-in-fallback för gym-vision (`app/ai/ollama.py` är
  abstraktionspunkten)
