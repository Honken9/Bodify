import SwiftUI
import Charts

/// Trendgrafer för hemvyn — vecka/månad/kvartal/år. Serierna hämtas
/// från metrics-API:t, aggregeras per dag (bästa källa per dag för
/// steg, snitt för mätvärden) och buntas per vecka för långa perioder.

struct TrendPoint: Identifiable {
    var id: Date { day }
    let day: Date
    let value: Double
}

struct MetricSeriesPoint: Decodable {
    let measured_at: String
    let value: Double
}

struct DashboardSummary: Decodable {
    let strength_sessions: Int
    let cardio_sessions: Int
    let cardio_distance_km: Double
    let avg_kcal: Int?
    let weight_delta_kg: Double?
    let active_days: Int
}

struct TrendsView: View {
    @ObservedObject var session: SessionStore
    let days: Int          // 7, 30, 90 eller 365
    let periodKey: String  // week/month/quarter/year

    @State private var summary: DashboardSummary?
    @State private var weight: [TrendPoint] = []
    @State private var steps: [TrendPoint] = []
    @State private var restingHr: [TrendPoint] = []
    @State private var vo2max: [TrendPoint] = []
    @State private var kcal: [TrendPoint] = []
    @State private var kcalTarget: Double?
    @State private var loading = false

    /// Långa perioder buntas per vecka så graferna hålls luftiga
    private var weekly: Bool { days > 45 }

    var body: some View {
        VStack(spacing: 12) {
            if let summary = summary {
                summaryCard(summary)
            }
            if !kcal.isEmpty {
                chartCard("🔥 Kalorier per \(weekly ? "vecka (snitt/dag)" : "dag")",
                          latest: kcal.last.map { "\(Int($0.value)) kcal" }) {
                    Chart(kcal) { point in
                        BarMark(
                            x: .value("Dag", point.day, unit: weekly ? .weekOfYear : .day),
                            y: .value("kcal", point.value)
                        )
                        .foregroundStyle(
                            kcalTarget.map { point.value > $0 } == true
                                ? Color.red.opacity(0.7) : Color.green.opacity(0.75)
                        )
                        if let target = kcalTarget {
                            RuleMark(y: .value("Mål", target))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            if !steps.isEmpty {
                chartCard("👟 Steg per \(weekly ? "vecka (snitt/dag)" : "dag")",
                          latest: steps.last.map { "\(Int($0.value))" }) {
                    Chart(steps) { point in
                        BarMark(
                            x: .value("Dag", point.day, unit: weekly ? .weekOfYear : .day),
                            y: .value("Steg", point.value)
                        )
                        .foregroundStyle(Color.accentColor.opacity(0.75))
                    }
                }
            }
            if !weight.isEmpty {
                chartCard("⚖️ Vikt", latest: weight.last.map {
                    String(format: "%.1f kg", $0.value)
                }) {
                    Chart(weight) { point in
                        LineMark(x: .value("Dag", point.day),
                                 y: .value("Kg", point.value))
                            .interpolationMethod(.monotone)
                        PointMark(x: .value("Dag", point.day),
                                  y: .value("Kg", point.value))
                            .symbolSize(12)
                    }
                    .chartYScale(domain: yDomain(weight, padding: 1))
                }
            }
            if !restingHr.isEmpty {
                chartCard("❤️ Vilopuls", latest: restingHr.last.map {
                    "\(Int($0.value)) bpm"
                }) {
                    Chart(restingHr) { point in
                        LineMark(x: .value("Dag", point.day),
                                 y: .value("bpm", point.value))
                            .interpolationMethod(.monotone)
                            .foregroundStyle(.red)
                    }
                    .chartYScale(domain: yDomain(restingHr, padding: 3))
                }
            }
            if !vo2max.isEmpty {
                chartCard("🫁 VO₂max", latest: vo2max.last.map {
                    String(format: "%.1f", $0.value)
                }) {
                    Chart(vo2max) { point in
                        LineMark(x: .value("Dag", point.day),
                                 y: .value("VO₂max", point.value))
                            .interpolationMethod(.monotone)
                            .foregroundStyle(.teal)
                        PointMark(x: .value("Dag", point.day),
                                  y: .value("VO₂max", point.value))
                            .symbolSize(12)
                            .foregroundStyle(.teal)
                    }
                    .chartYScale(domain: yDomain(vo2max, padding: 2))
                }
            }
            if loading && summary == nil {
                ProgressView().padding(.vertical, 30)
            }
        }
        .onAppear { Task { await load() } }
        .onChange(of: days) { _ in Task { await load() } }
    }

    // MARK: Kort

    private func summaryCard(_ summary: DashboardSummary) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Perioden i korthet").font(.subheadline).bold()
            HStack {
                stat("🏋️", "\(summary.strength_sessions + summary.cardio_sessions)", "pass")
                stat("🏃", String(format: "%.0f", summary.cardio_distance_km), "km")
                stat("📅", "\(summary.active_days)", "aktiva dgr")
                if let kcal = summary.avg_kcal {
                    stat("🔥", "\(kcal)", "kcal/dag")
                }
                if let delta = summary.weight_delta_kg {
                    stat("⚖️", String(format: "%+.1f", delta), "kg")
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

    private func chartCard<Content: View>(
        _ title: String, latest: String?, @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title).font(.subheadline).bold()
                Spacer()
                if let latest = latest {
                    Text(latest).font(.subheadline).foregroundColor(.secondary)
                }
            }
            content()
                .frame(height: 140)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    private func yDomain(_ points: [TrendPoint], padding: Double) -> ClosedRange<Double> {
        let values = points.map { $0.value }
        let low = (values.min() ?? 0) - padding
        let high = (values.max() ?? 1) + padding
        return low...max(high, low + 1)
    }

    // MARK: Data

    private func load() async {
        loading = true
        defer { loading = false }

        summary = try? await APIClient.shared.get(
            "api/dashboard", query: ["period": periodKey]
        )

        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -(days - 1), to: end) ?? end
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        let query = ["start": f.string(from: start), "end": f.string(from: end)]

        async let weightSeries = series("weight", query: query)
        async let stepsSeries = series("steps", query: query)
        async let hrSeries = series("resting_hr", query: query)
        async let vo2Series = series("vo2max", query: query)
        weight = bucket(await weightSeries, aggregate: .average)
        steps = bucket(await stepsSeries, aggregate: .maxPerDay)
        restingHr = bucket(await hrSeries, aggregate: .average)
        vo2max = bucket(await vo2Series, aggregate: .average)

        // Kalorier: dagssummor + mål
        let summaries: [DaySummaryModel] = (try? await APIClient.shared.get(
            "api/meals/summary", query: ["days": String(days)]
        )) ?? []
        let points = summaries.compactMap { entry -> TrendPoint? in
            guard let day = f.date(from: entry.day) else { return nil }
            return TrendPoint(day: day, value: entry.kcal)
        }
        kcal = weekly ? bucketWeekly(points, aggregate: .average) : points.sorted { $0.day < $1.day }
        let targets: NutritionTargets? = try? await APIClient.shared.get("api/nutrition-targets")
        kcalTarget = targets.map { Double($0.kcal) }
    }

    private func series(_ metric: String, query: [String: String]) async -> [MetricSeriesPoint] {
        (try? await APIClient.shared.get("api/metrics/\(metric)", query: query)) ?? []
    }

    private enum Aggregate {
        case average, maxPerDay
    }

    /// Rådata → en punkt per dag (och per vecka för långa perioder)
    private func bucket(_ raw: [MetricSeriesPoint], aggregate: Aggregate) -> [TrendPoint] {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fallback = ISO8601DateFormatter()
        fallback.formatOptions = [.withInternetDateTime]
        var perDay: [Date: [Double]] = [:]
        for point in raw {
            guard let stamp = parser.date(from: point.measured_at)
                ?? fallback.date(from: point.measured_at) else { continue }
            let day = Calendar.current.startOfDay(for: stamp)
            perDay[day, default: []].append(point.value)
        }
        let daily = perDay.map { day, values -> TrendPoint in
            switch aggregate {
            case .average:
                return TrendPoint(day: day, value: values.reduce(0, +) / Double(values.count))
            case .maxPerDay:
                return TrendPoint(day: day, value: values.max() ?? 0)
            }
        }
        .sorted { $0.day < $1.day }
        return weekly ? bucketWeekly(daily, aggregate: .average) : daily
    }

    /// Dagspunkter → veckosnitt (måndagsdatum som x-värde)
    private func bucketWeekly(_ daily: [TrendPoint], aggregate: Aggregate) -> [TrendPoint] {
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
            TrendPoint(day: week, value: values.reduce(0, +) / Double(values.count))
        }
        .sorted { $0.day < $1.day }
    }
}
