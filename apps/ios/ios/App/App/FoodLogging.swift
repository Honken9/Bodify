import SwiftUI
import AudioToolbox
import AVFoundation
import UIKit

// MARK: - 📷 Fota måltiden

struct PhotoMealSheet: View {
    @ObservedObject var session: SessionStore
    let dayString: String
    let onDone: () -> Void

    struct EditableItem: Identifiable {
        let id = UUID()
        var name: String
        var grams: Double
        let aiGrams: Double
        let per100g: [String: Double]
    }

    @State private var image: UIImage?
    @State private var showCamera = false
    @State private var showLibrary = false
    @State private var items: [EditableItem] = []
    @State private var meal = "lunch"
    @State private var busy = false
    @State private var message: String?

    var body: some View {
        NavigationView {
            Form {
                if let image = image {
                    Image(uiImage: image)
                        .resizable().scaledToFit()
                        .frame(maxHeight: 180)
                        .cornerRadius(10)
                        .listRowSeparator(.hidden)
                }
                Section {
                    HStack {
                        Button("📷 Kamera") { showCamera = true }
                            .buttonStyle(.bordered)
                        Button("🖼 Bildbibliotek") { showLibrary = true }
                            .buttonStyle(.bordered)
                    }
                    if image != nil && items.isEmpty {
                        Button(busy ? "AI:n analyserar…" : "✨ Analysera fotot") {
                            Task { await analyze() }
                        }
                        .disabled(busy)
                    }
                }

                if !items.isEmpty {
                    Section("Justera mängderna") {
                        ForEach($items) { $item in
                            VStack(alignment: .leading, spacing: 4) {
                                TextField("Namn", text: $item.name)
                                    .font(.subheadline).bold()
                                HStack {
                                    Slider(value: $item.grams, in: 5...800, step: 5)
                                    Text("\(Int(item.grams)) g")
                                        .font(.caption).monospacedDigit()
                                        .frame(width: 52, alignment: .trailing)
                                }
                                Text("\(Int((item.per100g["kcal"] ?? 0) * item.grams / 100)) kcal")
                                    .font(.caption).foregroundColor(.secondary)
                            }
                        }
                        .onDelete { items.remove(atOffsets: $0) }
                        MealPicker(meal: $meal)
                        Button(busy ? "Loggar…" : "🍽 Logga måltiden") {
                            Task { await log() }
                        }
                        .disabled(busy || items.isEmpty)
                    }
                }
                if let message = message {
                    Text(message).font(.footnote).foregroundColor(.secondary)
                }
            }
            .navigationTitle("Fota måltiden")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Klar") { onDone() }
                }
            }
            .sheet(isPresented: $showCamera) {
                ImagePicker(source: .camera) { picked in
                    image = picked
                    items = []
                }
            }
            .sheet(isPresented: $showLibrary) {
                ImagePicker(source: .photoLibrary) { picked in
                    image = picked
                    items = []
                }
            }
        }
    }

    private func analyze() async {
        guard let image = image,
              let data = image.jpegData(compressionQuality: 0.7) else { return }
        busy = true
        message = nil
        defer { busy = false }
        do {
            let result: VisionResult = try await APIClient.shared.upload(
                "api/ai/meal-vision", imageData: data
            )
            items = result.items.map {
                EditableItem(name: $0.name, grams: $0.grams,
                             aiGrams: $0.grams, per100g: $0.per_100g)
            }
            if items.isEmpty { message = "AI:n hittade inga livsmedel — prova en tydligare bild." }
        } catch {
            message = error.localizedDescription
        }
    }

    private func log() async {
        busy = true
        defer { busy = false }
        let payload: [String: Any] = [
            "eaten_on": dayString,
            "meal": meal,
            "items": items.map {
                [
                    "name": $0.name,
                    "grams": $0.grams,
                    "ai_grams": $0.aiGrams,
                    "per_100g": $0.per100g,
                ] as [String: Any]
            },
        ]
        do {
            struct Entry: Decodable { let id: String }
            let _: [Entry] = try await APIClient.shared.post(
                "api/meals/photo-log", body: payload
            )
            onDone()
        } catch {
            message = error.localizedDescription
        }
    }
}

/// UIImagePickerController-wrapper: kamera eller bildbibliotek
struct ImagePicker: UIViewControllerRepresentable {
    let source: UIImagePickerController.SourceType
    let onPicked: (UIImage) -> Void
    @Environment(\.presentationMode) private var presentationMode

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        if UIImagePickerController.isSourceTypeAvailable(source) {
            picker.sourceType = source
        }
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    final class Coordinator: NSObject, UIImagePickerControllerDelegate,
                             UINavigationControllerDelegate {
        let parent: ImagePicker
        init(_ parent: ImagePicker) { self.parent = parent }

        func imagePickerController(
            _ picker: UIImagePickerController,
            didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]
        ) {
            if let image = info[.originalImage] as? UIImage {
                parent.onPicked(image)
            }
            parent.presentationMode.wrappedValue.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.presentationMode.wrappedValue.dismiss()
        }
    }
}

// MARK: - Streckkodsskanning

struct BarcodeSheet: View {
    @ObservedObject var session: SessionStore
    let dayString: String
    let onDone: () -> Void

    @State private var scannedCode: String?
    @State private var food: FoodItemFull?
    @State private var notFound = false
    @State private var message: String?

    var body: some View {
        NavigationView {
            Group {
                if let food = food {
                    PortionForm(session: session, food: food,
                                dayString: dayString, onLogged: onDone)
                } else if notFound, let code = scannedCode {
                    CreateFoodForm(session: session, barcode: code) { created in
                        food = created
                        notFound = false
                    }
                } else {
                    ZStack(alignment: .bottom) {
                        BarcodeScannerView { code in
                            guard scannedCode == nil else { return }
                            scannedCode = code
                            Task { await lookup(code) }
                        }
                        Text(message ?? "Rikta kameran mot streckkoden")
                            .font(.footnote)
                            .padding(10)
                            .background(.thinMaterial)
                            .cornerRadius(10)
                            .padding(.bottom, 30)
                    }
                }
            }
            .navigationTitle("Skanna streckkod")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Klar") { onDone() }
                }
            }
        }
    }

    private func lookup(_ code: String) async {
        message = "Slår upp \(code)…"
        do {
            food = try await APIClient.shared.get("api/food/barcode/\(code)")
        } catch {
            if let apiError = error as? APIError, case .server(404) = apiError {
                notFound = true
            } else {
                message = error.localizedDescription
                scannedCode = nil
            }
        }
    }
}

/// AVFoundation-skanner för EAN/UPC
struct BarcodeScannerView: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    func makeUIViewController(context: Context) -> ScannerController {
        let controller = ScannerController()
        controller.delegate = context.coordinator
        return controller
    }

    func updateUIViewController(_ uiViewController: ScannerController, context: Context) {}

    final class Coordinator: NSObject, AVCaptureMetadataOutputObjectsDelegate {
        let onCode: (String) -> Void
        private var fired = false
        init(onCode: @escaping (String) -> Void) { self.onCode = onCode }

        func metadataOutput(
            _ output: AVCaptureMetadataOutput,
            didOutput metadataObjects: [AVMetadataObject],
            from connection: AVCaptureConnection
        ) {
            guard !fired,
                  let object = metadataObjects.first as? AVMetadataMachineReadableCodeObject,
                  let value = object.stringValue else { return }
            fired = true
            AudioServicesPlaySystemSound(SystemSoundID(kSystemSoundID_Vibrate))
            DispatchQueue.main.async { self.onCode(value) }
        }
    }

    final class ScannerController: UIViewController {
        var delegate: AVCaptureMetadataOutputObjectsDelegate?
        private let captureSession = AVCaptureSession()

        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black
            guard let device = AVCaptureDevice.default(for: .video),
                  let input = try? AVCaptureDeviceInput(device: device),
                  captureSession.canAddInput(input) else { return }
            captureSession.addInput(input)

            let output = AVCaptureMetadataOutput()
            guard captureSession.canAddOutput(output) else { return }
            captureSession.addOutput(output)
            output.setMetadataObjectsDelegate(delegate, queue: .main)
            output.metadataObjectTypes = [.ean13, .ean8, .upce, .code128]

            let preview = AVCaptureVideoPreviewLayer(session: captureSession)
            preview.frame = view.layer.bounds
            preview.videoGravity = .resizeAspectFill
            view.layer.addSublayer(preview)

            DispatchQueue.global(qos: .userInitiated).async { [captureSession] in
                captureSession.startRunning()
            }
        }

        override func viewWillDisappear(_ animated: Bool) {
            super.viewWillDisappear(animated)
            captureSession.stopRunning()
        }
    }
}

// MARK: - Portionsval (gram / ml / antal med styckvikt)

struct PortionForm: View {
    @ObservedObject var session: SessionStore
    let food: FoodItemFull
    let dayString: String
    let onLogged: () -> Void

    @State private var grams: Double = 100
    @State private var count = 1
    @State private var useCount = false
    @State private var meal = "lunch"
    @State private var busy = false
    @State private var message: String?

    private var unitLabel: String { food.unit == "ml" ? "ml" : "g" }

    private var effectiveGrams: Double {
        useCount ? Double(count) * (food.serving_g ?? 100) : grams
    }

    var body: some View {
        Form {
            Section {
                Text(food.name).font(.headline)
                if let brand = food.brand {
                    Text(brand).font(.caption).foregroundColor(.secondary)
                }
                Text("\(Int(food.per_100g["kcal"] ?? 0)) kcal per 100 \(unitLabel)")
                    .font(.caption).foregroundColor(.secondary)
            }
            Section("Portion") {
                if let serving = food.serving_g {
                    Picker("Ange som", selection: $useCount) {
                        Text(unitLabel).tag(false)
                        Text("antal").tag(true)
                    }
                    .pickerStyle(.segmented)
                    if useCount {
                        Stepper("\(count) st à \(Int(serving)) \(unitLabel)",
                                value: $count, in: 1...30)
                    }
                }
                if !useCount {
                    HStack {
                        Slider(value: $grams, in: 5...1000, step: 5)
                        Text("\(Int(grams)) \(unitLabel)")
                            .font(.caption).monospacedDigit()
                            .frame(width: 60, alignment: .trailing)
                    }
                }
                Text("= \(Int((food.per_100g["kcal"] ?? 0) * effectiveGrams / 100)) kcal")
                    .font(.subheadline).bold()
                MealPicker(meal: $meal)
            }
            Button(busy ? "Loggar…" : "🍽 Logga") {
                Task { await log() }
            }
            .disabled(busy)
            if let message = message {
                Text(message).font(.footnote).foregroundColor(.red)
            }
        }
        .onAppear {
            if food.serving_g != nil { useCount = true }
        }
    }

    private func log() async {
        busy = true
        defer { busy = false }
        do {
            struct Entry: Decodable { let id: String }
            let _: Entry = try await APIClient.shared.post(
                "api/meals",
                body: ["eaten_on": dayString, "meal": meal,
                       "food_item_id": food.id, "grams": effectiveGrams]
            )
            onLogged()
        } catch {
            message = error.localizedDescription
        }
    }
}

// MARK: - Lägg in egen vara (okänd streckkod)

struct CreateFoodForm: View {
    @ObservedObject var session: SessionStore
    let barcode: String
    let onCreated: (FoodItemFull) -> Void

    @State private var name = ""
    @State private var brand = ""
    @State private var kcal = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var busy = false
    @State private var message: String?

    var body: some View {
        Form {
            Section(footer: Text("Varan (\(barcode)) fanns inte i databasen — lägg in den från förpackningens näringstabell (per 100 g), så hittas den direkt nästa skanning.")) {
                TextField("Namn", text: $name)
                TextField("Märke (valfritt)", text: $brand)
                HStack { Text("kcal"); Spacer()
                    TextField("0", text: $kcal).keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing) }
                HStack { Text("Protein (g)"); Spacer()
                    TextField("0", text: $protein).keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing) }
                HStack { Text("Kolhydrater (g)"); Spacer()
                    TextField("0", text: $carbs).keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing) }
                HStack { Text("Fett (g)"); Spacer()
                    TextField("0", text: $fat).keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing) }
            }
            Button(busy ? "Sparar…" : "💾 Spara varan") {
                Task { await save() }
            }
            .disabled(busy || name.trimmingCharacters(in: .whitespaces).isEmpty)
            if let message = message {
                Text(message).font(.footnote).foregroundColor(.red)
            }
        }
    }

    private func number(_ text: String) -> Double {
        Double(text.replacingOccurrences(of: ",", with: ".")) ?? 0
    }

    private func save() async {
        busy = true
        defer { busy = false }
        do {
            let created: FoodItemFull = try await APIClient.shared.post(
                "api/food",
                body: [
                    "name": name.trimmingCharacters(in: .whitespaces),
                    "brand": brand.trimmingCharacters(in: .whitespaces).isEmpty
                        ? NSNull() : brand.trimmingCharacters(in: .whitespaces),
                    "barcode": barcode,
                    "per_100g": [
                        "kcal": number(kcal), "protein_g": number(protein),
                        "carbs_g": number(carbs), "fat_g": number(fat),
                    ],
                ]
            )
            onCreated(created)
        } catch {
            message = error.localizedDescription
        }
    }
}

// MARK: - 🔍 Sök livsmedel

struct FoodSearchSheet: View {
    @ObservedObject var session: SessionStore
    let dayString: String
    let onDone: () -> Void

    @State private var query = ""
    @State private var results: [FoodItemFull] = []
    @State private var favorites: [FoodItemFull] = []
    @State private var selected: FoodItemFull?
    @State private var searching = false

    var body: some View {
        NavigationView {
            Group {
                if let food = selected {
                    PortionForm(session: session, food: food,
                                dayString: dayString, onLogged: onDone)
                } else {
                    List {
                        TextField("Sök: kycklingfilé, Big Mac, kvarg…", text: $query)
                            .autocapitalization(.none)
                            .onSubmit { Task { await search() } }
                        Button(searching ? "Söker…" : "🔍 Sök") {
                            Task { await search() }
                        }
                        .disabled(query.trimmingCharacters(in: .whitespaces).count < 2)

                        if !results.isEmpty {
                            Section("Träffar") { foodRows(results) }
                        } else if !favorites.isEmpty {
                            Section("⭐ Favoriter") { foodRows(favorites) }
                        }
                    }
                }
            }
            .navigationTitle("Sök livsmedel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Klar") { onDone() }
                }
                if selected != nil {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("‹ Sök") { selected = nil }
                    }
                }
            }
        }
        .onAppear {
            Task {
                favorites = (try? await APIClient.shared.get("api/food/favorites")) ?? []
            }
        }
    }

    private func foodRows(_ foods: [FoodItemFull]) -> some View {
        ForEach(foods) { food in
            Button {
                selected = food
            } label: {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(food.name).font(.subheadline).bold()
                            .foregroundColor(.primary)
                        Text((food.brand.map { "\($0) · " } ?? "")
                             + "\(Int(food.per_100g["kcal"] ?? 0)) kcal/100\(food.unit)")
                            .font(.caption).foregroundColor(.secondary)
                    }
                    Spacer()
                    Image(systemName: "plus.circle").foregroundColor(.accentColor)
                }
            }
        }
    }

    private func search() async {
        searching = true
        defer { searching = false }
        results = (try? await APIClient.shared.get(
            "api/food/search", query: ["q": query]
        )) ?? []
    }
}
