# Plan: Shapiqo som iOS-app i App Store

Målet är en riktig iOS-app byggd som ett Capacitor-skal runt den befintliga
webbappen, med två native-funktioner som ger den ett eget värde: direkt
HealthKit-synk (ersätter Health Auto Export) och riktiga push-notiser via
APNs. Lansering sker i två steg — först TestFlight till familj och vänner,
sedan publik App Store-listning.

## Fas 0 — Förberedelser (Daniel, kan göras direkt)

- [ ] Registrera Apple Developer Program på developer.apple.com (99 USD/år).
      Verifieringen tar ibland 1–2 dagar — starta den först av allt.
- [ ] Installera Xcode från Mac App Store (~15 GB, låt den stå och ladda).
- [ ] Bestäm bundle-ID, förslag: `com.shapiqo.app`.
- [ ] App-ikon: en 1024×1024-bild behövs. Underlag kan genereras från
      befintlig PWA-ikon.

## Fas 1 — Capacitor-skal (Claude bygger i repot)

- [ ] Nytt paket `apps/ios` med Capacitor: iOS-projekt som laddar
      `https://shapiqo.com` i en native webbvy (remote-läge = appen visar
      alltid senaste deployen, UI-ändringar kräver aldrig app-uppdatering).
- [ ] Persistenta cookies i WKWebView så Cloudflare Access-sessionen
      överlever appomstarter (ingen ny OTP varje gång).
- [ ] Safe areas/notch, statusfärg, splashskärm, appikon i alla storlekar.
- [ ] Extern-länk-hantering (Strava/Withings-OAuth öppnas korrekt och
      studsar tillbaka in i appen).

**Beslutspunkt inloggning:** på sikt bör appen autentisera direkt mot API:t
med egen långlivad token (t.ex. QR/engångskod från webbvyn) i stället för
att gå genom Cloudflare Access-OTP. Det gör både granskarkontot (fas 4) och
vardagsanvändningen enklare. Kan byggas i fas 2 eller senare.

## Fas 2 — Native mervärde (Claude bygger, Daniel testar på sin iPhone)

- [ ] **HealthKit-synk**: appen begär läsrättigheter för steg, puls, sömn,
      träningspass, VO₂max, SpO₂, trappor, aktiv energi och GPS-rutter och
      postar till befintliga `/api/apple-health`-endpoints med ingest-token
      (samma väg som Health Auto Export använder i dag — servern behöver
      knappt röras). Health Auto Export blir därmed onödig för iPhone-
      användare.
- [ ] Bakgrundssynk med HealthKit observer queries + background delivery,
      så data flyter in utan att appen öppnas.
- [ ] **APNs-push**: webbpush når inte in i en WKWebView, så appen
      registrerar en APNs-token. Backend: ny kolumn/tabell för APNs-tokens
      bredvid webbpush-prenumerationerna, sändning med token-baserad
      `.p8`-nyckel; `app/push.py` får en gemensam ingång som väljer kanal.
      Alla befintliga notiser (utmaningar, dueller, etapper, märken,
      påminnelser) fungerar då automatiskt i appen.

## Fas 3 — Signering och TestFlight (Daniel med steg-för-steg-guide)

- [ ] Öppna `apps/ios` i Xcode, välj Signing Team (utvecklarkontot),
      aktivera capabilities: HealthKit, Push Notifications, Background
      Modes.
- [ ] Skapa app-posten i App Store Connect (namn Shapiqo, bundle-ID).
- [ ] Product → Archive → ladda upp bygget.
- [ ] Aktivera TestFlight: intern testning är tillgänglig direkt utan
      granskning; extern testning (upp till 10 000 testare) kräver en
      lättare granskning (~1 dygn).
- [ ] Bjud in testarna via e-post/länk — appen installeras via TestFlight-
      appen och känns som vilken app som helst.

## Fas 4 — Publik App Store-lansering

- [ ] **Granskarkonto**: Apples granskare måste kunna logga in. Lös innan
      inskick — antingen app-egen inloggning från fas 2-beslutet, eller en
      vitlistad demoadress vars OTP-kod Daniel kan läsa och ange i
      granskningsanteckningarna, eller en Access-policy som släpper förbi
      ett dedikerat granskarkonto.
- [ ] **Integritetssida**: publik privacy policy på shapiqo.com (krav för
      hälsoappar) + App Privacy-deklarationen i App Store Connect.
      Hälsodata är extra känsligt: HealthKit-data får aldrig delas med
      tredje part eller användas för reklam — Shapiqo skickar den bara
      till Daniels egen server, vilket ska framgå tydligt.
- [ ] Skärmbilder (minst 6,7-tumsformat), beskrivning, nyckelord,
      åldersmärkning, kategori Hälsa & fitness.
- [ ] **Drift under granskningen**: servern måste vara uppe när Apple
      testar — uptime-larm och gärna backup-ström/nät innan inskick.
- [ ] Skicka in; typisk granskningstid 1–3 dagar. Vid avslag enligt 4.2
      ("minimal funktionalitet") är motmedlet mer native-yta: widgets,
      Live Activities för pågående pass, Siri-genvägar.

## Kostnader och tidslinje

| Post | Kostnad |
|---|---|
| Apple Developer Program | 99 USD/år |
| Allt annat (Capacitor, Xcode, TestFlight) | 0 kr |

Grovt uppskattat: fas 1 kan byggas direkt, fas 2 är det största
utvecklingsblocket, fas 3 hänger på att utvecklarkontot är godkänt, fas 4
är mest formalia och väntetid. TestFlight-versionen är alltså realistisk
inom kort efter att kontot är klart; publik listning därefter när
granskarinloggning och privacy-sidan är på plats.

## Risker

- **Riktlinje 4.2 (webbwrapper)** — mitigeras av HealthKit + APNs; mer
  native-yta finns som plan B.
- **Cloudflare Access vs granskare** — löses i fas 4-punkten ovan; app-egen
  inloggning är den robusta vägen.
- **Självhostad server** — nedtid under granskning ger avslag; uptime-larm
  först.
- **Apple-kontots ledtid** — utanför vår kontroll; därför startas fas 0
  först av allt.
