import SwiftUI

// MARK: - Modeller

struct ExerciseModel: Decodable, Identifiable {
    let id: String
    let name: String
    let muscle_groups: [String]
    let equipment: [String]
}

struct PlannedExercise: Decodable, Identifiable {
    var id: String { exercise_id }
    let exercise_id: String
    let name: String
    let sets: Int
    let reps: String
    let rest_seconds: Int
}

struct GeneratedPlan: Decodable {
    let name: String
    let exercises: [PlannedExercise]
}

// MARK: - Passtyper med muskelkartor

struct WorkoutFocus: Identifiable {
    var id: String { name }
    let name: String
    let focusText: String   // skickas till AI:n
    let muscles: Set<String>
}

let WORKOUT_FOCUSES: [WorkoutFocus] = [
    WorkoutFocus(name: "Push", focusText: "push — bröst, axlar, triceps",
                 muscles: ["bröst", "axlar", "triceps"]),
    WorkoutFocus(name: "Pull", focusText: "pull — rygg, biceps",
                 muscles: ["rygg", "biceps"]),
    WorkoutFocus(name: "Ben", focusText: "ben och säte",
                 muscles: ["ben", "säte"]),
    WorkoutFocus(name: "Core", focusText: "mage och bål",
                 muscles: ["mage"]),
    WorkoutFocus(name: "Armar", focusText: "armar — biceps och triceps",
                 muscles: ["biceps", "triceps"]),
    WorkoutFocus(name: "Helkropp", focusText: "helkropp, balanserat",
                 muscles: ["bröst", "axlar", "triceps", "rygg", "biceps",
                           "ben", "säte", "mage"]),
]

let MUSCLE_GROUPS: [String] = [
    "bröst", "axlar", "biceps", "triceps", "rygg", "mage", "ben", "säte",
]

// MARK: - Muskelfigur (fram + bak, ritad i SwiftUI)

/// Stiliserad kropp med markerade muskelgrupper — fram- och baksida
/// sida vid sida. Markerade grupper lyser lime, övriga är grå.
struct MuscleFigure: View {
    let highlighted: Set<String>

    private let on = Color(red: 0.63, green: 0.90, blue: 0.27)
    private let off = Color.gray.opacity(0.25)

    private func tint(_ group: String) -> Color {
        highlighted.contains(group) ? on : off
    }

    var body: some View {
        HStack(spacing: 14) {
            figure(front: true)
            figure(front: false)
        }
    }

    private func figure(front: Bool) -> some View {
        ZStack {
            // Huvud
            Circle()
                .fill(Color.gray.opacity(0.35))
                .frame(width: 14, height: 14)
                .position(x: 30, y: 9)
            // Axlar
            Capsule()
                .fill(tint("axlar"))
                .frame(width: 44, height: 9)
                .position(x: 30, y: 22)
            // Överarmar: biceps fram, triceps bak
            Capsule()
                .fill(tint(front ? "biceps" : "triceps"))
                .frame(width: 7, height: 22)
                .position(x: 7, y: 37)
            Capsule()
                .fill(tint(front ? "biceps" : "triceps"))
                .frame(width: 7, height: 22)
                .position(x: 53, y: 37)
            // Underarmar
            Capsule()
                .fill(Color.gray.opacity(0.25))
                .frame(width: 6, height: 18)
                .position(x: 6, y: 57)
            Capsule()
                .fill(Color.gray.opacity(0.25))
                .frame(width: 6, height: 18)
                .position(x: 54, y: 57)

            if front {
                // Bröst
                RoundedRectangle(cornerRadius: 4)
                    .fill(tint("bröst"))
                    .frame(width: 26, height: 12)
                    .position(x: 30, y: 30)
                // Mage
                RoundedRectangle(cornerRadius: 3)
                    .fill(tint("mage"))
                    .frame(width: 18, height: 20)
                    .position(x: 30, y: 48)
                // Framsida ben (quadriceps)
                Capsule()
                    .fill(tint("ben"))
                    .frame(width: 10, height: 30)
                    .position(x: 24, y: 74)
                Capsule()
                    .fill(tint("ben"))
                    .frame(width: 10, height: 30)
                    .position(x: 36, y: 74)
            } else {
                // Rygg
                RoundedRectangle(cornerRadius: 4)
                    .fill(tint("rygg"))
                    .frame(width: 26, height: 26)
                    .position(x: 30, y: 37)
                // Säte
                RoundedRectangle(cornerRadius: 5)
                    .fill(tint("säte"))
                    .frame(width: 20, height: 11)
                    .position(x: 30, y: 56)
                // Baksida ben (hamstrings + vader)
                Capsule()
                    .fill(tint("ben"))
                    .frame(width: 10, height: 26)
                    .position(x: 24, y: 74)
                Capsule()
                    .fill(tint("ben"))
                    .frame(width: 10, height: 26)
                    .position(x: 36, y: 74)
            }
        }
        .frame(width: 60, height: 92)
    }
}

// MARK: - Passbyggaren

struct WorkoutBuilderSheet: View {
    @ObservedObject var session: SessionStore
    let onDone: () -> Void

    @State private var mode = 0  // 0 = passtyp, 1 = muskelgrupp
    @State private var minutes = 45
    @State private var selectedFocus: WorkoutFocus?
    @State private var selectedMuscle: String?
    @State private var exercises: [ExerciseModel] = []
    @State private var plan: GeneratedPlan?
    @State private var busy = false
    @State private var message: String?
    @State private var errorMessage: String?

    var body: some View {
        NavigationView {
            List {
                Picker("Läge", selection: $mode) {
                    Text("🏋️ Passtyp").tag(0)
                    Text("💪 Muskelgrupp").tag(1)
                }
                .pickerStyle(.segmented)
                .listRowSeparator(.hidden)

                if let message = errorMessage {
                    ErrorBanner(message: message)
                }

                if mode == 0 {
                    focusGrid
                } else {
                    muscleBrowser
                }

                if selectedFocus != nil || selectedMuscle != nil {
                    Section("Generera pass") {
                        Stepper("\(minutes) minuter", value: $minutes, in: 15...120, step: 5)
                        Button(busy ? "AI:n bygger passet…" : "✨ Föreslå övningar") {
                            Task { await generate() }
                        }
                        .disabled(busy)
                    }
                }

                if let plan = plan {
                    Section(plan.name) {
                        ForEach(plan.exercises) { exercise in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(exercise.name).font(.subheadline).bold()
                                Text("\(exercise.sets) set × \(exercise.reps) · vila \(exercise.rest_seconds) s")
                                    .font(.caption).foregroundColor(.secondary)
                            }
                        }
                        Button(busy ? "Sparar…" : "💾 Spara som pass") {
                            Task { await accept() }
                        }
                        .disabled(busy)
                        if let message = message {
                            Text(message).font(.footnote).foregroundColor(.green)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Bygg pass")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Stäng") { onDone() }
                }
            }
        }
        .onAppear { Task { await loadExercises() } }
    }

    // Passtyps-korten med muskelfigurer
    private var focusGrid: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ForEach(WORKOUT_FOCUSES) { focus in
                Button {
                    selectedFocus = focus
                    selectedMuscle = nil
                    plan = nil
                } label: {
                    VStack(spacing: 6) {
                        MuscleFigure(highlighted: focus.muscles)
                        Text(focus.name)
                            .font(.subheadline).bold()
                            .foregroundColor(.primary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 14)
                            .fill(selectedFocus?.name == focus.name
                                  ? Color.accentColor.opacity(0.15)
                                  : Color(.secondarySystemBackground))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(selectedFocus?.name == focus.name
                                    ? Color.accentColor : Color.clear, lineWidth: 2)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .listRowSeparator(.hidden)
        .padding(.vertical, 4)
    }

    // Muskelgruppsläget: välj grupp → se övningar
    private var muscleBrowser: some View {
        Group {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(MUSCLE_GROUPS, id: \.self) { group in
                        Button {
                            selectedMuscle = group
                            selectedFocus = nil
                            plan = nil
                        } label: {
                            Text(group.capitalized)
                                .font(.caption).bold()
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(selectedMuscle == group
                                            ? Color.accentColor
                                            : Color(.secondarySystemBackground))
                                .foregroundColor(selectedMuscle == group ? .white : .primary)
                                .cornerRadius(16)
                        }
                    }
                }
            }
            .listRowSeparator(.hidden)

            if let muscle = selectedMuscle {
                HStack {
                    MuscleFigure(highlighted: [muscle])
                    Spacer()
                    Text("\(matching(muscle).count) övningar")
                        .font(.caption).foregroundColor(.secondary)
                }
                ForEach(matching(muscle)) { exercise in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(exercise.name).font(.subheadline).bold()
                        Text(exercise.equipment.joined(separator: ", ")
                             + " · " + exercise.muscle_groups.joined(separator: ", "))
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
            }
        }
    }

    private func matching(_ muscle: String) -> [ExerciseModel] {
        exercises.filter { $0.muscle_groups.contains(muscle) }
    }

    private func loadExercises() async {
        exercises = (try? await APIClient.shared.get("api/exercises")) ?? []
    }

    private func generate() async {
        busy = true
        errorMessage = nil
        plan = nil
        message = nil
        defer { busy = false }
        let focus = selectedFocus?.focusText
            ?? selectedMuscle.map { "muskelgrupp: \($0)" }
            ?? "helkropp"
        do {
            plan = try await APIClient.shared.post(
                "api/ai/generate-workout",
                body: ["minutes": minutes, "focus": focus],
                timeout: 120
            )
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func accept() async {
        guard let plan = plan else { return }
        busy = true
        defer { busy = false }
        let planDict: [String: Any] = [
            "name": plan.name,
            "exercises": plan.exercises.map {
                [
                    "exercise_id": $0.exercise_id,
                    "name": $0.name,
                    "sets": $0.sets,
                    "reps": $0.reps,
                    "rest_seconds": $0.rest_seconds,
                ] as [String: Any]
            },
        ]
        do {
            struct OK: Decodable { let day_id: String? }
            let _: OK = try await APIClient.shared.post(
                "api/ai/generate-workout/accept", body: ["plan": planDict]
            )
            message = "✅ Sparat! Passet finns under dina program och kan köras direkt."
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}
