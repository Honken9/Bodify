import SwiftUI

/// Träningsfliken: växlar mellan passlistan och kartan, med manuell
/// passloggning via +.
struct TrainingTab: View {
    @ObservedObject var session: SessionStore
    @State private var mode = 0
    @State private var showLog = false
    @State private var reloadKey = 0

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Picker("Vy", selection: $mode) {
                    Text("Lista").tag(0)
                    Text("🗺 Karta").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.vertical, 6)

                if mode == 0 {
                    WorkoutsView(session: session)
                        .id(reloadKey)
                } else {
                    MapView(session: session)
                }
            }
            .navigationTitle("Träning")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showLog = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showLog) {
                LogWorkoutSheet(session: session) {
                    showLog = false
                    reloadKey += 1
                    mode = 0
                }
            }
        }
        .navigationViewStyle(.stack)
    }
}

/// Manuell passloggning — för pass utan klocka/telefon (t.ex. fotboll,
/// padel). Skapar en aktivitet via API:t, källa "manual".
struct LogWorkoutSheet: View {
    @ObservedObject var session: SessionStore
    let onLogged: () -> Void

    @State private var type = "other"
    @State private var name = ""
    @State private var startedAt = Date()
    @State private var minutes = 45
    @State private var distanceKm = ""
    @State private var busy = false
    @State private var errorMessage: String?

    private static let types: [(String, String)] = [
        ("run", "🏃 Löpning"), ("ride", "🚴 Cykling"), ("walk", "🚶 Promenad"),
        ("swim", "🏊 Simning"), ("other", "💪 Annat"),
    ]

    var body: some View {
        NavigationView {
            Form {
                if let message = errorMessage {
                    ErrorBanner(message: message)
                }
                Picker("Typ", selection: $type) {
                    ForEach(Self.types, id: \.0) { key, label in
                        Text(label).tag(key)
                    }
                }
                TextField("Namn, t.ex. Padel med Demus", text: $name)
                DatePicker("Start", selection: $startedAt)
                Stepper("\(minutes) minuter", value: $minutes, in: 5...600, step: 5)
                TextField("Distans i km (valfritt)", text: $distanceKm)
                    .keyboardType(.decimalPad)
                Button(busy ? "Sparar…" : "💾 Logga passet") {
                    Task { await save() }
                }
                .disabled(busy)
            }
            .navigationTitle("Logga pass")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func save() async {
        busy = true
        errorMessage = nil
        defer { busy = false }
        let iso = ISO8601DateFormatter()
        var body: [String: Any] = [
            "type": type,
            "started_at": iso.string(from: startedAt),
            "duration_s": minutes * 60,
        ]
        let trimmedName = name.trimmingCharacters(in: .whitespaces)
        if !trimmedName.isEmpty { body["name"] = trimmedName }
        let km = Double(distanceKm.replacingOccurrences(of: ",", with: "."))
        if let km = km, km > 0 { body["distance_m"] = km * 1000 }
        do {
            let _: WorkoutModel = try await APIClient.shared.post(
                "api/cardio", body: body
            )
            onLogged()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}
