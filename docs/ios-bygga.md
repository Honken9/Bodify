# Bygga Shapiqo-appen: från Xcode till TestFlight

Appen är en **helt native SwiftUI-app** (etapp 1). Webben används på ett
enda ställe: Cloudflare Access-inloggningen. Allt annat är native vyer
som pratar direkt med API:t på shapiqo.com.

## Vad appen innehåller (etapp 1)

- **Inloggning** — Access-flödet (e-post + engångskod) i en inbäddad vy;
  sessionen sparas i Keychain och appen är sedan helt native tills
  sessionen går ut.
- **Hem** — dagens siffror med dagbläddring: kalorier mot målet, steg,
  vilopuls, vikt, VO₂max, SpO₂, aktiv energi, träningsminuter, trappor.
- **Måltider** — dagens logg per måltid med radering, totaler mot mål,
  och fritextloggning ("Big Mac, mellan pommes, cola zero") via samma
  AI-tolkning som webben.
- **Träning** — senaste passen från alla källor med distans, tid, puls.
- **Profil** — konto, märkesväggen och **Apple Health-synk direkt i
  appen** (HealthKit: steg, puls, HRV, VO₂max, SpO₂, sömnfaser, pass med
  GPS-rutt — postas till samma endpoint som Health Auto Export använde,
  med bakgrundssynk). Health Auto Export behövs inte.

**Etapp 2 (senare):** karta (MapKit), socialt (utmaningar/dueller/ligor),
utmaningsskapande, adminvyer, APNs-push. Tills dess finns allt det på
shapiqo.com i webbläsaren.

## Steg 1 — Öppna projektet

```bash
open ~/Bodify/apps/ios/ios/App/App.xcodeproj
```

## Steg 2 — Signering (redan gjort en gång)

Target **App** → Signing & Capabilities: Automatically manage signing,
team **Alex AB**, bundle-ID `se.vintermist.Shapiqo`, HealthKit-capability
med Background Delivery (Clinical Health Records ska vara AV).

## Steg 3 — Testa på din iPhone

1. iPhone i kabeln → välj den i enhetsväljaren → **⌘R**.
2. Logga in via Access-flödet → appen växlar till native flikar.
3. **Profil → Aktivera Apple Health-synk** → godkänn alla kategorier →
   90 dagar hämtas; "Hämta hela historiken" för allt.

**Tips:** sätt Access-sessionens längd till t.ex. 1 månad så slipper ni
logga in ofta: Cloudflare Zero Trust → Access → Applications → shapiqo →
Session Duration.

## Steg 4 — TestFlight

1. Enhetsväljaren → **Any iOS Device (arm64)** → **Product → Archive**.
2. Organizer → markera det NYA arkivet (kolla tidsstämpeln!) →
   **Distribute App → App Store Connect → Upload**.
3. ~15 min senare: App Store Connect → Shapiqo → TestFlight → lägg till
   dig i intern testgrupp → inbjudan via mejl.
4. Extern testning (Demus m.fl.): egen grupp, lätt granskning ~1 dygn.
   Testarna måste vara vitlistade i Cloudflare Access.

## Kom ihåg

- **Native UI = ny appversion vid ändringar.** Till skillnad från
  webbappen kräver ändringar i appens vyer en ny TestFlight-upload
  (höj Build-numret i Xcode → Archive → Upload).
- **Servern måste vara uppe** när appen används — uptime-larm
  rekommenderas.
- **Om Swift-bygget felar**: kopiera hela felmeddelandet ur Xcode och
  klistra in i Claude-sessionen — koden är skriven utan att ha
  kompilerats på riktig Mac och rättas på studs.

## Mot publik App Store

Se `docs/ios-app-plan.md` fas 4: granskarinloggning, privacy policy,
App Privacy-deklaration (hälsodata), skärmbilder. APNs-push kommer i
etapp 2.
