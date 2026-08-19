import SwiftUI
import WebKit

/// Inloggning — det ENDA stället där webben används. Cloudflare Access-
/// flödet (e-post + engångskod) körs i en webbvy; när sessionscookien
/// finns skördas alla shapiqo.com-cookies till Keychain och appen går
/// över till helt native läge.
struct AuthView: UIViewRepresentable {
    let onLoggedIn: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onLoggedIn: onLoggedIn)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.allowsLinkPreview = false
        webView.load(URLRequest(url: URL(string: "https://shapiqo.com")!))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let onLoggedIn: () -> Void
        private var done = false

        init(onLoggedIn: @escaping () -> Void) {
            self.onLoggedIn = onLoggedIn
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard !done else { return }
            webView.configuration.websiteDataStore.httpCookieStore
                .getAllCookies { [weak self] cookies in
                    guard let self = self, !self.done else { return }
                    let siteCookies = cookies.filter {
                        $0.domain.contains("shapiqo.com")
                    }
                    let hasSession = siteCookies.contains {
                        $0.name == "CF_Authorization"
                    }
                    guard hasSession else { return }
                    let header = siteCookies
                        .map { "\($0.name)=\($0.value)" }
                        .joined(separator: "; ")
                    APIClient.shared.saveCookies(header)
                    self.done = true
                    DispatchQueue.main.async { self.onLoggedIn() }
                }
        }
    }
}

struct LoginScreen: View {
    let onLoggedIn: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Text("Logga in på Shapiqo")
                .font(.headline)
                .padding(.vertical, 12)
            AuthView(onLoggedIn: onLoggedIn)
        }
    }
}

struct ConnectRef: Identifiable {
    var id: String { provider }
    let provider: String
}

/// OAuth-koppling (Strava/Withings) inne i appen: webbvyn delar
/// inloggningssessionen, användaren godkänner hos leverantören och
/// studsar tillbaka — då stängs arket och statusen laddas om.
struct ConnectProviderSheet: View {
    let provider: String
    let onDone: () -> Void

    var body: some View {
        NavigationView {
            ConnectWebView(provider: provider, onDone: onDone)
                .navigationTitle(provider == "strava" ? "Koppla Strava" : "Koppla Withings")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Stäng") { onDone() }
                    }
                }
        }
    }
}

struct ConnectWebView: UIViewRepresentable {
    let provider: String
    let onDone: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onDone: onDone) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()  // samma session som inloggningen
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        let url = URL(string: "https://shapiqo.com/api/integrations/\(provider)/connect")!
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let onDone: () -> Void
        private var leftSite = false

        init(onDone: @escaping () -> Void) {
            self.onDone = onDone
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard let host = webView.url?.host else { return }
            if !host.contains("shapiqo.com") {
                leftSite = true  // hos leverantören (Strava/Withings)
            } else if leftSite {
                // Tillbaka på shapiqo.com efter OAuth = kopplingen klar
                onDone()
            }
        }
    }
}
