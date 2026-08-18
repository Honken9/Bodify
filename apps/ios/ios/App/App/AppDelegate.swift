import SwiftUI
import UIKit

/// Shapiqo är en helt native SwiftUI-app — RootView är hela UI:t.
/// Webben används enbart för Cloudflare Access-inloggningen.
@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

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
        return true
    }
}
