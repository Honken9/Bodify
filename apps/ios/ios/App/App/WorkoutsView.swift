import SwiftUI

/// Träning: senaste passen från alla källor (Withings, Strava, Apple
/// Health, Shapiqo) — samma lista som webbens historik.
struct WorkoutsView: View {
    @ObservedObject var session: SessionStore

    @State private var workouts: [WorkoutModel] = []
    @State private var errorMessage: String?

    private static let icons: [String: String] = [
        "run": "🏃", "ride": "🚴", "walk": "🚶", "swim": "🏊",
        "strength": "🏋️", "other": "💪",
    ]

    private static let sourceNames: [String: String] = [
        "withings": "Withings", "strava": "Strava",
        "apple_health": "Apple Health", "manual": "Manuellt",
        "shapiqo": "Shapiqo",
    ]

    var body: some View {
        List {
            if let message = errorMessage {
                ErrorBanner(message: message)
            }
            ForEach(workouts) { workout in
                HStack(alignment: .top, spacing: 10) {
                    Text(Self.icons[workout.type] ?? "💪")
                        .font(.title3)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(workout.name ?? "Träning")
                            .font(.subheadline).bold()
                        Text(subtitle(for: workout))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 2)
            }
            if workouts.isEmpty && errorMessage == nil {
                Text("Inga pass ännu.").foregroundColor(.secondary)
            }
        }
        .refreshable { await load() }
        .onAppear { Task { await load() } }
    }

    private func subtitle(for workout: WorkoutModel) -> String {
        var parts: [String] = [formatDate(workout.started_at)]
        if let distance = workout.distance_m, distance > 0 {
            parts.append(String(format: "%.1f km", distance / 1000))
        }
        parts.append("\(workout.duration_s / 60) min")
        if let hr = workout.avg_hr {
            parts.append("♥ \(Int(hr))")
        }
        if let source = Self.sourceNames[workout.source] {
            parts.append("via \(source)")
        }
        return parts.joined(separator: " · ")
    }

    private func formatDate(_ iso: String) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = parser.date(from: iso)
        if date == nil {
            parser.formatOptions = [.withInternetDateTime]
            date = parser.date(from: iso)
        }
        guard let parsed = date else { return iso }
        let f = DateFormatter()
        f.locale = Locale(identifier: "sv_SE")
        f.dateFormat = "d MMM yyyy"
        return f.string(from: parsed)
    }

    private func load() async {
        errorMessage = nil
        do {
            workouts = try await APIClient.shared.get(
                "api/cardio", query: ["limit": "100"]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}
