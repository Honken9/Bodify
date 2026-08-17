import Foundation
import Capacitor
import HealthKit

/// Synkar Apple Health direkt till Shapiqo-servern — samma payloadformat
/// och endpoint som Health Auto Export använder, så backend är oförändrad.
/// Webben (i appens webbvy) konfigurerar modulen med endpoint + ingest-token
/// och triggar synk; bakgrundsleverans håller datan färsk däremellan.
@objc(HealthKitSyncPlugin)
public class HealthKitSyncPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "HealthKitSyncPlugin"
    public let jsName = "HealthKitSync"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "isAvailable", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "configure", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestAuthorization", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "sync", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "disable", returnType: CAPPluginReturnPromise),
    ]

    private let store = HKHealthStore()
    private static var syncing = false

    // Serverns parser förväntar sig HAE:s datumformat: "2026-08-16 07:30:00 +0200"
    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss Z"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    private struct MetricSpec {
        let id: HKQuantityTypeIdentifier
        let haeName: String   // namnet METRIC_MAP i backend känner igen
        let unit: HKUnit
        let cumulative: Bool  // summa per dag (annars snitt per dag)
        let scale: Double
    }

    private static let bpm = HKUnit.count().unitDivided(by: .minute())
    private static let vo2Unit = HKUnit.literUnit(with: .milli)
        .unitDivided(by: HKUnit.gramUnit(with: .kilo).unitMultiplied(by: .minute()))

    private static let metricSpecs: [MetricSpec] = [
        MetricSpec(id: .stepCount, haeName: "step_count", unit: .count(), cumulative: true, scale: 1),
        MetricSpec(id: .flightsClimbed, haeName: "flights_climbed", unit: .count(), cumulative: true, scale: 1),
        MetricSpec(id: .appleExerciseTime, haeName: "apple_exercise_time", unit: .minute(), cumulative: true, scale: 1),
        MetricSpec(id: .activeEnergyBurned, haeName: "active_energy", unit: .kilocalorie(), cumulative: true, scale: 1),
        MetricSpec(id: .restingHeartRate, haeName: "resting_heart_rate", unit: bpm, cumulative: false, scale: 1),
        MetricSpec(id: .heartRateVariabilitySDNN, haeName: "heart_rate_variability", unit: .secondUnit(with: .milli), cumulative: false, scale: 1),
        MetricSpec(id: .vo2Max, haeName: "vo2_max", unit: vo2Unit, cumulative: false, scale: 1),
        MetricSpec(id: .oxygenSaturation, haeName: "blood_oxygen_saturation", unit: .percent(), cumulative: false, scale: 100),
        MetricSpec(id: .bodyMass, haeName: "weight_body_mass", unit: .gramUnit(with: .kilo), cumulative: false, scale: 1),
        MetricSpec(id: .bodyFatPercentage, haeName: "body_fat_percentage", unit: .percent(), cumulative: false, scale: 100),
    ]

    private var readTypes: Set<HKObjectType> {
        var types: Set<HKObjectType> = [HKObjectType.workoutType(), HKSeriesType.workoutRoute()]
        for spec in Self.metricSpecs {
            if let t = HKQuantityType.quantityType(forIdentifier: spec.id) { types.insert(t) }
        }
        if let hr = HKQuantityType.quantityType(forIdentifier: .heartRate) { types.insert(hr) }
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) { types.insert(sleep) }
        return types
    }

    public override func load() {
        // Om synk redan är aktiverad: väck observatörerna vid varje appstart
        if SyncSettings.load() != nil {
            startObservers()
        }
    }

    // MARK: - JS-metoder

    @objc func isAvailable(_ call: CAPPluginCall) {
        call.resolve(["available": HKHealthStore.isHealthDataAvailable()])
    }

    @objc func configure(_ call: CAPPluginCall) {
        guard let endpoint = call.getString("endpoint"), let token = call.getString("token"),
              endpoint.hasPrefix("https://") else {
            call.reject("endpoint (https) och token krävs.")
            return
        }
        SyncSettings.save(endpoint: endpoint, token: token)
        call.resolve()
    }

    @objc func requestAuthorization(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.reject("Hälsodata är inte tillgängligt på den här enheten.")
            return
        }
        store.requestAuthorization(toShare: nil, read: readTypes) { [weak self] granted, error in
            if let error = error {
                call.reject("Behörighetsfrågan misslyckades: \(error.localizedDescription)")
                return
            }
            self?.startObservers()
            call.resolve(["granted": granted])
        }
    }

    @objc func sync(_ call: CAPPluginCall) {
        let days = call.getInt("days") ?? 7
        guard SyncSettings.load() != nil else {
            call.reject("Synken är inte konfigurerad ännu.")
            return
        }
        Task {
            do {
                let counts = try await self.runSync(days: days)
                call.resolve(counts)
            } catch {
                call.reject("Synk misslyckades: \(error.localizedDescription)")
            }
        }
    }

    @objc func status(_ call: CAPPluginCall) {
        let configured = SyncSettings.load() != nil
        var result: [String: Any] = ["configured": configured]
        if let last = UserDefaults.standard.object(forKey: "shapiqo.lastSync") as? Date {
            result["lastSync"] = Self.dateFormatter.string(from: last)
        }
        call.resolve(result)
    }

    @objc func disable(_ call: CAPPluginCall) {
        store.disableAllBackgroundDelivery { _, _ in }
        SyncSettings.clear()
        UserDefaults.standard.removeObject(forKey: "shapiqo.lastSync")
        call.resolve()
    }

    // MARK: - Synkmotorn

    /// Hämtar allt ur HealthKit för fönstret och POST:ar till servern.
    /// Långa fönster delas i 90-dagarsblock så payloaden hålls rimlig.
    private func runSync(days: Int) async throws -> [String: Int] {
        guard let settings = SyncSettings.load() else {
            throw NSError(domain: "HealthKitSync", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "Inte konfigurerad."])
        }
        if Self.syncing { return ["metrics": 0, "sleep": 0, "workouts": 0, "skipped": 0] }
        Self.syncing = true
        defer { Self.syncing = false }

        var totals: [String: Int] = ["metrics": 0, "sleep": 0, "workouts": 0, "skipped": 0]
        var remaining = max(days, 1)
        var end = Date()
        while remaining > 0 {
            let chunk = min(remaining, 90)
            let start = Calendar.current.date(byAdding: .day, value: -chunk, to: end) ?? end
            let payload = await buildPayload(start: start, end: end)
            let counts = try await upload(payload: payload, settings: settings)
            for (key, value) in counts {
                if let n = value as? Int { totals[key] = (totals[key] ?? 0) + n }
            }
            remaining -= chunk
            end = start
        }
        UserDefaults.standard.set(Date(), forKey: "shapiqo.lastSync")
        return totals
    }

    private func buildPayload(start: Date, end: Date) async -> [String: Any] {
        var metrics: [[String: Any]] = []
        for spec in Self.metricSpecs {
            let points = await dailyStats(spec, start: start, end: end)
            if !points.isEmpty {
                metrics.append([
                    "name": spec.haeName,
                    "units": spec.haeName == "active_energy" ? "kcal" : "count",
                    "data": points,
                ])
            }
        }
        let sleepPoints = await fetchSleep(start: start, end: end)
        if !sleepPoints.isEmpty {
            metrics.append(["name": "sleep_analysis", "units": "hr", "data": sleepPoints])
        }
        let workouts = await fetchWorkouts(start: start, end: end)
        return ["data": ["metrics": metrics, "workouts": workouts]]
    }

    /// Dagsvärden: summa för räknare (steg, kcal…), snitt för mätvärden
    /// (vilopuls, VO₂max…) — samma upplösning som HAE levererar.
    private func dailyStats(_ spec: MetricSpec, start: Date, end: Date) async -> [[String: Any]] {
        guard let type = HKQuantityType.quantityType(forIdentifier: spec.id) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        let anchor = Calendar.current.startOfDay(for: start)
        let options: HKStatisticsOptions = spec.cumulative ? .cumulativeSum : .discreteAverage
        return await withCheckedContinuation { cont in
            let query = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: options,
                anchorDate: anchor,
                intervalComponents: DateComponents(day: 1)
            )
            query.initialResultsHandler = { _, results, _ in
                var points: [[String: Any]] = []
                results?.enumerateStatistics(from: start, to: end) { stat, _ in
                    let quantity = spec.cumulative ? stat.sumQuantity() : stat.averageQuantity()
                    if let quantity = quantity {
                        let value = quantity.doubleValue(for: spec.unit) * spec.scale
                        points.append([
                            "date": Self.dateFormatter.string(from: stat.startDate),
                            "qty": (value * 1000).rounded() / 1000,
                        ])
                    }
                }
                cont.resume(returning: points)
            }
            self.store.execute(query)
        }
    }

    /// Sömnpass grupperade till nätter (nytt block vid > 3 h gap), med
    /// timmar per fas — nycklarna matchar backendens _ingest_sleep.
    private func fetchSleep(start: Date, end: Date) async -> [[String: Any]] {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        let samples: [HKCategorySample] = await withCheckedContinuation { cont in
            let query = HKSampleQuery(sampleType: type, predicate: predicate,
                                      limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, result, _ in
                cont.resume(returning: (result as? [HKCategorySample]) ?? [])
            }
            self.store.execute(query)
        }

        var nights: [[HKCategorySample]] = []
        for sample in samples where sample.value != HKCategoryValueSleepAnalysis.inBed.rawValue {
            if let prevEnd = nights.last?.last?.endDate,
               sample.startDate.timeIntervalSince(prevEnd) < 3 * 3600 {
                nights[nights.count - 1].append(sample)
            } else {
                nights.append([sample])
            }
        }

        var points: [[String: Any]] = []
        for night in nights {
            guard let first = night.first, let last = night.last else { continue }
            var deep = 0.0, rem = 0.0, core = 0.0, awake = 0.0
            for sample in night {
                let hours = sample.endDate.timeIntervalSince(sample.startDate) / 3600
                if #available(iOS 16.0, *) {
                    switch sample.value {
                    case HKCategoryValueSleepAnalysis.asleepDeep.rawValue: deep += hours
                    case HKCategoryValueSleepAnalysis.asleepREM.rawValue: rem += hours
                    case HKCategoryValueSleepAnalysis.asleepCore.rawValue: core += hours
                    case HKCategoryValueSleepAnalysis.awake.rawValue: awake += hours
                    default: core += hours
                    }
                } else if sample.value == HKCategoryValueSleepAnalysis.awake.rawValue {
                    awake += hours
                } else {
                    core += hours
                }
            }
            points.append([
                "sleepStart": Self.dateFormatter.string(from: first.startDate),
                "sleepEnd": Self.dateFormatter.string(from: last.endDate),
                "deep": (deep * 100).rounded() / 100,
                "rem": (rem * 100).rounded() / 100,
                "core": (core * 100).rounded() / 100,
                "awake": (awake * 100).rounded() / 100,
            ])
        }
        return points
    }

    private func fetchWorkouts(start: Date, end: Date) async -> [[String: Any]] {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
        let workouts: [HKWorkout] = await withCheckedContinuation { cont in
            let query = HKSampleQuery(sampleType: .workoutType(), predicate: predicate,
                                      limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, result, _ in
                cont.resume(returning: (result as? [HKWorkout]) ?? [])
            }
            self.store.execute(query)
        }

        var out: [[String: Any]] = []
        for workout in workouts {
            var dict: [String: Any] = [
                "id": workout.uuid.uuidString,
                "name": Self.workoutName(workout.workoutActivityType),
                "start": Self.dateFormatter.string(from: workout.startDate),
                "end": Self.dateFormatter.string(from: workout.endDate),
            ]
            if let distance = workout.totalDistance {
                dict["distance"] = [
                    "qty": distance.doubleValue(for: HKUnit.meterUnit(with: .kilo)),
                    "units": "km",
                ]
            }
            if let energy = workout.totalEnergyBurned {
                dict["activeEnergyBurned"] = [
                    "qty": energy.doubleValue(for: .kilocalorie()),
                    "units": "kcal",
                ]
            }
            if let hr = await workoutHeartRate(workout) {
                dict["avgHeartRate"] = ["qty": hr.avg]
                dict["maxHeartRate"] = ["qty": hr.max]
            }
            let route = await workoutRoute(workout)
            if !route.isEmpty {
                dict["route"] = route
            }
            out.append(dict)
        }
        return out
    }

    private func workoutHeartRate(_ workout: HKWorkout) async -> (avg: Double, max: Double)? {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return nil }
        let predicate = HKQuery.predicateForSamples(
            withStart: workout.startDate, end: workout.endDate, options: []
        )
        return await withCheckedContinuation { cont in
            let query = HKStatisticsQuery(
                quantityType: hrType, quantitySamplePredicate: predicate,
                options: [.discreteAverage, .discreteMax]
            ) { _, stats, _ in
                guard let avg = stats?.averageQuantity()?.doubleValue(for: Self.bpm) else {
                    cont.resume(returning: nil)
                    return
                }
                let max = stats?.maximumQuantity()?.doubleValue(for: Self.bpm) ?? avg
                cont.resume(returning: (avg.rounded(), max.rounded()))
            }
            self.store.execute(query)
        }
    }

    /// GPS-rutten för ett pass, glesad till max 500 punkter (samma tak
    /// som backendens _route_points).
    private func workoutRoute(_ workout: HKWorkout) async -> [[String: Double]] {
        let predicate = HKQuery.predicateForObjects(from: workout)
        let routes: [HKWorkoutRoute] = await withCheckedContinuation { cont in
            let query = HKSampleQuery(sampleType: HKSeriesType.workoutRoute(), predicate: predicate,
                                      limit: 1, sortDescriptors: nil) { _, result, _ in
                cont.resume(returning: (result as? [HKWorkoutRoute]) ?? [])
            }
            self.store.execute(query)
        }
        guard let route = routes.first else { return [] }

        var coords: [[String: Double]] = []
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            let query = HKWorkoutRouteQuery(route: route) { _, locations, done, _ in
                if let locations = locations {
                    for loc in locations {
                        coords.append([
                            "lat": loc.coordinate.latitude,
                            "lon": loc.coordinate.longitude,
                        ])
                    }
                }
                if done { cont.resume() }
            }
            self.store.execute(query)
        }

        if coords.count > 500 {
            let step = Double(coords.count) / 500.0
            var thinned: [[String: Double]] = []
            for i in 0..<500 { thinned.append(coords[Int(Double(i) * step)]) }
            thinned.append(coords[coords.count - 1])
            coords = thinned
        }
        return coords
    }

    private static func workoutName(_ type: HKWorkoutActivityType) -> String {
        switch type {
        case .running: return "Running"
        case .walking: return "Walking"
        case .hiking: return "Hiking"
        case .cycling: return "Cycling"
        case .swimming: return "Swimming"
        case .traditionalStrengthTraining, .functionalStrengthTraining:
            return "Strength Training"
        case .highIntensityIntervalTraining: return "HIIT"
        case .yoga: return "Yoga"
        case .rowing: return "Rowing"
        case .elliptical: return "Elliptical"
        default: return "Workout"
        }
    }

    // MARK: - Bakgrundsleverans

    /// Nya pass/steg i HealthKit väcker appen → tyst synk av senaste dagarna.
    private func startObservers() {
        var types: [HKSampleType] = [HKObjectType.workoutType()]
        if let steps = HKQuantityType.quantityType(forIdentifier: .stepCount) {
            types.append(steps)
        }
        for type in types {
            let query = HKObserverQuery(sampleType: type, predicate: nil) { [weak self] _, completion, _ in
                Task {
                    _ = try? await self?.runSync(days: 3)
                    completion()
                }
            }
            store.execute(query)
            store.enableBackgroundDelivery(for: type, frequency: .hourly) { _, _ in }
        }
    }

    // MARK: - Uppladdning

    private func upload(payload: [String: Any], settings: SyncSettings) async throws -> [String: Any] {
        guard let url = URL(string: settings.endpoint) else {
            throw NSError(domain: "HealthKitSync", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "Ogiltig endpoint."])
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(settings.token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        request.timeoutInterval = 60

        let (data, response): (Data, URLResponse) = try await withCheckedThrowingContinuation { cont in
            URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    cont.resume(throwing: error)
                } else if let data = data, let response = response {
                    cont.resume(returning: (data, response))
                } else {
                    cont.resume(throwing: NSError(domain: "HealthKitSync", code: 3))
                }
            }.resume()
        }
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw NSError(domain: "HealthKitSync", code: 4,
                          userInfo: [NSLocalizedDescriptionKey: "Servern svarade \(code)."])
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }
}

// MARK: - Nyckelringen

/// Endpoint + ingest-token lagras i Keychain — aldrig i UserDefaults.
private struct SyncSettings {
    let endpoint: String
    let token: String

    private static let account = "shapiqo-healthkit-sync"

    static func save(endpoint: String, token: String) {
        guard let data = try? JSONSerialization.data(
            withJSONObject: ["endpoint": endpoint, "token": token]
        ) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var attrs = query
        attrs[kSecValueData as String] = data
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(attrs as CFDictionary, nil)
    }

    static func load() -> SyncSettings? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let dict = (try? JSONSerialization.jsonObject(with: data)) as? [String: String],
              let endpoint = dict["endpoint"], let token = dict["token"] else {
            return nil
        }
        return SyncSettings(endpoint: endpoint, token: token)
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
