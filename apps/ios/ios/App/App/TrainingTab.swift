import SwiftUI

/// Träningsfliken: växlar mellan passlistan och kartan.
struct TrainingTab: View {
    @ObservedObject var session: SessionStore
    @State private var mode = 0

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Picker("Vy", selection: $mode) {
                    Text("Lista").tag(0)
                    Text("🗺 Karta").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.vertical, 6)

                if mode == 0 {
                    WorkoutsView(session: session)
                } else {
                    MapView(session: session)
                }
            }
            .navigationTitle("Träning")
            .navigationBarTitleDisplayMode(.inline)
        }
        .navigationViewStyle(.stack)
    }
}
