# Bodify – Systemarkitektur & Genomförandeplan

> Self-hosted, universell plattform för kost- och träningsuppföljning.
> Målbild: "den enda appen du behöver" – driftad lokalt via Docker med minimalt molnberoende.

---

## Innehåll

1. [Övergripande arkitektur](#1-övergripande-arkitektur)
2. [Teknikstack](#2-teknikstack)
3. [Säkerhet & autentisering (Cloudflare Access)](#3-säkerhet--autentisering-cloudflare-access)
4. [Integrationer & dataflöden](#4-integrationer--dataflöden)
5. [Databasstruktur](#5-databasstruktur)
6. [AI-funktioner](#6-ai-funktioner)
7. [Push-notiser](#7-push-notiser)
8. [Genomförandeplan (MVP → fullversion)](#8-genomförandeplan)

---

## 1. Övergripande arkitektur

```
                        Internet
                           │
              ┌────────────▼─────────────┐
              │   Cloudflare Access      │  ← inloggning, e-post-vitlista
              │   (Zero Trust)           │
              └────────────┬─────────────┘
                           │  Cloudflare Tunnel (cloudflared)
   ────────────────────────┼────────────────────────────────────
   Din maskin (Docker)     │
              ┌────────────▼─────────────┐
              │  Reverse proxy (Caddy)   │
              └───┬──────────────────┬───┘
                  │                  │
        ┌─────────▼────────┐  ┌──────▼───────────┐
        │  Frontend (PWA)  │  │  Backend-API     │
        │  Next.js         │  │  FastAPI         │
        └──────────────────┘  └──┬────┬────┬─────┘
                                 │    │    │
              ┌──────────────────┘    │    └──────────────────┐
     ┌────────▼────────┐   ┌──────────▼─────────┐   ┌─────────▼────────┐
     │  PostgreSQL 16  │   │  Worker (ARQ)      │   │  Ollama          │
     │  + TimescaleDB  │   │  synk, notiser,    │   │  vision + text   │
     │  + RLS          │   │  AI-jobb           │   │  (lokala LLM:er) │
     └─────────────────┘   └──────────┬─────────┘   └──────────────────┘
                                      │
                               ┌──────▼──────┐
                               │   Redis     │  (jobbkö + cache)
                               └─────────────┘

   Inkommande webhooks:  Strava ─┐
                         Withings ├─► /api/webhooks/... (via tunneln)
                         Health Auto Export (iPhone) ─┘
```

**Principer**

- **Allt körs i Docker Compose** på din egen maskin. Enda externa beroenden:
  Cloudflare (auth + tunnel), Strava/Withings API:er, Open Food Facts, samt
  Apples push-tjänst (indirekt via Web Push).
- **Origin är aldrig exponerad direkt** – all trafik går genom Cloudflare
  Tunnel, så du behöver inte öppna portar i din router.
- **PWA istället för nativ app** – en installerbar Progressive Web App ger
  kamera (streckkoder + foton), push-notiser (iOS 16.4+) och hemskärmsikon
  utan App Store, utan Mac för utveckling och utan årlig Apple-avgift.
- **Multi-tenant på radnivå** – varje rad ägs av en användare; PostgreSQL
  Row Level Security (RLS) garanterar isolering även om applikationskoden
  skulle innehålla en bugg.

---

## 2. Teknikstack

| Lager | Val | Motivering |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui** | PWA-stöd, snabb UI-utveckling, stort ekosystem. shadcn/ui ger snygga, tillgängliga komponenter direkt. |
| Streckkodsläsare | **`html5-qrcode` / ZXing-js** (fallback: native `BarcodeDetector`) | Fungerar i mobilkameran direkt i PWA:n, ingen nativ app krävs. |
| Grafer | **Recharts** (alt. Observable Plot) | Viktkurvor, fett-%, PWV, veckovolym m.m. |
| Backend | **Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic** | Utmärkt för webhooks/API-integrationer, Pydantic-validering, förstklassigt AI-ekosystem. |
| Bakgrundsjobb | **ARQ** (Redis-baserad, async) | Token-refresh, synkjobb, AI-jobb, notisutskick, nattliga aggregat. |
| Databas | **PostgreSQL 16 + TimescaleDB** | Relationsdata + tidsserier (kroppsmetrik, HRV, pulsdata) i samma databas. RLS för tenant-isolering. |
| Cache/kö | **Redis 7** | Jobbkö + cache av livsmedelsuppslag. |
| AI lokalt | **Ollama** (`qwen2.5-vl` för bild, `llama3.1/qwen2.5` för text) | Körs helt lokalt. Providern abstraheras så att ett moln-API (t.ex. Claude) kan slås på som opt-in-fallback för svårare bildtolkning. |
| Push | **Web Push (VAPID)** via `pywebpush` | Självhostat, gratis, fungerar på iOS (installerad PWA, 16.4+) och Android. |
| Reverse proxy | **Caddy** | Automatisk intern TLS, enkel konfig. |
| Ingress | **cloudflared** (Cloudflare Tunnel) | Ingen portöppning; Access-policyn appliceras framför allt. |
| Livsmedelsdata | **Open Food Facts** (streckkoder) + **Livsmedelsverkets databas** (svenska basvaror) | OFF har utmärkt streckkodstäckning; Livsmedelsverket ger korrekta näringsvärden för svenska råvaror. Uppslag cachas lokalt i `food_items`. |

**Monorepo-layout**

```
bodify/
├── docker-compose.yml
├── apps/
│   ├── web/          # Next.js PWA
│   └── api/          # FastAPI + workers
│       ├── app/
│       │   ├── routers/      # trainings-, kost-, webhook-, admin-endpoints
│       │   ├── integrations/ # strava.py, withings.py, apple_health.py
│       │   ├── ai/           # ollama-klient, prompts, provider-abstraktion
│       │   ├── models/       # SQLAlchemy
│       │   └── workers/      # ARQ-jobb
│       └── alembic/
├── packages/
│   └── shared/       # delade typer (OpenAPI-genererad TS-klient)
└── docs/
```

---

## 3. Säkerhet & autentisering (Cloudflare Access)

### Princip

Appen har **inga egna lösenord**. Cloudflare Access sköter inloggning
(e-post-OTP eller valfri IdP) och släpper bara igenom vitlistade adresser.
Backend **litar aldrig blint** på att trafiken kom via Cloudflare – den
verifierar kryptografiskt varje request.

### Flöde

1. Användaren surfar till `bodify.dindomän.se` → Cloudflare Access kräver
   inloggning mot din vitlista.
2. Access injicerar en signerad JWT i headern **`Cf-Access-Jwt-Assertion`**
   (finns även som cookie `CF_Authorization`).
3. En FastAPI-middleware verifierar JWT:n på varje request:
   - **Signatur** mot Cloudflares publika nycklar:
     `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` (cachas, roteras automatiskt).
   - **`aud`** = din Access-applikations AUD-tag (miljövariabel).
   - **`iss`** = `https://<team>.cloudflareaccess.com`.
   - **`exp`** – ej utgången.
4. `email`-claimen slås upp mot `users`-tabellen:
   - Finns användaren → requesten får `user_id`, och `SET LOCAL app.user_id`
     sätts i databastransaktionen (RLS-nyckeln).
   - Finns den inte → 403, eller auto-provisionering om admin aktiverat det.

```python
# apps/api/app/auth.py (kärnan)
import jwt
from jwt import PyJWKClient

jwks = PyJWKClient(f"https://{TEAM}.cloudflareaccess.com/cdn-cgi/access/certs")

async def verify_cf_access(request: Request) -> str:
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if not token:
        raise HTTPException(401, "Missing Cloudflare Access token")
    key = jwks.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token, key.key, algorithms=["RS256"],
        audience=CF_ACCESS_AUD,
        issuer=f"https://{TEAM}.cloudflareaccess.com",
    )
    return claims["email"]
```

### Försvar i djupled

| Åtgärd | Effekt |
|---|---|
| Cloudflare Tunnel (ingen öppen port) | Origin kan inte nås utan att passera Access. |
| JWT-verifiering i backend | Skydd även om tunneln/nätet skulle felkonfigureras. |
| Webhook-endpoints (`/api/webhooks/*`) undantas från Access-policyn men skyddas med **egna hemligheter** | Strava verify_token, Withings-signatur, egen bearer-token för Health Auto Export. |
| PostgreSQL RLS per `user_id` | Dataisolering mellan vänner garanteras i databaslagret. |
| Adminroll = flagga i `users` + separat Access-policy på `/admin` | Dubbel grind för adminfunktioner. |

---

## 4. Integrationer & dataflöden

### 4.1 Strava (löpning, cykling, konditionspass)

```
Strava ──(webhook: activity created/updated)──► /api/webhooks/strava
                                                      │
                                    ARQ-jobb: hämta aktivitet + streams
                                                      │
                                    normalisera → cardio_activities (+ samples)
```

1. **Anslutning:** klassisk OAuth2 – användaren klickar "Koppla Strava",
   godkänner scope `activity:read_all`, backend sparar access/refresh-token
   i `oauth_connections` (krypterade med Fernet-nyckel från env).
2. **Webhook-prenumeration:** en per app (inte per användare). Strava
   verifierar endpointen med en GET + `hub.challenge`-eko. Events innehåller
   `owner_id` + `object_id`; workern slår upp rätt användare och hämtar
   aktiviteten + streams (tid, distans, puls, tempo) via API:t.
3. **Normalisering:** allt lagras i ett källoberoende format
   (`cardio_activities` + `activity_samples`), med `external_id` +
   `source='strava'` för dedupe – samma pass som även kommer via Apple Health
   skrivs inte in dubbelt.
4. **Tempo/intervaller:** min/km beräknas ur streams; intervallpass matchas
   mot definierade `interval_workouts` för målspårning (t.ex. "10 km på 45 min"
   → progressionskurva mot mål-tempot 4:30/km).

### 4.2 Withings (vikt, fett-%, muskelmassa, vatten, PWV)

```
Withings ──(notify-webhook: ny mätning)──► /api/webhooks/withings
                                                 │
                              ARQ-jobb: GET /measure (getmeas)
                                                 │
                              body_metrics (TimescaleDB-hypertabell)
```

1. **OAuth2** som Strava; scopes `user.metrics`.
2. **Notify-prenumerationer** per användare (appli 1 = kroppsmätningar,
   appli 4 = blodtryck/hjärta). Withings pushar bara *att* något hänt –
   workern hämtar själva mätvärdena.
3. **Mättyper som lagras** (Withings `meastype` → vår metrik):
   `1` vikt, `6` fettprocent, `76` muskelmassa, `77` vattenmängd,
   `88` benmassa, `91` **pulsvågshastighet (PWV)**, `11` vilopuls.
   Schemat är generiskt (`metric_type` + `value`), så nya mätetal kräver
   ingen migrering – bara en ny rad i metrik-katalogen.
4. **Målspårning:** mål som "ner till 11 % fett" lagras i `goals` och plottas
   mot tidsserien med trendlinje (rullande 7-dagarssnitt, eftersom
   dagsvärden för fett-% är brusiga).

### 4.3 Apple Health – strategin för det saknade webb-API:t

Apple Health har inget moln-API; datat bor i telefonen. Elegantast utan att
bygga en egen iOS-app:

**Primär lösning: [Health Auto Export] (App Store-app, ~engångskostnad)**

```
iPhone (HealthKit) ──► Health Auto Export ──(REST-automation, JSON)──►
   https://bodify.dindomän.se/api/webhooks/apple-health   (Bearer-token per användare)
```

- Varje användare installerar appen, pekar automationen mot din endpoint och
  klistrar in sin personliga ingest-token (genereras i Bodify under
  *Inställningar → Kopplingar*).
- Automationen kör t.ex. varje timme och skickar: **sömn, HRV, vilopuls,
  steg, träningspass, aktiv energi**.
- Backend validerar token → mappar till `user_id` → normaliserar in i
  `body_metrics`, `sleep_sessions` och `cardio_activities` (med dedupe mot
  Strava via tidsöverlapp + typ).

**Skrivning tillbaka till Apple Health** (pass loggade i Bodify → Health):
lösbart i v2 via "Shortcuts"-genvägar eller en minimal egen HealthKit-app.
MVP:n nöjer sig med läsriktningen – det är den som driver
återhämtningsanalysen.

**Framtidssäkring:** ingestlagret är källoberoende. Byter du senare till en
egen companion-app eller annan exportör ändras bara adaptern, inte datamodellen.

### 4.4 Sammanfattande dataflödesprincip

Alla tre integrationer följer samma mönster – **webhook → kö → hämta →
normalisera → lagra** – vilket gör systemet robust (retry i kön) och lätt att
utöka (Garmin/Polar/Oura = ny adapter i `integrations/`).

---

## 5. Databasstruktur

Översikt (PK/FK utelämnade där de är uppenbara; **alla användardata-tabeller
har `user_id` + RLS-policy**):

### Användare & plattform

```sql
users(id, email UNIQUE, display_name, avatar_url, is_admin bool,
      units, locale, created_at)

oauth_connections(id, user_id, provider ENUM(strava,withings),
      access_token_enc, refresh_token_enc, expires_at,
      external_user_id, scopes, status)

ingest_tokens(id, user_id, token_hash, source ENUM(apple_health),
      last_seen_at)   -- Health Auto Export-nycklar

push_subscriptions(id, user_id, endpoint, p256dh, auth, created_at)

notifications(id, user_id, type, title, body, data jsonb,
      sent_at, read_at)
```

### Styrketräning

```sql
exercises(id, name, muscle_groups text[], equipment text[],
      is_global bool, created_by)          -- globalt bibliotek + egna

programs(id, user_id NULL för globala, name, description,
      level ENUM(beginner,intermediate,advanced), days_per_week)

program_days(id, program_id, name, position)      -- "Pass A", "Pass B"...
program_day_exercises(id, program_day_id, exercise_id, position,
      target_sets, target_reps, rest_seconds, notes)

-- Rullande split: user_programs pekar på nästa dag i rotationen,
-- så en 4-dagarssplit med två likadana pass (A,B,A,B) bara rullar vidare
user_programs(id, user_id, program_id, started_at, next_day_position)

workout_sessions(id, user_id, program_day_id NULL, started_at,
      finished_at, notes, source ENUM(manual,generated))

workout_sets(id, session_id, exercise_id, set_number,
      weight_kg, reps, rpe, is_warmup, rest_seconds_actual)
```

> **"Föregående pass"-vyn** är en enkel fråga: senaste `workout_sets` för
> samma `exercise_id` + `user_id`, grupperat på session – visas inline vid
> inmatning så progressiv överbelastning blir självklar.

### Kondition

```sql
cardio_activities(id, user_id, type ENUM(run,ride,walk,swim,other),
      source ENUM(strava,apple_health,manual), external_id,
      started_at, duration_s, distance_m, avg_hr, max_hr,
      avg_pace_s_per_km, calories, raw jsonb)
      UNIQUE(user_id, source, external_id)

activity_samples(activity_id, t_offset_s, hr, pace_s_per_km,
      altitude_m)                          -- TimescaleDB-hypertabell

interval_workouts(id, user_id, name, structure jsonb)
      -- t.ex. [{"repeat":5,"work":"1000m@4:20","rest":"90s"}]

goals(id, user_id, kind ENUM(pace_distance,body_metric,frequency),
      target jsonb, deadline, achieved_at)
      -- {"distance_m":10000,"time_s":2700}  = 10 km på 45 min
      -- {"metric":"fat_percent","value":11} = ner till 11 %
```

### Kost

```sql
food_items(id, barcode UNIQUE NULL, name, brand, source ENUM(off,slv,custom),
      per_100g jsonb)   -- kcal, protein, kolhydrater, fett, fibrer...

meal_templates(id, user_id, name, items jsonb)  -- "Min standardfrukost"

meal_entries(id, user_id, eaten_at, meal ENUM(breakfast,lunch,dinner,snack),
      food_item_id, grams, kcal, protein_g, carbs_g, fat_g)
      -- makron denormaliserade för snabba dashboards

nutrition_targets(id, user_id, valid_from, kcal, protein_g, carbs_g, fat_g)
```

### Kroppsdata & återhämtning (TimescaleDB-hypertabeller)

```sql
body_metrics(user_id, metric ENUM(weight,fat_percent,muscle_mass,
      hydration,bone_mass,pwv,resting_hr,hrv_rmssd,vo2max,...),
      measured_at, value numeric, source, raw jsonb)
      -- ett generiskt schema: nya mätetal = ny enum-rad, ingen migrering

sleep_sessions(user_id, start_at, end_at, deep_s, rem_s, light_s,
      awake_s, source)
```

### Socialt & gamification

```sql
friendships(user_id, friend_id, status ENUM(pending,accepted))

challenges(id, creator_id, name, metric ENUM(workout_count,
      weight_loss_kg, fat_loss_percent, distance_m),
      starts_at, ends_at, visibility)

challenge_participants(challenge_id, user_id, joined_at,
      baseline jsonb)   -- startvikt/start-fett-% låses vid join

challenge_snapshots(challenge_id, user_id, day, value)
      -- nattligt jobb; driver leaderboard + "vän gick om dig"-notiser

progress_photos(id, user_id, taken_at, pose ENUM(front,side,back),
      file_path, challenge_id NULL)   -- filer på volym, ej i DB
```

### Tenant-isolering (RLS)

```sql
ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON workout_sessions
  USING (user_id = current_setting('app.user_id')::uuid);
-- Undantag för delning styrs av explicita policies
-- (t.ex. challenge-deltagares snapshots är läsbara för andra deltagare).
```

---

## 6. AI-funktioner

Alla AI-anrop går genom en **provider-abstraktion** (`ai/provider.py`):
default är Ollama lokalt; ett moln-API kan aktiveras per funktion i admin.

| Funktion | Modell (lokalt) | Flöde |
|---|---|---|
| **Gym-vision** | `qwen2.5-vl` (vision) | Foto → vision-modellen identifierar utrustning → matchas mot `exercises.equipment` → förslagslista med övningar, direkt startbara som pass. Ärlig brasklapp: lokala vision-modeller är godkända men inte perfekta – därför visas förslagen som redigerbar lista, och moln-fallback är ett opt-in. |
| **Pass-generator** | `llama3.1`/`qwen2.5` | Prompt byggs av: tillgänglig tid, utrustning, senaste veckans volym per muskelgrupp, aktivt program. Modellen svarar i **strikt JSON-schema** (valideras med Pydantic, retry vid ogiltigt svar) → blir en `workout_session`-mall. |
| **Holistisk coach** | `llama3.1` + regelmotor | Nattligt jobb beräknar readiness: HRV-trend (7d vs 28d), sömnskuld, akut:kronisk träningsbelastning (ACWR). **Regelmotorn** flaggar läget (grön/gul/röd); LLM:en formulerar bara rådet och anpassar dagens pass ("byt benpasset mot rörlighet + 20 min zon 2"). Beslutslogiken är alltså deterministisk och testbar – LLM:en är presentationslager. |

Hårdvarunot: vision-modeller kräver en GPU med ≥ 8–12 GB VRAM för rimlig
svarstid. Utan GPU: kör textmodellerna lokalt och gym-vision via moln-API.

---

## 7. Push-notiser

**Web Push med VAPID-nycklar** – helt självhostat, ingen Firebase-server krävs
för webbläsar-push (leverans sker via Apples/Googles push-gateways, vilket är
ofrånkomligt, men du behöver inget konto):

1. PWA:n registrerar en service worker och begär push-tillstånd
   (på iOS krävs att appen är **tillagd på hemskärmen**, iOS 16.4+ –
   onboarding-flödet instruerar användaren).
2. Prenumerationen sparas i `push_subscriptions`.
3. ARQ-workern skickar via `pywebpush` vid händelser:
   - vän går om dig i utmaning (från `challenge_snapshots`-jobbet),
   - påminnelse om dagens pass / måltidsloggning,
   - readiness-råd från coachen ("hög belastning + låg HRV – vila idag?").
4. Alla notistyper är per-användare-konfigurerbara (ingen notisspam).

---

## 8. Genomförandeplan

Varje fas är körbar och ger värde på egen hand. Bygg i ordning.

### Fas 0 – Fundament (≈ 1 vecka)
- [ ] Monorepo, Docker Compose: Postgres+Timescale, Redis, FastAPI, Next.js, Caddy, cloudflared, Ollama.
- [ ] Cloudflare Tunnel + Access-app med e-post-vitlista.
- [ ] JWT-middleware (avsnitt 3) + `users`-tabell + RLS-grund.
- [ ] Alembic-migrationer, CI (lint + test), OpenAPI → TS-klientgenerering.
- **Klart när:** du loggar in via Cloudflare och ser "Hej Daniel" från databasen.

### Fas 1 – Träningsloggbok (MVP-kärna, ≈ 2–3 veckor)
- [ ] Övningsbibliotek (seed ~200 övningar med muskelgrupper/utrustning).
- [ ] Program & rullande split (`user_programs.next_day_position`).
- [ ] Inmatningsvy: set/reps/vikt, **föregående pass inline**, vilotimer
      (lokal timer + valfri push när vilan är slut).
- [ ] Passhistorik + enkel volym/PR-vy.
- **Klart när:** du kör din 4-dagarssplit helt i appen och ser förra passets vikter vid varje övning.

### Fas 2 – Kost (≈ 2 veckor)
- [ ] Streckkodsläsare i PWA:n → Open Food Facts-uppslag → lokal cache.
- [ ] Sökning (OFF + Livsmedelsverket), egna livsmedel, måltidsmallar.
- [ ] Dagsvy med makromål och veckosummering.
- **Klart när:** att logga en normal dag tar under 2 minuter.

### Fas 3 – Integrationer (≈ 2–3 veckor)
- [ ] Withings OAuth + notify-webhooks → `body_metrics` (vikt, fett-%, muskel, vatten, PWV).
- [ ] Strava OAuth + webhooks → `cardio_activities` + tempo/intervaller.
- [ ] Apple Health-ingest (Health Auto Export-endpoint + per-användar-token): sömn, HRV, steg, pass. Dedupe mot Strava.
- [ ] Mål-modellen: "10 km på 45 min", "11 % fett" med progressionsgrafer.
- **Klart när:** morgonvägning och gårdagens löprunda dyker upp av sig själva.

### Fas 4 – Dashboard & PWA-polish (≈ 1–2 veckor)
- [ ] Dashboard: vecka/månad/år – pass, kostföljsamhet, viktkurva, tempotrend.
- [ ] Progressfoton (kamera → volym, före/efter-jämförelseslider).
- [ ] Full PWA: offline-skal, installationsonboarding, push-registrering.

### Fas 5 – Socialt & gamification (≈ 2 veckor)
- [ ] Vänner (alla är redan vitlistade i Access – friendship är bara opt-in-delning).
- [ ] Utmaningar: flest pass / total viktnedgång / procentuell fettnedgång, med baseline-låsning och nattliga snapshots.
- [ ] Leaderboard + push: "Anna gick precis om dig!".
- [ ] Admin-gränssnitt: användare, kopplingsstatus, jobbkö, notisutskick, feature-flags.

### Fas 6 – AI (≈ 2–3 veckor)
- [ ] Provider-abstraktion + Ollama-integration.
- [ ] Pass-generatorn (tid/utrustning → JSON-pass).
- [ ] Readiness-motorn (HRV/sömn/ACWR-regler) + coach-råd på dashboarden.
- [ ] Gym-vision (foto → övningsförslag).

### Fas 7 – Färdiga program & finlir
- [ ] Program-/kostbibliotek för nybörjare→avancerad (seedas som globala `programs`).
- [ ] Skrivning till Apple Health (Shortcuts eller companion-app) – om behovet finns.
- [ ] Backupjobb (pg_dump + fotovolym → extern disk/NAS).

---

## Bilaga: docker-compose-skiss

```yaml
services:
  caddy:      { image: caddy:2, ports: [] }          # bara internt nät
  cloudflared:{ image: cloudflare/cloudflared, command: tunnel run }
  web:        { build: apps/web }
  api:        { build: apps/api, depends_on: [db, redis] }
  worker:     { build: apps/api, command: arq app.workers.main.WorkerSettings }
  db:         { image: timescale/timescaledb:latest-pg16,
                volumes: [dbdata:/var/lib/postgresql/data] }
  redis:      { image: redis:7-alpine }
  ollama:     { image: ollama/ollama,
                volumes: [ollama:/root/.ollama],
                deploy: { resources: { reservations: { devices:
                  [{ driver: nvidia, count: 1, capabilities: [gpu] }] } } } }
volumes: { dbdata: {}, ollama: {}, photos: {} }
```
