import SwiftUI
import Charts

/// Kosthistorik — samma överskådlighet som träningsuppföljningen:
/// snitt per dag, kalori- och proteingrafer mot målen och en
/// veckosammanställning med träffsäkerhet mot kalorimålet.
struct KostHistoryView: View {
    @ObservedObject var session: SessionStore

    @State private var days = 30
    @State private var summaries: [DaySummaryModel] = []
    @State private var targets: NutritionTargets?
    @State private var loading = false

    private static let periods: [(Int, String)] = [
        (7, "Vecka"), (30, "Månad"), (90, "Kvartal"), (365, "År"),
    ]

    private var weekly: Bool { days > 45 }

    private let isoFormat: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    var body: some View {
        VStack(spacing: 12) {
            Picker("Period", selection: $days) {
                ForEach(Self.periods, id: \.0) { value, label in
                    Text(label).tag(value)
                }
            }
            .pickerStyle(.segmented)

            if summaries.isEmpty {
                Text(loading ? "Laddar…" : "Ingen kost loggad i perioden.")
                    .foregroundColor(.secondary)
                    .padding(.vertical, 30)
            } else {
                averagesCard
                kcalChart
                proteinChart
                weekList
            }
        }
        .onAppear { Task { await load() } }
        .onChange(of: days) { _ in Task { await load() } }
    }

    // MARK: Snittkortet

    private var loggedDays: [DaySummaryModel] {
        summaries.filter { $0.entry_count > 0 }
    }

    private func average(_ value: (DaySummaryModel) -> Double) -> Double {
        let logged = loggedDays
        guard !logged.isEmpty else { return 0 }
        return logged.map(value).reduce(0, +) / Double(logged.count)
    }

    private var daysOnTarget: Int {
        guard let target = targets?.kcal else { return 0 }
        return loggedDays.filter { $0.kcal <= Double(target) }.count
    }

    private var averagesCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Snitt per loggad dag").font(.subheadline).bold()
            HStack {
                stat("🔥", "\(Int(average { $0.kcal }))", "kcal")
                stat("🥩", "\(Int(average { $0.protein_g }))", "protein")
                stat("🍞", "\(Int(average { $0.carbs_g }))", "kolh.")
                stat("🧈", "\(Int(average { $0.fat_g }))", "fett")
            }
            HStack {
                stat("📅", "\(loggedDays.count) av \(days)", "dagar loggade")
                if targets != nil {
                    stat("🎯", "\(daysOnTarget)/\(loggedDays.count)", "inom målet")
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    private func stat(_ icon: String, _ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(icon).font(.caption)
            Text(value).font(.subheadline).bold().monospacedDigit()
            Text(label).font(.caption2).foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: Grafer

    private struct ChartPoint: Identifiable {
        var id: Date { day }
        let day: Date
        let value: Double
    }

    private func points(_ value: (DaySummaryModel) -> Double) -> [ChartPoint] {
        let daily = loggedDays.compactMap { entry -> ChartPoint? in
            guard let day = isoFormat.date(from: entry.day) else { return nil }
            return ChartPoint(day: day, value: value(entry))
        }
        .sorted { $0.day < $1.day }
        guard weekly else { return daily }
        var calendar = Calendar(identifier: .iso8601)
        calendar.firstWeekday = 2
        var perWeek: [Date: [Double]] = [:]
        for point in daily {
            let week = calendar.date(
                from: calendar.dateComponents(
                    [.yearForWeekOfYear, .weekOfYear], from: point.day)
            ) ?? point.day
            perWeek[week, default: []].append(point.value)
        }
        return perWeek.map { week, values in
            ChartPoint(day: week, value: values.reduce(0, +) / Double(values.count))
        }
        .sorted { $0.day < $1.day }
    }

    private var kcalChart: some View {
        chartCard("🔥 Kalorier per \(weekly ? "vecka (snitt/dag)" : "dag")") {
            let data = points { $0.kcal }
            let target = targets.map { Double($0.kcal) }
            Chart(data) { point in
                BarMark(
                    x: .value("Dag", point.day, unit: weekly ? .weekOfYear : .day),
                    y: .value("kcal", point.value)
                )
                .foregroundStyle(
                    target.map { point.value > $0 } == true
                        ? Color.red.opacity(0.7) : Color.green.opacity(0.75)
                )
                if let target = target {
                    RuleMark(y: .value("Mål", target))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var proteinChart: some View {
        chartCard("🥩 Protein per \(weekly ? "vecka (snitt/dag)" : "dag")") {
            let data = points { $0.protein_g }
            let target = targets.map { Double($0.protein_g) }
            Chart(data) { point in
                BarMark(
                    x: .value("Dag", point.day, unit: weekly ? .weekOfYear : .day),
                    y: .value("g", point.value)
                )
                .foregroundStyle(
                    target.map { point.value >= $0 } == true
                        ? Color.green.opacity(0.75) : Color.orange.opacity(0.7)
                )
                if let target = target {
                    RuleMark(y: .value("Mål", target))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private func chartCard<Content: View>(
        _ title: String, @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.subheadline).bold()
            content().frame(height: 140)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    // MARK: Veckosammanställningen

    private struct WeekSummary: Identifiable {
        let id: String
        let title: String
        let avgKcal: Int
        let avgProtein: Int
        let logged: Int
        let onTarget: Bool?
    }

    private var weekSummaries: [WeekSummary] {
        var calendar = Calendar(identifier: .iso8601)
        calendar.firstWeekday = 2
        let dayFormat = DateFormatter()
        dayFormat.locale = Locale(identifier: "sv_SE")
        dayFormat.dateFormat = "d MMM"

        var groups: [(start: Date, items: [DaySummaryModel])] = []
        for entry in loggedDays.sorted(by: { $0.day > $1.day }) {
            guard let day = isoFormat.date(from: entry.day) else { continue }
            let week = calendar.date(
                from: calendar.dateComponents(
                    [.yearForWeekOfYear, .weekOfYear], from: day)
            ) ?? day
            if let index = groups.firstIndex(where: { $0.start == week }) {
                groups[index].items.append(entry)
            } else {
                groups.append((week, [entry]))
            }
        }
        return groups.map { group in
            let avgKcal = group.items.map { $0.kcal }.reduce(0, +) / Double(group.items.count)
            let avgProtein = group.items.map { $0.protein_g }.reduce(0, +) / Double(group.items.count)
            let week = calendar.component(.weekOfYear, from: group.start)
            return WeekSummary(
                id: group.start.description,
                title: "v.\(week) · \(dayFormat.string(from: group.start))",
                avgKcal: Int(avgKcal),
                avgProtein: Int(avgProtein),
                logged: group.items.count,
                onTarget: targets.map { avgKcal <= Double($0.kcal) }
            )
        }
    }

    private var weekList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Vecka för vecka").font(.subheadline).bold()
            ForEach(weekSummaries) { week in
                HStack {
                    Circle()
                        .fill(week.onTarget == nil ? Color.gray
                              : week.onTarget! ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(week.title).font(.caption)
                    Spacer()
                    Text("\(week.avgKcal) kcal · P \(week.avgProtein) g · \(week.logged) dgr")
                        .font(.caption).foregroundColor(.secondary)
                        .monospacedDigit()
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    // MARK: Data

    private func load() async {
        loading = true
        defer { loading = false }
        summaries = (try? await APIClient.shared.get(
            "api/meals/summary", query: ["days": String(days)]
        )) ?? []
        targets = try? await APIClient.shared.get("api/nutrition-targets")
    }
}
