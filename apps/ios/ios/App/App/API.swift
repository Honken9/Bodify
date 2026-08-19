import Foundation

/// Shapiqos API-klient. Autentiserar med Cloudflare Access-sessionens
/// cookies (skördas en gång i inloggningsvyn och sparas i Keychain).
/// När sessionen gått ut svarar servern med Access-inloggningens HTML —
/// då kastas .authNeeded och appen visar inloggningen igen.

enum APIError: LocalizedError {
    case authNeeded
    case server(Int)
    case decoding

    var errorDescription: String? {
        switch self {
        case .authNeeded: return "Inloggningen har gått ut."
        case .server(let code): return "Servern svarade \(code)."
        case .decoding: return "Kunde inte tolka svaret."
        }
    }
}

final class APIClient {
    static let shared = APIClient()
    let base = URL(string: "https://shapiqo.com")!

    private static let cookieKey = "shapiqo.session.cookies"

    var cookieHeader: String? {
        get { KeychainStore.read(Self.cookieKey) }
    }

    func saveCookies(_ header: String) {
        KeychainStore.write(Self.cookieKey, value: header)
    }

    func clearCookies() {
        KeychainStore.delete(Self.cookieKey)
    }

    var isLoggedIn: Bool { cookieHeader != nil }

    private func makeRequest(
        _ path: String, method: String, body: [String: Any]?
    ) throws -> URLRequest {
        var request = URLRequest(url: base.appendingPathComponent(path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let cookies = cookieHeader {
            request.setValue(cookies, forHTTPHeaderField: "Cookie")
        }
        if let body = body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        request.timeoutInterval = 30
        return request
    }

    private func validate(_ data: Data, _ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else { throw APIError.server(0) }
        // Utloggad → Access svarar med inloggningssidans HTML (ofta 200)
        let contentType = http.value(forHTTPHeaderField: "Content-Type") ?? ""
        if http.statusCode == 401 || http.statusCode == 403 { throw APIError.authNeeded }
        if contentType.contains("text/html") { throw APIError.authNeeded }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.server(http.statusCode)
        }
    }

    func get<T: Decodable>(_ path: String, query: [String: String] = [:]) async throws -> T {
        var components = URLComponents(
            url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false
        )!
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let cookies = cookieHeader {
            request.setValue(cookies, forHTTPHeaderField: "Cookie")
        }
        request.timeoutInterval = 30
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(data, response)
        guard let decoded = try? JSONDecoder().decode(T.self, from: data) else {
            throw APIError.decoding
        }
        return decoded
    }

    func post<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        let request = try makeRequest(path, method: "POST", body: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(data, response)
        guard let decoded = try? JSONDecoder().decode(T.self, from: data) else {
            throw APIError.decoding
        }
        return decoded
    }

    func delete(_ path: String) async throws {
        let request = try makeRequest(path, method: "DELETE", body: nil)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(data, response)
    }
}

// MARK: - Svarsmodeller (matchar API:ts JSON)

struct Me: Decodable {
    let email: String
    let display_name: String?
    let is_admin: Bool
}

struct MetricValue: Decodable {
    let value: Double
    let source: String?
}

struct FoodItemLite: Decodable {
    let name: String
    let brand: String?
}

struct MealEntryModel: Decodable, Identifiable {
    let id: String
    let meal: String
    let food_item: FoodItemLite
    let grams: Double
    let kcal: Double
    let protein_g: Double
    let carbs_g: Double
    let fat_g: Double
}

struct MacroTotals: Decodable {
    let kcal: Double
    let protein_g: Double
    let carbs_g: Double
    let fat_g: Double
}

struct NutritionTargets: Decodable {
    let kcal: Int
    let protein_g: Int
    let carbs_g: Int
    let fat_g: Int
}

struct DayLog: Decodable {
    let day: String
    let entries: [MealEntryModel]
    let totals: MacroTotals
    let targets: NutritionTargets
}

struct WorkoutModel: Decodable, Identifiable {
    let id: String
    let type: String
    let source: String
    let name: String?
    let started_at: String
    let duration_s: Int
    let distance_m: Double?
    let avg_hr: Double?
    let calories: Double?
}

struct BadgeModel: Decodable, Identifiable {
    var id: String { key }
    let key: String
    let emoji: String
    let title: String
    let description: String
    let earned: Bool
}

struct QuickLogItem: Decodable {
    let name: String
    let grams: Double
    let kcal: Double
}

struct QuickLogResult: Decodable {
    let logged: [QuickLogItem]
    let missing: [String]
}

struct IngestTokenOut: Decodable {
    let token: String
    let endpoint: String
}

struct ProviderStatus: Decodable {
    let provider: String
    let connected: Bool
    let status: String?
}

struct IntegrationsStatus: Decodable {
    let providers: [ProviderStatus]
}

// MARK: - Keychain-hjälpare (generisk sträng-lagring)

enum KeychainStore {
    static func write(_ key: String, value: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
        var attrs = query
        attrs[kSecValueData as String] = Data(value.utf8)
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(attrs as CFDictionary, nil)
    }

    static func read(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
