import SwiftUI

/// Måltider: dagens logg + fritextloggning ("Big Mac, mellan pommes och
/// cola zero") — samma AI-tolkning som webben, via /api/meals/quick-log.
struct MealsView: View {
    @ObservedObject var session: SessionStore

    @State private var dayLog: DayLog?
    @State private var text = ""
    @State private var meal = "lunch"
    @State private var busy = false
    @State private var resultMessage: String?
    @State private var errorMessage: String?

    private static let mealNames: [(String, String)] = [
        ("breakfast", "Frukost"),
        ("lunch", "Lunch"),
        ("dinner", "Middag"),
        ("snack", "Mellanmål"),
    ]

    private var todayString: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }

    var body: some View {
        NavigationView {
            List {
                Section("Logga med text") {
                    TextField("t.ex. Big Mac, mellan pommes, cola zero", text: $text)
                    Picker("Måltid", selection: $meal) {
                        ForEach(Self.mealNames, id: \.0) { key, name in
                            Text(name).tag(key)
                        }
                    }
                    Button(busy ? "Tolkar…" : "🍽 Logga") {
                        Task { await quickLog() }
                    }
                    .disabled(busy || text.trimmingCharacters(in: .whitespaces).count < 2)
                    if let message = resultMessage {
                        Text(message).font(.footnote).foregroundColor(.secondary)
                    }
                    if let message = errorMessage {
                        Text(message).font(.footnote).foregroundColor(.red)
                    }
                }

                if let log = dayLog {
                    Section(footer: totalsFooter(log)) {
                        if log.entries.isEmpty {
                            Text("Inget loggat idag ännu.")
                                .foregroundColor(.secondary)
                        }
                        ForEach(log.entries) { entry in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(entry.food_item.name)
                                        .font(.subheadline).bold()
                                    Text("\(mealName(entry.meal)) · \(Int(entry.grams)) g")
                                        .font(.caption).foregroundColor(.secondary)
                                }
                                Spacer()
                                Text("\(Int(entry.kcal)) kcal")
                                    .font(.subheadline)
                            }
                        }
                        .onDelete { indexSet in
                            Task { await deleteEntries(at: indexSet) }
                        }
                    }
                }
            }
            .navigationTitle("Måltider")
            .refreshable { await load() }
        }
        .navigationViewStyle(.stack)
        .onAppear { Task { await load() } }
    }

    private func mealName(_ key: String) -> String {
        Self.mealNames.first { $0.0 == key }?.1 ?? key
    }

    private func totalsFooter(_ log: DayLog) -> some View {
        Text("Totalt \(Int(log.totals.kcal)) av \(log.targets.kcal) kcal · "
             + "P \(Int(log.totals.protein_g)) · K \(Int(log.totals.carbs_g)) · "
             + "F \(Int(log.totals.fat_g))")
    }

    private func load() async {
        errorMessage = nil
        do {
            dayLog = try await APIClient.shared.get(
                "api/meals", query: ["day": todayString]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func quickLog() async {
        busy = true
        resultMessage = nil
        errorMessage = nil
        defer { busy = false }
        do {
            let result: QuickLogResult = try await APIClient.shared.post(
                "api/meals/quick-log",
                body: ["text": text.trimmingCharacters(in: .whitespaces),
                       "eaten_on": todayString,
                       "meal": meal]
            )
            var parts: [String] = result.logged.map {
                "✅ \($0.name) \(Int($0.grams)) g (\(Int($0.kcal)) kcal)"
            }
            if !result.missing.isEmpty {
                parts.append("❓ Hittade inte: \(result.missing.joined(separator: ", "))")
            }
            resultMessage = parts.isEmpty ? "Inget kunde tolkas." : parts.joined(separator: "\n")
            text = ""
            await load()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func deleteEntries(at indexSet: IndexSet) async {
        guard let entries = dayLog?.entries else { return }
        for index in indexSet {
            let entry = entries[index]
            try? await APIClient.shared.delete("api/meals/\(entry.id)")
        }
        await load()
    }
}
