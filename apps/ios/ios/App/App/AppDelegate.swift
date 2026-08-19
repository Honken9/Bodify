import SwiftUI
import UIKit
import UserNotifications

/// Shapiqo är en helt native SwiftUI-app — RootView är hela UI:t.
/// Webben används enbart för Cloudflare Access-inloggningen.
@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    var window: UIWindow?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = UIHostingController(rootView: RootView())
        window.makeKeyAndVisible()
        self.window = window

        // Bakgrundsleverans från HealthKit kräver att observatörerna
        // registreras om vid varje appstart
        HealthKitService.shared.startObserversIfConfigured()

        // Notiser: har användaren redan sagt ja hämtas en färsk token
        // (den kan rotera) vid varje start
        UNUserNotificationCenter.current().delegate = self
        if UserDefaults.standard.bool(forKey: "shapiqo.push.enabled") {
            application.registerForRemoteNotifications()
        }
        return true
    }

    // MARK: - Push

    /// Fråga om tillstånd och registrera — anropas från Profil-fliken.
    static func enablePush() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound, .badge]
        ) { granted, _ in
            guard granted else { return }
            UserDefaults.standard.set(true, forKey: "shapiqo.push.enabled")
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task {
            struct OK: Decodable { let ok: Bool? }
            let _: OK? = try? await APIClient.shared.post(
                "api/push/apns-token", body: ["token": token]
            )
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Simulator eller nätfel — tyst; knappen kan tryckas igen
    }

    /// Visa notiser även när appen är öppen
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler:
            @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        completionHandler()
    }
}
