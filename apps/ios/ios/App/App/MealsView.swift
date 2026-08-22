import SwiftUI

/// Kost 2.0 — hela kostflödet native: dagbläddring med jämförelse,
/// kaloriring mot målet, foto-AI, streckkodsskanner, sökning,
/// fritextloggning, mikronäringsämnen och måljustering.
struct MealsView: View {
    @ObservedObject var session: SessionStore

    @State private var dayOffset = 0
    @State private var dayLog: DayLog?
    @State private var summary: [DaySummaryModel] = []
    @State private var errorMessage: String?
    @State private var activeSheet: KostSheet?
    @State private var showMicros = false

    enum KostSheet: String, Identifiable {
        case photo, barcode, search, quicklog, targets
        var id: String { rawValue }
    }

    private var day: Date {
        Calendar.current.date(byAdding: .day, value: dayOffset, to: Date()) ?? Date()
    }

    var dayString: String {
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

    private static let mealNames: [(String, String)] = [
        ("breakfast", "Frukost"), ("lunch", "Lunch"),
        ("dinner", "Middag"), ("snack", "Mellanmål"),
    ]

    static func mealName(_ key: String) -> String {
        mealNames.first { $0.0 == key }?.1 ?? key
    }

    @State private var mode = 0  // 0 = idag, 1 = historik

    var body: some View {
        NavigationView {
            Group {
                if mode == 0 {
                    List {
                        modePicker
                        daySection
                        compareSection
                        ringSection
                        logButtons
                        entriesSection
                        microsSection
                    }
                    .listStyle(.insetGrouped)
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            modePicker
                            KostHistoryView(session: session)
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Kost")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        activeSheet = .targets
                    } label: {
                        Image(systemName: "target")
                    }
                }
            }
            .refreshable { await load() }
            .sheet(item: $activeSheet) { sheet in
                switch sheet {
                case .photo:
                    PhotoMealSheet(session: session, dayString: dayString) {
                        activeSheet = nil
                        Task { await load() }
                    }
                case .barcode:
                    BarcodeSheet(session: session, dayString: dayString) {
                        activeSheet = nil
                        Task { await load() }
                    }
                case .search:
                    FoodSearchSheet(session: session, dayString: dayString) {
                        activeSheet = nil
                        Task { await load() }
                    }
                case .quicklog:
                    QuickLogSheet(session: session, dayString: dayString) {
                        activeSheet = nil
                        Task { await load() }
                    }
                case .targets:
                    TargetsSheet(session: session, current: dayLog?.targets) {
                        activeSheet = nil
                        Task { await load() }
                    }
                }
            }
        }
        .navigationViewStyle(.stack)
        .onAppear { Task { await load() } }
        .onChange(of: dayOffset) { _ in Task { await loadDay() } }
    }

    // MARK: Sektioner

    private var modePicker: some View {
        Picker("Vy", selection: $mode) {
            Text("Idag").tag(0)
            Text("📊 Historik").tag(1)
        }
        .pickerStyle(.segmented)
        .listRowSeparator(.hidden)
    }

    private var daySection: some View {
        HStack {
            Button { dayOffset -= 1 } label: {
                Image(systemName: "chevron.left").padding(6)
            }
            .buttonStyle(.plain)
            Spacer()
            Text(dayLabel).font(.headline)
            Spacer()
            Button { dayOffset += 1 } label: {
                Image(systemName: "chevron.right").padding(6)
            }
            .buttonStyle(.plain)
            .disabled(dayOffset >= 0)
        }
        .listRowSeparator(.hidden)
    }

    /// 14 dagars staplar — tryck på en stapel för att hoppa dit
    private var compareSection: some View {
        Group {
            if !summary.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .bottom, spacing: 3) {
                        ForEach(summary) { entry in
                            let target = Double(dayLog?.targets.kcal ?? 2000)
                            let height = max(6, min(entry.kcal / max(target, 1), 1.4) * 40)
                            let offset = offsetFor(entry.day)
                            Button {
                                dayOffset = offset
                            } label: {
                                RoundedRectangle(cornerRadius: 2)
                                    .fill(offset == dayOffset
                                          ? Color.accentColor
                                          : entry.kcal > target
                                              ? Color.red.opacity(0.6)
                                              : Color.green.opacity(0.6))
                                    .frame(height: height)
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .frame(height: 58, alignment: .bottom)
                    if let diff = comparedToYesterday {
                        Text(diff).font(.caption2).foregroundColor(.secondary)
                    }
                }
                .listRowSeparator(.hidden)
            }
        }
    }

    private func offsetFor(_ dayIso: String) -> Int {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        guard let date = f.date(from: dayIso) else { return 0 }
        let days = Calendar.current.dateComponents(
            [.day], from: Calendar.current.startOfDay(for: date),
            to: Calendar.current.startOfDay(for: Date())
        ).day ?? 0
        return -days
    }

    private var comparedToYesterday: String? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        let previous = Calendar.current.date(byAdding: .day, value: -1, to: day) ?? day
        guard let today = summary.first(where: { $0.day == dayString }),
              let before = summary.first(where: { $0.day == f.string(from: previous) })
        else { return nil }
        let diff = Int(today.kcal - before.kcal)
        let sign = diff >= 0 ? "+" : ""
        return "Jämfört med dagen innan: \(sign)\(diff) kcal"
    }

    private var ringSection: some View {
        Group {
            if let log = dayLog {
                let eaten = log.totals.kcal
                let target = Double(log.targets.kcal)
                HStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .stroke(Color.gray.opacity(0.2), lineWidth: 9)
                        Circle()
                            .trim(from: 0, to: CGFloat(min(eaten / max(target, 1), 1)))
                            .stroke(eaten > target ? Color.red : Color.green,
                                    style: StrokeStyle(lineWidth: 9, lineCap: .round))
                            .rotationEffect(.degrees(-90))
                        VStack(spacing: 0) {
                            Text("\(Int(eaten))").font(.headline)
                            Text("kcal").font(.caption2).foregroundColor(.secondary)
                        }
                    }
                    .frame(width: 84, height: 84)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(Int(max(target - eaten, 0))) kcal kvar av \(Int(target))")
                            .font(.subheadline).bold()
                        Text("Protein \(Int(log.totals.protein_g)) / \(log.targets.protein_g) g")
                            .font(.caption).foregroundColor(.secondary)
                        Text("Kolhydrater \(Int(log.totals.carbs_g)) / \(log.targets.carbs_g) g")
                            .font(.caption).foregroundColor(.secondary)
                        Text("Fett \(Int(log.totals.fat_g)) / \(log.targets.fat_g) g")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
                .listRowSeparator(.hidden)
            }
        }
    }

    private var logButtons: some View {
        HStack(spacing: 8) {
            kostButton("📷", "Fota") { activeSheet = .photo }
            kostButton("barcode", "Skanna", system: true) { activeSheet = .barcode }
            kostButton("🔍", "Sök") { activeSheet = .search }
            kostButton("⚡", "Fritext") { activeSheet = .quicklog }
        }
        .listRowSeparator(.hidden)
    }

    private func kostButton(
        _ icon: String, _ label: String, system: Bool = false,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                if system {
                    Image(systemName: icon).font(.title3)
                } else {
                    Text(icon).font(.title3)
                }
                Text(label).font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }

    private var entriesSection: some View {
        Group {
            if let message = errorMessage {
                ErrorBanner(message: message)
            }
            if let log = dayLog {
                ForEach(Self.mealNames, id: \.0) { key, name in
                    let meals = log.entries.filter { $0.meal == key }
                    if !meals.isEmpty {
                        Section(name) {
                            ForEach(meals) { entry in
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(entry.food_item.name)
                                            .font(.subheadline).bold()
                                        Text("\(Int(entry.grams)) g · P \(Int(entry.protein_g)) K \(Int(entry.carbs_g)) F \(Int(entry.fat_g))")
                                            .font(.caption).foregroundColor(.secondary)
                                    }
                                    Spacer()
                                    Text("\(Int(entry.kcal)) kcal").font(.subheadline)
                                }
                            }
                            .onDelete { indexSet in
                                Task {
                                    for index in indexSet {
                                        try? await APIClient.shared.delete(
                                            "api/meals/\(meals[index].id)")
                                    }
                                    await load()
                                }
                            }
                        }
                    }
                }
                if log.entries.isEmpty {
                    Text("Inget loggat den här dagen.")
                        .foregroundColor(.secondary)
                }
            }
        }
    }

    private var microsSection: some View {
        Group {
            if let micros = dayLog?.micros, !micros.isEmpty {
                Section {
                    Button(showMicros ? "Dölj näringsämnen" : "🧪 Visa näringsämnen (\(micros.count))") {
                        showMicros.toggle()
                    }
                    if showMicros {
                        ForEach(micros) { micro in
                            HStack {
                                Text(micro.label).font(.caption)
                                Spacer()
                                Text("\(micro.amount, specifier: "%.1f") \(micro.unit)")
                                    .font(.caption)
                                Text("\(Int(micro.percent))%")
                                    .font(.caption).bold()
                                    .foregroundColor(micro.percent >= 100 ? .green : .secondary)
                                    .frame(width: 46, alignment: .trailing)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: Laddning

    private func load() async {
        await loadDay()
        summary = (try? await APIClient.shared.get(
            "api/meals/summary", query: ["days": "14"]
        )) ?? summary
    }

    private func loadDay() async {
        errorMessage = nil
        do {
            dayLog = try await APIClient.shared.get(
                "api/meals", query: ["day": dayString]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

// MARK: - Fritextloggning

struct QuickLogSheet: View {
    @ObservedObject var session: SessionStore
    let dayString: String
    let onDone: () -> Void

    @State private var text = ""
    @State private var meal = "lunch"
    @State private var busy = false
    @State private var message: String?

    var body: some View {
        NavigationView {
            Form {
                TextField("t.ex. Big Mac, mellan pommes, cola zero", text: $text)
                MealPicker(meal: $meal)
                Button(busy ? "Tolkar…" : "⚡ Logga") {
                    Task { await log() }
                }
                .disabled(busy || text.trimmingCharacters(in: .whitespaces).count < 2)
                if let message = message {
                    Text(message).font(.footnote).foregroundColor(.secondary)
                }
            }
            .navigationTitle("Fritextloggning")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Klar") { onDone() }
                }
            }
        }
    }

    private func log() async {
        busy = true
        message = nil
        defer { busy = false }
        do {
            let result: QuickLogResult = try await APIClient.shared.post(
                "api/meals/quick-log",
                body: ["text": text.trimmingCharacters(in: .whitespaces),
                       "eaten_on": dayString, "meal": meal],
                timeout: 120
            )
            var parts = result.logged.map {
                "✅ \($0.name) \(Int($0.grams)) g (\(Int($0.kcal)) kcal)"
            }
            if !result.missing.isEmpty {
                parts.append("❓ Hittade inte: \(result.missing.joined(separator: ", "))")
            }
            message = parts.isEmpty ? "Inget kunde tolkas." : parts.joined(separator: "\n")
            text = ""
        } catch {
            message = error.localizedDescription
        }
    }
}

// MARK: - Mål

struct TargetsSheet: View {
    @ObservedObject var session: SessionStore
    let current: NutritionTargets?
    let onDone: () -> Void

    @State private var kcal = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var busy = false
    @State private var message: String?

    var body: some View {
        NavigationView {
            Form {
                Section("Dagliga mål") {
                    HStack { Text("Kalorier"); Spacer()
                        TextField("2000", text: $kcal)
                            .keyboardType(.numberPad).multilineTextAlignment(.trailing) }
                    HStack { Text("Protein (g)"); Spacer()
                        TextField("150", text: $protein)
                            .keyboardType(.numberPad).multilineTextAlignment(.trailing) }
                    HStack { Text("Kolhydrater (g)"); Spacer()
                        TextField("200", text: $carbs)
                            .keyboardType(.numberPad).multilineTextAlignment(.trailing) }
                    HStack { Text("Fett (g)"); Spacer()
                        TextField("70", text: $fat)
                            .keyboardType(.numberPad).multilineTextAlignment(.trailing) }
                }
                Button(busy ? "Sparar…" : "💾 Spara mål") {
                    Task { await save() }
                }
                .disabled(busy)
                if let message = message {
                    Text(message).font(.footnote).foregroundColor(.green)
                }
            }
            .navigationTitle("🎯 Mål")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Klar") { onDone() }
                }
            }
        }
        .onAppear {
            if let current = current {
                kcal = String(current.kcal)
                protein = String(current.protein_g)
                carbs = String(current.carbs_g)
                fat = String(current.fat_g)
            }
        }
    }

    private func save() async {
        busy = true
        defer { busy = false }
        var request = URLRequest(
            url: APIClient.shared.base.appendingPathComponent("api/nutrition-targets")
        )
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let cookies = APIClient.shared.cookieHeader {
            request.setValue(cookies, forHTTPHeaderField: "Cookie")
        }
        let body: [String: Any] = [
            "kcal": Int(kcal) ?? 2000,
            "protein_g": Int(protein) ?? 150,
            "carbs_g": Int(carbs) ?? 200,
            "fat_g": Int(fat) ?? 70,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        if let (_, response) = try? await URLSession.shared.data(for: request),
           let http = response as? HTTPURLResponse, http.statusCode < 300 {
            message = "✅ Sparat!"
        } else {
            message = "Kunde inte spara — försök igen."
        }
    }
}

/// Delad måltidsväljare
struct MealPicker: View {
    @Binding var meal: String

    var body: some View {
        Picker("Måltid", selection: $meal) {
            Text("Frukost").tag("breakfast")
            Text("Lunch").tag("lunch")
            Text("Middag").tag("dinner")
            Text("Mellanmål").tag("snack")
        }
    }
}
