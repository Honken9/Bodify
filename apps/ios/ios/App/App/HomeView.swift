import SwiftUI

/// Hemskärmen: dagens siffror med dagbläddring — kalorier mot målet,
/// steg, vilopuls, sömn m.m. Samma data som webbens hemskärm.
struct HomeView: View {
    @ObservedObject var session: SessionStore

    @State private var dayOffset = 0
    @State private var metrics: [String: MetricValue] = [:]
    @State private var dayLog: DayLog?
    @State private var errorMessage: String?
    @State private var loading = false

    private var day: Date {
        Calendar.current.date(byAdding: .day, value: dayOffset, to: Date()) ?? Date()
    }

    private var dayString: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: day)
    }

    private var dayLabel: String {
        if dayOffset == 0 { return "Idag" }
        if dayOffset == -1 { return "Igår" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "sv_SE")
        f.dateFormat = "EEE d MMM"
        return f.string(from: day)
    }

    @State private var period = 0  // 0 = dag, sedan vecka/månad/kvartal/år

    private static let periods: [(String, Int, String)] = [
        ("Dag", 1, "day"),
        ("Vecka", 7, "week"),
        ("Månad", 30, "month"),
        ("Kvartal", 90, "quarter"),
        ("År", 365, "year"),
    ]

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 12) {
                    Picker("Period", selection: $period) {
                        ForEach(0..<Self.periods.count, id: \.self) { index in
                            Text(Self.periods[index].0).tag(index)
                        }
                    }
                    .pickerStyle(.segmented)

                    if period == 0 {
                        dayPicker
                        if let message = errorMessage {
                            ErrorBanner(message: message)
                        }
                        calorieCard
                        metricsGrid
                    } else {
                        TrendsView(
                            session: session,
                            days: Self.periods[period].1,
                            periodKey: Self.periods[period].2
                        )
                        .id(period)
                    }
                }
                .padding()
            }
            .navigationTitle("Shapiqo")
            .refreshable { await load() }
        }
        .navigationViewStyle(.stack)
        .onAppear { Task { await load() } }
        .onChange(of: dayOffset) { _ in Task { await load() } }
    }

    private var dayPicker: some View {
        HStack {
            Button { dayOffset -= 1 } label: {
                Image(systemName: "chevron.left").padding(8)
            }
            Spacer()
            Text(dayLabel).font(.headline)
            Spacer()
            Button { dayOffset += 1 } label: {
                Image(systemName: "chevron.right").padding(8)
            }
            .disabled(dayOffset >= 0)
        }
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var calorieCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("🔥 Kalorier").font(.subheadline).foregroundColor(.secondary)
            if let log = dayLog {
                let eaten = log.totals.kcal
                let target = Double(log.targets.kcal)
                Text("\(Int(eaten)) / \(Int(target)) kcal")
                    .font(.title2).bold()
                ProgressView(value: min(eaten / max(target, 1), 1.0))
                    .tint(eaten > target ? .red : .green)
                Text("P \(Int(log.totals.protein_g)) g · K \(Int(log.totals.carbs_g)) g · F \(Int(log.totals.fat_g)) g")
                    .font(.footnote).foregroundColor(.secondary)
            } else {
                Text(loading ? "Laddar…" : "Ingen kost loggad")
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(14)
    }

    private struct MetricCard: Identifiable {
        let id: String
        let icon: String
        let label: String
        let unit: String
        let decimals: Int
    }

    private static let cards: [MetricCard] = [
        MetricCard(id: "steps", icon: "👟", label: "Steg", unit: "", decimals: 0),
        MetricCard(id: "resting_hr", icon: "❤️", label: "Vilopuls", unit: "bpm", decimals: 0),
        MetricCard(id: "weight", icon: "⚖️", label: "Vikt", unit: "kg", decimals: 1),
        MetricCard(id: "vo2max", icon: "🫁", label: "VO₂max", unit: "", decimals: 1),
        MetricCard(id: "spo2", icon: "🩸", label: "SpO₂", unit: "%", decimals: 0),
        MetricCard(id: "active_kcal", icon: "⚡", label: "Aktiv energi", unit: "kcal", decimals: 0),
        MetricCard(id: "exercise_min", icon: "⏱", label: "Träningsmin", unit: "min", decimals: 0),
        MetricCard(id: "flights_climbed", icon: "🪜", label: "Trappor", unit: "", decimals: 0),
    ]

    private var metricsGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ForEach(Self.cards) { card in
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(card.icon) \(card.label)")
                        .font(.caption).foregroundColor(.secondary)
                    if let metric = metrics[card.id] {
                        Text(formatted(metric.value, decimals: card.decimals)
                             + (card.unit.isEmpty ? "" : " \(card.unit)"))
                            .font(.title3).bold()
                    } else {
                        Text("–").font(.title3).foregroundColor(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(Color(.secondarySystemBackground))
                .cornerRadius(12)
            }
        }
    }

    private func formatted(_ value: Double, decimals: Int) -> String {
        decimals == 0
            ? String(Int(value.rounded()))
            : String(format: "%.\(decimals)f", value)
    }

    private func load() async {
        loading = true
        errorMessage = nil
        defer { loading = false }
        do {
            metrics = try await APIClient.shared.get(
                "api/metrics/day", query: ["day": dayString]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
            return
        }
        do {
            dayLog = try await APIClient.shared.get(
                "api/meals", query: ["day": dayString]
            )
        } catch {
            dayLog = nil
        }
    }
}
