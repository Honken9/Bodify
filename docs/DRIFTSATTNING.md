# Driftsättning: från Loopia-domän till körande Bodify

Checklista för att gå live. Tidsåtgång: ~30 min aktivt arbete +
väntetid på namnserverbytet.

## A. Koppla domänen till Cloudflare (engångsjobb)

1. Skapa ett gratis konto på [dash.cloudflare.com](https://dash.cloudflare.com)
   → **Add a site** → skriv in din domän → välj **Free**-planen.
2. Cloudflare visar nu **två namnservrar**, t.ex.
   `ada.ns.cloudflare.com` och `bob.ns.cloudflare.com`. Låt fliken vara öppen.
3. Logga in i **Loopia kundzon** → klicka på domänen →
   **Namnservrar** (kan ligga under "DNS-inställningar") → byt från
   Loopias namnservrar till Cloudflares två → spara.
4. Vänta. `.se`-domäner slår oftast igenom inom en timme; Cloudflare
   mejlar när domänen är aktiv ("Great news…"). Klicka **Check nameservers**
   i Cloudflare om du är otålig.

> Obs: efter bytet sköts all DNS i Cloudflare — Loopias DNS-verktyg och
> eventuella "parkerad sida"-poster slutar gälla. Det är meningen.

## B. Zero Trust: team, tunnel och inloggning

1. Gå till [one.dash.cloudflare.com](https://one.dash.cloudflare.com) och
   aktivera **Zero Trust** (gratisplanen räcker — upp till 50 användare).
   Du väljer ett **team-namn** → detta ger `CF_TEAM_DOMAIN`,
   t.ex. `holmkvist.cloudflareaccess.com`.
2. **Tunneln:** Networks → Tunnels → **Create a tunnel** → typ
   *Cloudflared* → döp den till `bodify` → **kopiera token** (lång sträng
   som börjar med `eyJ`) → detta är `TUNNEL_TOKEN`. Du behöver INTE köra
   install-kommandona som visas — vår docker-compose kör cloudflared.
3. Samma tunnel → fliken **Public Hostnames** → *Add a public hostname*:
   - Subdomain: `bodify`, Domain: din domän
   - Service: **HTTP** → `caddy:80`
   - Spara (DNS-posten skapas automatiskt).
4. **Inloggningen:** Access → Applications → **Add an application** →
   *Self-hosted*:
   - Application domain: `bodify.dindomän.se`
   - Policy: namn `Vitlista`, action **Allow**, Include → **Emails** →
     lägg in din och testarnas adresser.
   - Spara. Öppna appen igen och kopiera **Application Audience (AUD) Tag**
     → detta är `CF_ACCESS_AUD`.
5. **Webhook-undantaget:** Access → Applications → **Add an application**
   → *Self-hosted* igen:
   - Application domain: `bodify.dindomän.se`, **Path:** `api/webhooks`
   - Policy: action **Bypass**, Include → **Everyone**.
   - (Webhooks skyddas istället av egna hemligheter i appen.)
6. **(Valfritt) API-token för testarsidan i admin:**
   dash.cloudflare.com → My Profile → API Tokens → Create Token →
   Custom → Permission: **Account · Access: Apps and Policies · Edit** →
   detta är `CF_API_TOKEN`. `CF_ACCOUNT_ID` syns i dashboardens URL
   (`dash.cloudflare.com/<account-id>/…`), och `CF_ACCESS_APP_ID` är
   Access-applikationens ID (UUID:t i appens detaljvy/URL — använd
   vitlist-appen från steg 4, inte bypass-appen).

## C. Starta Bodify på din maskin

Kräver Docker Desktop/Engine och git.

```bash
git clone https://github.com/Honken9/Bodify.git && cd Bodify
# (eller checkout av rätt branch om main inte är uppdaterad ännu)

cp .env.example .env
```

Fyll i `.env`:

```ini
CF_TEAM_DOMAIN=holmkvist.cloudflareaccess.com   # ditt team-namn
CF_ACCESS_AUD=<AUD-taggen från steg B4>
TUNNEL_TOKEN=<token från steg B2>
SECRET_KEY=<kör: openssl rand -hex 32>
DB_PASSWORD=<valfritt starkt lösenord>
PUBLIC_BASE_URL=https://bodify.dindomän.se
BOOTSTRAP_ADMIN_EMAIL=daniel.holmkvist@gmail.com
AUTO_PROVISION_USERS=true
```

Starta:

```bash
docker compose --profile tunnel up -d --build
docker compose logs -f api        # vänta på "Application startup complete"
```

## D. Verifiera

1. Surfa till `https://bodify.dindomän.se` → Cloudflares inloggningssida →
   ange din e-post → engångskod i mejlen → **"Hej Daniel! 👋"**.
2. Du är admin (bootstrap-adressen). Kolla **Admin**-länken på hemvyn.
3. På mobilen: öppna sidan → *Lägg till på hemskärmen* → nu funkar
   streckkodsläsaren och (efter VAPID-setup) push-notiser.
4. Bjud in första testaren under **Admin → Externa testare** (kräver
   steg B6) eller lägg in adressen manuellt i Access-policyn.

## Felsökning

| Symptom | Trolig orsak |
|---|---|
| Cloudflare-sidan visas aldrig, "DNS not found" | Namnserverbytet inte klart än — vänta/verifiera i Cloudflare |
| Inloggning ok men appen visar 401 | Fel `CF_ACCESS_AUD` eller `CF_TEAM_DOMAIN` i `.env` |
| "Din e-postadress är inte upplagd" | Adressen saknas i Access-policyn, eller `AUTO_PROVISION_USERS=false` |
| Tunnel "inactive" i dashboarden | `cloudflared`-containern kör inte: `docker compose --profile tunnel up -d` och kolla `docker compose logs cloudflared` |
| 502 från Cloudflare | Caddy/web/api-containrarna är inte uppe — `docker compose ps` |

## Efteråt (valfritt, i egen takt)

- **Push:** `npx web-push generate-vapid-keys` → in i `.env` → starta om.
- **Withings/Strava:** skapa apparna, fyll i nycklarna, koppla under ⚙️,
  kör `./scripts/strava-webhook-subscribe.sh` en gång.
- **Apple Health:** Health Auto Export + token från ⚙️ Kopplingar.
- **AI:** `docker compose --profile ai up -d ollama` + `ollama pull`.
- **Backup i cron:** `0 3 * * * /sökväg/till/Bodify/scripts/backup.sh`
