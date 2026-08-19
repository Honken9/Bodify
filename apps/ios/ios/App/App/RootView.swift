import SwiftUI

/// Appens rot: inloggad → native flikar; utloggad → webbinloggningen.
final class SessionStore: ObservableObject {
    @Published var loggedIn: Bool = APIClient.shared.isLoggedIn

    func didLogin() {
        loggedIn = true
    }

    func logout() {
        APIClient.shared.clearCookies()
        loggedIn = false
    }
}

struct RootView: View {
    @StateObject private var session = SessionStore()

    var body: some View {
        if session.loggedIn {
            TabView {
                HomeView(session: session)
                    .tabItem { Label("Hem", systemImage: "house.fill") }
                MealsView(session: session)
                    .tabItem { Label("Kost", systemImage: "fork.knife") }
                TrainingTab(session: session)
                    .tabItem { Label("Träning", systemImage: "figure.run") }
                SocialView(session: session)
                    .tabItem { Label("Socialt", systemImage: "trophy.fill") }
                ProfileView(session: session)
                    .tabItem { Label("Profil", systemImage: "person.crop.circle") }
            }
            .onAppear {
                HealthKitService.shared.startObserversIfConfigured()
            }
        } else {
            LoginScreen { session.didLogin() }
        }
    }
}

// MARK: - Delade småkomponenter

struct ErrorBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.footnote)
            .foregroundColor(.red)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(Color.red.opacity(0.1))
            .cornerRadius(10)
    }
}

/// Gemensam felhantering: utgången session loggar ut, annat visas.
@MainActor
func handleAPIError(_ error: Error, session: SessionStore, message: inout String?) {
    if let apiError = error as? APIError, case .authNeeded = apiError {
        session.logout()
    } else {
        message = error.localizedDescription
    }
}
