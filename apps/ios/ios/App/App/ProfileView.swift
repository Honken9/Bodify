import SwiftUI

/// Profil: konto, märkesväggen och Apple Health-synken (native
/// HealthKit — inget mellansteg behövs).
struct ProfileView: View {
    @ObservedObject var session: SessionStore

    @State private var me: Me?
    @State private var badges: [BadgeModel] = []
    @State private var providers: [ProviderStatus] = []
    @State private var syncing: String?
    @State private var syncMessage: String?
    @State private var connectProvider: String?
    @State private var healthConfigured = HealthKitService.shared.isConfigured
    @State private var busy: String?
    @State private var healthMessage: String?
    @State private var errorMessage: String?

    var body: some View {
        NavigationView {
            List {
                if let message = errorMessage {
                    ErrorBanner(message: message)
                }

                Section("Konto") {
                    if let me = me {
                        Text(me.display_name ?? me.email).bold()
                        Text(me.email).font(.footnote).foregroundColor(.secondary)
                    }
                    Button("Logga ut", role: .destructive) {
                        session.logout()
                    }
                }

                Section("🍎 Apple Health") {
                    if healthConfigured {
                        if let last = HealthKitService.shared.lastSync {
                            Text("Senaste synk: \(format(last))")
                                .font(.footnote).foregroundColor(.secondary)
                        }
                        Button(busy == "sync" ? "Synkar…" : "🔄 Synka nu") {
                            Task { await runSync(days: 7, label: "sync") }
                        }
                        .disabled(busy != nil)
                        Button(busy == "all" ? "Hämtar…" : "📚 Hämta hela historiken") {
                            Task { await runSync(days: 3650, label: "all") }
                        }
                        .disabled(busy != nil)
                        Button("Stäng av synken", role: .destructive) {
                            HealthKitService.shared.disable()
                            healthConfigured = false
                            healthMessage = nil
                        }
                    } else {
                        Text("Appen läser steg, puls, sömn, VO₂max och pass "
                             + "med GPS direkt ur iPhonen och synkar till ditt konto.")
                            .font(.footnote).foregroundColor(.secondary)
                        Button(busy == "activate" ? "Aktiverar…" : "Aktivera Apple Health-synk") {
                            Task { await activate() }
                        }
                        .disabled(busy != nil)
                    }
                    if let message = healthMessage {
                        Text(message).font(.footnote).foregroundColor(.secondary)
                    }
                }

                Section("🔗 Kopplingar") {
                    ForEach(providers, id: \.provider) { provider in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(providerName(provider.provider)).bold()
                                Text(provider.connected ? "Kopplad — synkar automatiskt" : "Inte kopplad")
                                    .font(.caption)
                                    .foregroundColor(provider.connected ? .green : .secondary)
                            }
                            Spacer()
                            if provider.connected {
                                Button(syncing == provider.provider ? "Synkar…" : "🔄 Synka") {
                                    Task { await syncProvider(provider.provider) }
                                }
                                .buttonStyle(.bordered)
                                .font(.caption)
                                .disabled(syncing != nil)
                            } else {
                                Button("Koppla") {
                                    connectProvider = provider.provider
                                }
                                .buttonStyle(.borderedProminent)
                                .font(.caption)
                            }
                        }
                    }
                    if let message = syncMessage {
                        Text(message).font(.footnote).foregroundColor(.secondary)
                    }
                }

                Section("🔔 Notiser") {
                    if UserDefaults.standard.bool(forKey: "shapiqo.push.enabled") {
                        Text("Notiser är på — dueller, etappsegrar, märken och "
                             + "påminnelser landar direkt i appen.")
                            .font(.footnote).foregroundColor(.secondary)
                    } else {
                        Button("Aktivera notiser") {
                            AppDelegate.enablePush()
                        }
                    }
                }

                Section("🎖 Märken (\(badges.filter { $0.earned }.count) av \(badges.count))") {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        ForEach(badges) { badge in
                            VStack(spacing: 3) {
                                Text(badge.emoji).font(.title2)
                                Text(badge.title)
                                    .font(.caption2).bold()
                                    .multilineTextAlignment(.center)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(Color(.secondarySystemBackground))
                            .cornerRadius(10)
                            .opacity(badge.earned ? 1.0 : 0.3)
                            .saturation(badge.earned ? 1.0 : 0.0)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            .navigationTitle("Profil")
            .refreshable { await load() }
            .sheet(item: Binding(
                get: { connectProvider.map { ConnectRef(provider: $0) } },
                set: { connectProvider = $0?.provider }
            )) { ref in
                ConnectProviderSheet(provider: ref.provider) {
                    connectProvider = nil
                    Task { await load() }
                }
            }
        }
        .navigationViewStyle(.stack)
        .onAppear { Task { await load() } }
    }

    private func format(_ date: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "sv_SE")
        f.dateFormat = "d MMM HH:mm"
        return f.string(from: date)
    }

    private func load() async {
        errorMessage = nil
        do {
            me = try await APIClient.shared.get("api/me")
            badges = try await APIClient.shared.get("api/social/badges")
            let integrations: IntegrationsStatus =
                try await APIClient.shared.get("api/integrations")
            providers = integrations.providers
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
        healthConfigured = HealthKitService.shared.isConfigured
    }

    private func providerName(_ key: String) -> String {
        key == "strava" ? "Strava" : key == "withings" ? "Withings" : key
    }

    private func syncProvider(_ provider: String) async {
        syncing = provider
        syncMessage = nil
        defer { syncing = nil }
        do {
            struct SyncResult: Decodable {
                let imported: Int?
                let paused: Bool?
                let queued: Bool?
            }
            let result: SyncResult = try await APIClient.shared.post(
                "api/integrations/\(provider)/sync", body: [:]
            )
            if result.queued == true {
                syncMessage = "⏳ Full historikhämtning körs i bakgrunden."
            } else if result.paused == true {
                syncMessage = "⏸ Kvoten nådd — tryck igen om ca 15 min så fortsätter hämtningen."
            } else if let imported = result.imported, imported > 0 {
                syncMessage = "✅ \(imported) nya hämtade från \(providerName(provider))."
            } else {
                syncMessage = "✅ Redan i kapp — inget nytt hos \(providerName(provider))."
            }
            await load()
        } catch {
            if let apiError = error as? APIError, case .server(404) = apiError {
                syncMessage = "\(providerName(provider)) är inte kopplat ännu."
            } else {
                handleAPIError(error, session: session, message: &errorMessage)
            }
        }
    }

    private func activate() async {
        busy = "activate"
        healthMessage = nil
        defer { busy = nil }
        guard HealthKitService.shared.isAvailable else {
            healthMessage = "Hälsodata är inte tillgängligt på den här enheten."
            return
        }
        do {
            // Ingest-token mintas via API:t (samma som HAE använde)
            let created: IngestTokenOut = try await APIClient.shared.post(
                "api/integrations/apple-health/tokens",
                body: ["label": "Shapiqo-appen"]
            )
            HealthKitService.shared.configure(
                endpoint: "https://shapiqo.com/api/webhooks/apple-health",
                token: created.token
            )
            _ = await HealthKitService.shared.requestAuthorization()
            HealthKitService.shared.startObserversIfConfigured()
            healthConfigured = true
            healthMessage = "⏳ Hämtar de senaste 90 dagarna…"
            let counts = try await HealthKitService.shared.sync(days: 90)
            healthMessage = describe(counts)
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func runSync(days: Int, label: String) async {
        busy = label
        if days > 365 {
            healthMessage = "⏳ Hämtar hela historiken — kan ta flera minuter…"
        }
        defer { busy = nil }
        do {
            let counts = try await HealthKitService.shared.sync(days: days)
            healthMessage = describe(counts)
        } catch {
            healthMessage = error.localizedDescription
        }
    }

    private func describe(_ counts: [String: Int]) -> String {
        "✅ Synkat: \(counts["metrics"] ?? 0) mätvärden, "
        + "\(counts["sleep"] ?? 0) nätter, \(counts["workouts"] ?? 0) pass."
    }
}
