# Bygga Shapiqo-appen: från Xcode till TestFlight

Allt kodarbete är klart och ligger i `apps/ios`. Det här dokumentet är
checklistan för dig: öppna projektet, signera, bygga och skicka till
TestFlight. Inga extra verktyg behövs på Macen — inte ens Node; allt
genererat är incheckat.

## Vad som redan är byggt

- **`apps/ios/ios/App/App.xcodeproj`** — Xcode-projektet (Capacitor 7 med
  Swift Package Manager, inga CocoaPods). Appen laddar `https://shapiqo.com`
  i en native webbvy, så appen visar alltid senaste deployen.
- **`HealthKitSync.swift`** — native modul som läser Apple Health direkt
  (steg, vilopuls, HRV, VO₂max, SpO₂, trappor, träningsminuter, aktiv
  energi, vikt, kroppsfett, sömnfaser, träningspass med puls och GPS-rutt)
  och POST:ar till samma API-endpoint som Health Auto Export använde.
  Ingen serverändring behövdes — och HAE behövs inte längre i appen.
- **Bakgrundssynk** — nya pass och steg i HealthKit väcker appen som
  synkar tyst (kräver HealthKit background delivery, redan i
  entitlements-filen).
- **Webbsidan** — Kopplingar-sidan visar en ny sektion "📱 Apple Health i
  appen" när den öppnas inne i appen: aktivera med en knapp, synka nu,
  hämta hela historiken, stäng av.
- Inloggning sker via Cloudflare Access precis som på webben; sessionen
  sparas i appens webbvy så OTP-koden behövs bara ibland. Strava/Withings-
  OAuth är vitlistade att öppnas inne i appen.

## Steg 1 — Öppna projektet

```bash
open ~/Bodify/apps/ios/ios/App/App.xcodeproj
```

Första gången: Xcode laddar ner Capacitor-paketen via Swift Package
Manager automatiskt (ser du "Resolving packages…" i statusraden — låt den
jobba klart, tar en minut).

## Steg 2 — Signering

1. Klicka på **App** överst i filträdet till vänster → fliken
   **Signing & Capabilities**.
2. Bocka i **Automatically manage signing**.
3. Välj ditt **Team** (ditt utvecklarkonto) i rullistan.
4. Kontrollera att **Bundle Identifier** är `se.vintermist.Shapiqo`.
   Xcode registrerar App ID:t åt dig första gången.
5. Kontrollera att **HealthKit** syns som capability (entitlements-filen
   är redan kopplad — syns den inte: klicka **+ Capability** → HealthKit).

## Steg 3 — Testa på din iPhone

1. Anslut iPhonen med kabel (eller via wifi efter första gången).
2. Välj din iPhone som mål i enhetsväljaren högst upp.
3. Tryck **⌘R**. Första gången: godkänn utvecklaren på telefonen under
   Inställningar → Allmänt → VPN & enhetshantering.
4. Appen startar, Cloudflare Access-inloggningen dyker upp — logga in som
   vanligt.
5. Gå till **⚙️ Kopplingar** i appen → sektionen **📱 Apple Health i
   appen** → tryck **Aktivera**. iOS visar behörighetsdialogen — slå på
   alla kategorier. Sedan hämtas 90 dagar direkt; tryck **Hela
   historiken** när du vill ha allt.

## Steg 4 — TestFlight

1. Skapa appen i App Store Connect (en gång):
   [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → Mina
   appar → **+** → Ny app → plattform iOS, namn **Shapiqo**, bundle-ID
   `se.vintermist.Shapiqo`, SKU t.ex. `shapiqo-1`.
2. I Xcode: välj **Any iOS Device (arm64)** som mål →
   **Product → Archive**.
3. När arkivet är klart öppnas Organizer → **Distribute App** →
   **App Store Connect** → **Upload** → nästa-nästa-klart.
4. Efter ~15 min dyker bygget upp i App Store Connect under **TestFlight**.
   Första bygget: svara på frågan om exportkryptering (appen använder bara
   HTTPS → svara "standardkryptering", eller lägg till
   `ITSAppUsesNonExemptEncryption = NO` i Info.plist så slipper du frågan).
5. **Intern testning**: lägg till dig själv (och ev. familj med samma
   team) — funkar direkt utan granskning.
6. **Extern testning**: skapa en grupp, bjud in via e-post (Demus m.fl.).
   Kräver en lätt granskning (~1 dygn) första gången. Testarna installerar
   TestFlight-appen och accepterar inbjudan — klart.

## Kom ihåg

- **Vitlistan**: alla testare måste vara vitlistade i Cloudflare Access
  och registrerade i Shapiqo — annars kommer de inte förbi inloggningen.
- **Serverdrift**: appen kräver att shapiqo.com svarar (tunnel + Mac
  vaken). Uptime-larm rekommenderas före extern testning.
- **UI-ändringar kräver ingen ny appversion** — appen visar alltid det
  som är deployat på shapiqo.com. Ny appversion behövs bara när
  native-koden (Swift-filerna) ändras.
- **Om Swift-bygget felar**: kopiera felmeddelandet ur Xcode och klistra
  in i Claude-sessionen så fixas det — koden är skriven utan att ha
  kompilerats på riktig Mac.

## Nästa steg mot publik App Store (inte gjort ännu)

Se `docs/ios-app-plan.md` fas 4: granskarinloggning förbi Cloudflare
Access, publik integritetspolicy-sida, App Privacy-deklaration
(hälsodata!), skärmbilder och beskrivning. APNs-push (notiser i appen) är
också kvar — webbpush når inte in i appens webbvy.
