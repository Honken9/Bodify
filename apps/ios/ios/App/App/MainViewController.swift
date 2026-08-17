import UIKit
import Capacitor

/// Registrerar appens egna plugins hos Capacitor-bryggan.
class MainViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(HealthKitSyncPlugin())
    }
}
