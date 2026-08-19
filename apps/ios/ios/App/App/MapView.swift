import SwiftUI
import MapKit
import CoreLocation

/// Träningskartan — native MapKit. Alla pass med GPS ritas: rutter som
/// linjer (navy, vald i rött), platsbundna pass som prickar. Listan
/// zoomar till valt pass.

struct GeoActivity: Decodable, Identifiable {
    let id: String
    let type: String
    let source: String
    let name: String?
    let started_at: String
    let duration_s: Int
    let distance_m: Double?
    let polyline: String?
    let start: [Double]?
}

/// Google-kodad polyline → koordinater (samma format som Strava/servern)
func decodePolyline(_ encoded: String) -> [CLLocationCoordinate2D] {
    var coords: [CLLocationCoordinate2D] = []
    var index = encoded.startIndex
    var lat = 0, lng = 0
    while index < encoded.endIndex {
        var result = 0
        var shift = 0
        var byte = 0
        repeat {
            byte = Int(encoded[index].asciiValue ?? 63) - 63
            index = encoded.index(after: index)
            result |= (byte & 0x1F) << shift
            shift += 5
        } while byte >= 0x20 && index < encoded.endIndex
        lat += (result & 1) != 0 ? ~(result >> 1) : (result >> 1)

        guard index < encoded.endIndex else { break }
        result = 0
        shift = 0
        repeat {
            byte = Int(encoded[index].asciiValue ?? 63) - 63
            index = encoded.index(after: index)
            result |= (byte & 0x1F) << shift
            shift += 5
        } while byte >= 0x20 && index < encoded.endIndex
        lng += (result & 1) != 0 ? ~(result >> 1) : (result >> 1)

        coords.append(CLLocationCoordinate2D(
            latitude: Double(lat) / 1e5, longitude: Double(lng) / 1e5
        ))
    }
    return coords
}

struct MapView: View {
    @ObservedObject var session: SessionStore

    @State private var activities: [GeoActivity] = []
    @State private var filter = "all"
    @State private var focusId: String?
    @State private var showList = false
    @State private var errorMessage: String?

    private static let filters: [(String, String)] = [
        ("all", "Allt"), ("run", "🏃 Löpning"), ("ride", "🚴 Cykling"),
        ("walk", "🚶 Promenad"), ("strength", "🏋️ Gym"),
    ]

    private var filtered: [GeoActivity] {
        filter == "all" ? activities : activities.filter { $0.type == filter }
    }

    var body: some View {
        ZStack(alignment: .top) {
            MapContainer(activities: filtered, focusId: focusId)
                .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 8) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Self.filters, id: \.0) { key, label in
                            Button {
                                filter = key
                                focusId = nil
                            } label: {
                                Text(label)
                                    .font(.caption).bold()
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 7)
                                    .background(filter == key ? Color.accentColor : Color(.systemBackground))
                                    .foregroundColor(filter == key ? .white : .primary)
                                    .cornerRadius(16)
                                    .shadow(radius: 1)
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                if let message = errorMessage {
                    ErrorBanner(message: message).padding(.horizontal)
                }
            }
            .padding(.top, 8)
        }
        .overlay(alignment: .bottomTrailing) {
            Button {
                showList = true
            } label: {
                Image(systemName: "list.bullet")
                    .padding(12)
                    .background(Color(.systemBackground).opacity(0.95))
                    .clipShape(Circle())
                    .shadow(radius: 2)
            }
            .padding(.trailing, 12)
            .padding(.bottom, 24)
        }
        .sheet(isPresented: $showList) {
            ActivityListSheet(
                activities: filtered,
                onSelect: { id in
                    focusId = id
                    showList = false
                }
            )
        }
        .onAppear { Task { await load() } }
    }

    private func load() async {
        errorMessage = nil
        do {
            activities = try await APIClient.shared.get(
                "api/cardio/geo", query: ["limit": "5000"]
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

/// Listan i arket: tryck → kartan zoomar till passet
struct ActivityListSheet: View {
    let activities: [GeoActivity]
    let onSelect: (String) -> Void

    private static let icons: [String: String] = [
        "run": "🏃", "ride": "🚴", "walk": "🚶", "swim": "🏊",
        "strength": "🏋️", "other": "💪",
    ]

    var body: some View {
        NavigationView {
            List(activities) { activity in
                Button {
                    onSelect(activity.id)
                } label: {
                    HStack {
                        Text(Self.icons[activity.type] ?? "💪")
                        VStack(alignment: .leading, spacing: 2) {
                            Text(activity.name ?? "Träning")
                                .font(.subheadline).bold()
                                .foregroundColor(.primary)
                            Text(subtitle(activity))
                                .font(.caption).foregroundColor(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("\(activities.count) pass på kartan")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func subtitle(_ activity: GeoActivity) -> String {
        var parts = [String(activity.started_at.prefix(10))]
        if let distance = activity.distance_m, distance > 0 {
            parts.append(String(format: "%.1f km", distance / 1000))
        }
        parts.append("\(activity.duration_s / 60) min")
        return parts.joined(separator: " · ")
    }
}

/// MKMapView-wrapper: ritar polylines + prickar, hanterar fokus och 🧭
struct MapContainer: UIViewRepresentable {
    let activities: [GeoActivity]
    let focusId: String?

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.showsUserLocation = true
        context.coordinator.locationManager.requestWhenInUseAuthorization()
        let tracking = MKUserTrackingButton(mapView: map)
        tracking.translatesAutoresizingMaskIntoConstraints = false
        tracking.backgroundColor = UIColor.systemBackground.withAlphaComponent(0.9)
        tracking.layer.cornerRadius = 6
        map.addSubview(tracking)
        NSLayoutConstraint.activate([
            tracking.trailingAnchor.constraint(equalTo: map.trailingAnchor, constant: -10),
            tracking.topAnchor.constraint(equalTo: map.safeAreaLayoutGuide.topAnchor, constant: 54),
        ])
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        let coordinator = context.coordinator
        let ids = activities.map { $0.id }
        if coordinator.renderedIds != ids {
            coordinator.renderedIds = ids
            map.removeOverlays(map.overlays)
            map.removeAnnotations(map.annotations.filter { !($0 is MKUserLocation) })
            coordinator.routes = [:]
            coordinator.focused = nil

            var boundingRect = MKMapRect.null
            for activity in activities {
                if let encoded = activity.polyline {
                    let coords = decodePolyline(encoded)
                    if coords.count > 1 {
                        let line = ActivityPolyline(coordinates: coords, count: coords.count)
                        line.activityId = activity.id
                        map.addOverlay(line)
                        coordinator.routes[activity.id] = line
                        boundingRect = boundingRect.union(line.boundingMapRect)
                        continue
                    }
                }
                if let start = activity.start, start.count == 2 {
                    let pin = MKPointAnnotation()
                    pin.coordinate = CLLocationCoordinate2D(latitude: start[0], longitude: start[1])
                    pin.title = activity.name ?? "Träning"
                    pin.subtitle = String(activity.started_at.prefix(10))
                    map.addAnnotation(pin)
                    boundingRect = boundingRect.union(
                        MKMapRect(origin: MKMapPoint(pin.coordinate), size: MKMapSize(width: 1, height: 1))
                    )
                }
            }
            if !boundingRect.isNull {
                map.setVisibleMapRect(
                    boundingRect,
                    edgePadding: UIEdgeInsets(top: 90, left: 40, bottom: 40, right: 40),
                    animated: false
                )
            }
        }

        // Fokus: markera i rött och zooma in
        if coordinator.focused != focusId {
            if let previous = coordinator.focused, let line = coordinator.routes[previous],
               let renderer = map.renderer(for: line) as? MKPolylineRenderer {
                renderer.strokeColor = Coordinator.navy
                renderer.lineWidth = 3
            }
            coordinator.focused = focusId
            if let id = focusId, let line = coordinator.routes[id] {
                if let renderer = map.renderer(for: line) as? MKPolylineRenderer {
                    renderer.strokeColor = Coordinator.red
                    renderer.lineWidth = 5
                }
                map.setVisibleMapRect(
                    line.boundingMapRect,
                    edgePadding: UIEdgeInsets(top: 100, left: 50, bottom: 50, right: 50),
                    animated: true
                )
            }
        }
    }

    final class ActivityPolyline: MKPolyline {
        var activityId: String = ""
    }

    final class Coordinator: NSObject, MKMapViewDelegate {
        static let navy = UIColor(red: 0.137, green: 0.345, blue: 0.541, alpha: 0.85)
        static let red = UIColor(red: 0.882, green: 0.114, blue: 0.282, alpha: 1.0)

        let locationManager = CLLocationManager()
        var renderedIds: [String] = []
        var routes: [String: ActivityPolyline] = [:]
        var focused: String?

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            guard let line = overlay as? ActivityPolyline else {
                return MKOverlayRenderer(overlay: overlay)
            }
            let renderer = MKPolylineRenderer(polyline: line)
            let isFocused = line.activityId == focused
            renderer.strokeColor = isFocused ? Self.red : Self.navy
            renderer.lineWidth = isFocused ? 5 : 3
            return renderer
        }
    }
}
