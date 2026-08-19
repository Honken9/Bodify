import SwiftUI

// MARK: - Modeller

struct SplitModel: Decodable, Identifiable {
    var id: Int { km ?? Int(distance_m) }
    let km: Int?
    let distance_m: Double
    let time_s: Double
    let pace_s_per_km: Double
    let hr: Double?
    let elev_diff_m: Double?
}

struct CardioDetail: Decodable {
    let id: String
    let type: String
    let source: String
    let name: String?
    let started_at: String
    let duration_s: Int
    let distance_m: Double?
    let avg_hr: Double?
    let max_hr: Double?
    let avg_pace_s_per_km: Double?
    let calories: Double?
    let polyline: String?
    let start: [Double]?
    let extras: [String: AnyDecodable]
    let splits: [SplitModel]
}

/// Tolerant JSON-värde (extras innehåller blandade tal/strängar)
struct AnyDecodable: Decodable {
    let value: Any

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else {
            value = ""
        }
    }

    var text: String {
        if let double = value as? Double {
            return double == double.rounded()
                ? String(Int(double)) : String(format: "%.1f", double)
        }
        return value as? String ?? ""
    }
}

// MARK: - Träningslistan, grupperad per vecka

struct WorkoutsView: View {
    @ObservedObject var session: SessionStore
    var onShowMap: ((String) -> Void)? = nil

    @State private var workouts: [WorkoutModel] = []
    @State private var detailId: String?
    @State private var errorMessage: String?

    static let icons: [String: String] = [
        "run": "🏃", "ride": "🚴", "walk": "🚶", "swim": "🏊",
        "strength": "🏋️", "other": "💪",
    ]

    static let sourceNames: [String: String] = [
        "withings": "Withings", "strava": "Strava",
        "apple_health": "Apple Health", "manual": "Manuellt",
        "shapiqo": "Shapiqo",
    ]

    private struct WeekGroup: Identifiable {
        let id: String
        let title: String
        let summary: String
        let workouts: [WorkoutModel]
    }

    private var weekGroups: [WeekGroup] {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        fallback.formatOptions = [.withInternetDateTime]

        var calendar = Calendar(identifier: .iso8601)
        calendar.locale = Locale(identifier: "sv_SE")

        func date(_ iso: String) -> Date {
            parser.date(from: iso) ?? fallback.date(from: iso) ?? Date()
        }

        var groups: [(key: String, start: Date, items: [WorkoutModel])] = []
        for workout in workouts {
            let day = date(workout.started_at)
            let week = calendar.component(.weekOfYear, from: day)
            let year = calendar.component(.yearForWeekOfYear, from: day)
            let key = "\(year)-v\(week)"
            if let index = groups.firstIndex(where: { $0.key == key }) {
                groups[index].items.append(workout)
            } else {
                let start = calendar.date(
                    from: calendar.dateComponents(
                        [.yearForWeekOfYear, .weekOfYear], from: day)
                ) ?? day
                groups.append((key, start, [workout]))
            }
        }

        let dayFormat = DateFormatter()
        dayFormat.locale = Locale(identifier: "sv_SE")
        dayFormat.dateFormat = "d MMM"

        return groups.map { group in
            let week = calendar.component(.weekOfYear, from: group.start)
            let end = calendar.date(byAdding: .day, value: 6, to: group.start) ?? group.start
            let km = group.items.compactMap { $0.distance_m }.reduce(0, +) / 1000
            let minutes = group.items.map { $0.duration_s }.reduce(0, +) / 60
            var parts = ["\(group.items.count) pass"]
            if km >= 0.1 { parts.append(String(format: "%.1f km", km)) }
            parts.append(minutes >= 60 ? "\(minutes / 60) h \(minutes % 60) min" : "\(minutes) min")
            return WeekGroup(
                id: group.key,
                title: "v.\(week) · \(dayFormat.string(from: group.start))–\(dayFormat.string(from: end))",
                summary: parts.joined(separator: " · "),
                workouts: group.items
            )
        }
    }

    var body: some View {
        List {
            if let message = errorMessage {
                ErrorBanner(message: message)
            }
            ForEach(weekGroups) { group in
                Section(header: HStack {
                    Text(group.title)
                    Spacer()
                    Text(group.summary).font(.caption2)
                }) {
                    ForEach(group.workouts) { workout in
                        Button {
                            detailId = workout.id
                        } label: {
                            HStack(alignment: .top, spacing: 10) {
                                Text(Self.icons[workout.type] ?? "💪")
                                    .font(.title3)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(workout.name ?? "Träning")
                                        .font(.subheadline).bold()
                                        .foregroundColor(.primary)
                                    Text(subtitle(for: workout))
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }
            }
            if workouts.isEmpty && errorMessage == nil {
                Text("Inga pass ännu.").foregroundColor(.secondary)
            }
        }
        .refreshable { await load() }
        .onAppear { Task { await load() } }
        .sheet(item: Binding(
            get: { detailId.map { WorkoutDetailRef(id: $0) } },
            set: { detailId = $0?.id }
        )) { ref in
            WorkoutDetailSheet(
                session: session, activityId: ref.id,
                onShowMap: onShowMap.map { callback in
                    { id in
                        detailId = nil
                        callback(id)
                    }
                }
            )
        }
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
        f.dateFormat = "EEE d MMM"
        return f.string(from: parsed)
    }

    private func load() async {
        errorMessage = nil
        do {
            workouts = try await APIClient.shared.get(
                "api/cardio", query: ["limit": "200"]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

struct WorkoutDetailRef: Identifiable {
    let id: String
}

// MARK: - Passdetaljer med km-varv

struct WorkoutDetailSheet: View {
    @ObservedObject var session: SessionStore
    let activityId: String
    let onShowMap: ((String) -> Void)?

    @State private var detail: CardioDetail?
    @State private var errorMessage: String?

    private static let extraLabels: [String: String] = [
        "total_elevation_gain": "Höjdmeter",
        "temperature": "Temperatur (°C)",
        "humidity": "Luftfuktighet (%)",
        "intensity": "Intensitet",
        "average_cadence": "Kadens",
        "suffer_score": "Ansträngning",
    ]

    var body: some View {
        NavigationView {
            List {
                if let message = errorMessage {
                    ErrorBanner(message: message)
                }
                if let detail = detail {
                    statsSection(detail)
                    if !detail.splits.isEmpty {
                        splitsSection(detail)
                    }
                    if detail.polyline != nil || detail.start != nil,
                       let onShowMap = onShowMap {
                        Button {
                            onShowMap(detail.id)
                        } label: {
                            Label("Visa på kartan", systemImage: "map.fill")
                        }
                    }
                } else if errorMessage == nil {
                    Text("Laddar…").foregroundColor(.secondary)
                }
            }
            .navigationTitle(detail?.name ?? "Pass")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear { Task { await load() } }
    }

    private func statsSection(_ detail: CardioDetail) -> some View {
        Section {
            statRow("Datum", value: String(detail.started_at.prefix(10)))
            if let distance = detail.distance_m, distance > 0 {
                statRow("Distans", value: String(format: "%.2f km", distance / 1000))
            }
            statRow("Tid", value: formatDuration(detail.duration_s))
            if let pace = detail.avg_pace_s_per_km {
                statRow("Snittempo", value: formatPace(pace) + " /km")
            }
            if let hr = detail.avg_hr {
                statRow("Snittpuls", value: "\(Int(hr)) bpm")
            }
            if let hr = detail.max_hr {
                statRow("Maxpuls", value: "\(Int(hr)) bpm")
            }
            if let kcal = detail.calories {
                statRow("Kalorier", value: "\(Int(kcal)) kcal")
            }
            ForEach(Self.extraLabels.keys.sorted(), id: \.self) { key in
                if let extra = detail.extras[key], !extra.text.isEmpty {
                    statRow(Self.extraLabels[key] ?? key, value: extra.text)
                }
            }
            statRow("Källa",
                    value: WorkoutsView.sourceNames[detail.source] ?? detail.source)
        }
    }

    private func statRow(_ label: String, value: String) -> some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value).bold()
        }
        .font(.subheadline)
    }

    /// Km-varv med tempostaplar — snabbaste varvet har full stapel
    private func splitsSection(_ detail: CardioDetail) -> some View {
        Section("Km-varv") {
            let fastest = detail.splits.map { $0.pace_s_per_km }.min() ?? 1
            ForEach(detail.splits) { split in
                HStack(spacing: 8) {
                    Text(split.km.map { "\($0)" } ?? "–")
                        .font(.caption).monospacedDigit()
                        .frame(width: 24, alignment: .trailing)
                    GeometryReader { geometry in
                        RoundedRectangle(cornerRadius: 3)
                            .fill(Color.accentColor.opacity(0.75))
                            .frame(width: geometry.size.width
                                   * CGFloat(fastest / max(split.pace_s_per_km, 1)))
                    }
                    .frame(height: 14)
                    Text(formatPace(split.pace_s_per_km))
                        .font(.caption).monospacedDigit()
                        .frame(width: 44, alignment: .trailing)
                    Text(split.hr.map { "♥\(Int($0))" } ?? "")
                        .font(.caption2).foregroundColor(.secondary)
                        .frame(width: 38, alignment: .trailing)
                }
            }
        }
    }

    private func formatDuration(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        return hours > 0 ? "\(hours) h \(minutes) min" : "\(minutes) min"
    }

    private func formatPace(_ secondsPerKm: Double) -> String {
        let total = Int(secondsPerKm.rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    private func load() async {
        do {
            detail = try await APIClient.shared.get("api/cardio/\(activityId)")
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}
