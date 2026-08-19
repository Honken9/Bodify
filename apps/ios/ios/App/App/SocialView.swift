import SwiftUI

// MARK: - Modeller (matchar /api/social)

struct ChallengeItem: Decodable, Identifiable {
    let id: String
    let name: String
    let metric_label: String
    let unit: String
    let kind: String
    let is_open: Bool
    let stake: String?
    let club_name: String?
    let starts_on: String
    let ends_on: String
    let days_left: Int
    let finished: Bool
    let participant_count: Int
    let is_participant: Bool
    let invited: Bool
    let active: Bool
    // Bara i detaljsvaret:
    let leaderboard: [LeaderboardRow]?
    let stages: [StageRow]?
    let head_to_head: HeadToHead?
    let habit: HabitProgress?
}

struct LeaderboardRow: Decodable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let name: String
    let value: Double
    let rank: Int
}

struct StageRow: Decodable, Identifiable {
    var id: Int { index }
    let index: Int
    let completed: Bool
    let current: Bool
    let winner: String?
    let value: Double?
}

struct HeadToHead: Decodable {
    struct Side: Decodable {
        let user_id: String
        let wins: Int
    }
    let a: Side
    let b: Side
    let duels: Int
}

struct HabitProgress: Decodable {
    let completed: Int
    let total: Int
}

struct FeedItem: Decodable, Identifiable {
    var id: String { "\(kind)-\(itemId)" }
    let kind: String
    let itemId: String
    let user_id: String
    let user_name: String
    let title: String
    let when: String
    let detail: String?
    let cheers: Int
    let cheered_by_me: Bool

    enum CodingKeys: String, CodingKey {
        case kind
        case itemId = "id"
        case user_id, user_name, title, when, detail, cheers, cheered_by_me
    }
}

struct LeagueEntry: Decodable, Identifiable {
    var id: String { user_id }
    let rank: Int
    let user_id: String
    let name: String
    let elo: Int
    let is_me: Bool
}

struct FriendBrief: Decodable, Identifiable {
    var id: String { friendship_id }
    let friendship_id: String
    let name: String
    let email: String?
}

struct FriendsData: Decodable {
    let friends: [FriendBrief]
    let incoming: [FriendBrief]
    let outgoing: [FriendBrief]
}

struct ClubItem: Decodable, Identifiable {
    let id: String
    let name: String
    let description: String?
    let invite_code: String?
    let member_count: Int
    let is_admin: Bool
    let members: [ClubMemberRow]?
}

struct ClubMemberRow: Decodable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let name: String
    let elo: Int
    let role: String
    let is_me: Bool
    let rank: Int
}

// MARK: - Socialt-fliken

struct SocialView: View {
    @ObservedObject var session: SessionStore

    @State private var segment = 0
    @State private var challenges: [ChallengeItem] = []
    @State private var league: [LeagueEntry] = []
    @State private var friends: FriendsData?
    @State private var clubs: [ClubItem] = []
    @State private var errorMessage: String?
    @State private var showCreate = false
    @State private var duelOpponent: String?

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Picker("Del", selection: $segment) {
                    Text("🏆 Utmaningar").tag(0)
                    Text("🥇 Ligan").tag(1)
                    Text("👥 Vänner").tag(2)
                    Text("🏟 Ligor").tag(3)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.vertical, 6)

                if let message = errorMessage {
                    ErrorBanner(message: message).padding(.horizontal)
                }

                switch segment {
                case 0:
                    ChallengesList(
                        session: session, challenges: challenges,
                        reload: { await loadChallenges() }
                    )
                case 1:
                    LeagueList(entries: league)
                case 2:
                    FriendsList(
                        session: session, data: friends,
                        onDuel: { email in
                            duelOpponent = email
                            showCreate = true
                        },
                        reload: { await loadFriends() }
                    )
                default:
                    ClubsList(session: session, clubs: clubs, reload: { await loadClubs() })
                }
            }
            .navigationTitle("Socialt")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        duelOpponent = nil
                        showCreate = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showCreate) {
                CreateChallengeSheet(
                    session: session,
                    opponentEmail: duelOpponent,
                    onCreated: {
                        showCreate = false
                        Task { await loadChallenges() }
                        segment = 0
                    }
                )
            }
        }
        .navigationViewStyle(.stack)
        .onAppear { Task { await loadAll() } }
        .onChange(of: segment) { _ in Task { await loadAll() } }
    }

    private func loadAll() async {
        await loadChallenges()
        await loadLeague()
        await loadFriends()
        await loadClubs()
    }

    private func loadChallenges() async {
        do {
            challenges = try await APIClient.shared.get("api/social/challenges")
            errorMessage = nil
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func loadLeague() async {
        league = (try? await APIClient.shared.get("api/social/league")) ?? league
    }

    private func loadFriends() async {
        friends = (try? await APIClient.shared.get("api/social/friends")) ?? friends
    }

    private func loadClubs() async {
        clubs = (try? await APIClient.shared.get("api/social/clubs")) ?? clubs
    }
}

// MARK: - Utmaningar

struct ChallengesList: View {
    @ObservedObject var session: SessionStore
    let challenges: [ChallengeItem]
    let reload: () async -> Void

    @State private var showFinished = false
    @State private var detailId: String?

    private var visible: [ChallengeItem] {
        challenges.filter { $0.finished == showFinished }
    }

    var body: some View {
        List {
            Picker("Status", selection: $showFinished) {
                Text("Pågående").tag(false)
                Text("🏁 Avgjorda").tag(true)
            }
            .pickerStyle(.segmented)
            .listRowSeparator(.hidden)

            ForEach(visible) { challenge in
                Button {
                    detailId = challenge.id
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(icon(for: challenge) + " " + challenge.name)
                                .font(.subheadline).bold()
                                .foregroundColor(.primary)
                            Spacer()
                            Text(challenge.kind == "duel"
                                 ? "duell"
                                 : "\(challenge.participant_count) st")
                                .font(.caption).foregroundColor(.secondary)
                        }
                        Text(subtitle(for: challenge))
                            .font(.caption).foregroundColor(.secondary)
                        if let stake = challenge.stake {
                            Text("🎁 Insats: \(stake)")
                                .font(.caption).foregroundColor(.orange)
                        }
                        if challenge.invited && !challenge.is_participant {
                            Text(challenge.kind == "duel"
                                 ? "⚔️ Du är utmanad till duell!"
                                 : "🎟 Du är inbjuden!")
                                .font(.caption).bold()
                                .foregroundColor(.accentColor)
                        }
                    }
                }
            }
            if visible.isEmpty {
                Text(showFinished ? "Inga avgjorda ännu." : "Inga pågående utmaningar.")
                    .foregroundColor(.secondary)
            }
        }
        .listStyle(.plain)
        .refreshable { await reload() }
        .sheet(item: Binding(
            get: { detailId.map { ChallengeDetailRef(id: $0) } },
            set: { detailId = $0?.id }
        )) { ref in
            ChallengeDetailSheet(session: session, challengeId: ref.id) {
                detailId = nil
                Task { await reload() }
            }
        }
    }

    private func icon(for challenge: ChallengeItem) -> String {
        if challenge.kind == "duel" { return "⚔️" }
        if challenge.finished { return "🏁" }
        return challenge.active ? "🔥" : "📅"
    }

    private func subtitle(for challenge: ChallengeItem) -> String {
        var parts = [challenge.metric_label]
        if let club = challenge.club_name { parts.append("🏟 \(club)") }
        if challenge.active {
            parts.append(challenge.days_left == 0
                         ? "sista dagen!" : "\(challenge.days_left) d kvar")
        } else {
            parts.append("\(challenge.starts_on) → \(challenge.ends_on)")
        }
        return parts.joined(separator: " · ")
    }
}

struct ChallengeDetailRef: Identifiable {
    let id: String
}

struct ChallengeDetailSheet: View {
    @ObservedObject var session: SessionStore
    let challengeId: String
    let onChanged: () -> Void

    @State private var detail: ChallengeItem?
    @State private var feed: [FeedItem] = []
    @State private var busy = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationView {
            List {
                if let message = errorMessage {
                    ErrorBanner(message: message)
                }
                if let detail = detail {
                    if let stake = detail.stake {
                        Text("🎁 Insats: \(stake)").font(.subheadline)
                    }
                    if let habit = detail.habit {
                        Text("✅ \(habit.completed) av \(habit.total) veckor klarade")
                    }
                    if let h2h = detail.head_to_head, h2h.duels > 0,
                       let board = detail.leaderboard {
                        Text("⚔️ Inbördes möten: "
                             + "\(name(for: h2h.a.user_id, board)) \(h2h.a.wins)–"
                             + "\(h2h.b.wins) \(name(for: h2h.b.user_id, board))")
                            .font(.subheadline)
                    }

                    Section("Ställning") {
                        ForEach(detail.leaderboard ?? []) { row in
                            HStack {
                                Text(medal(row.rank)).frame(width: 30)
                                Text(row.name)
                                Spacer()
                                Text("\(trim(row.value)) \(detail.unit)").bold()
                            }
                        }
                    }

                    if let stages = detail.stages, !stages.isEmpty {
                        Section("🏁 Etapper") {
                            ForEach(stages) { stage in
                                HStack {
                                    Text("Etapp \(stage.index)"
                                         + (stage.current ? " · pågår 🔥" : ""))
                                    Spacer()
                                    if let winner = stage.winner {
                                        Text((stage.completed ? "🥇 " : "leder: ") + winner)
                                            .font(.caption)
                                    } else {
                                        Text("–").foregroundColor(.secondary)
                                    }
                                }
                            }
                        }
                    }

                    if !feed.isEmpty {
                        Section("Senaste passen — heja på! 👏") {
                            ForEach(feed.prefix(8)) { item in
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("\(item.user_name) · \(item.title)")
                                            .font(.subheadline)
                                        Text(String(item.when.prefix(10))
                                             + (item.detail.map { " · \($0)" } ?? ""))
                                            .font(.caption).foregroundColor(.secondary)
                                    }
                                    Spacer()
                                    Button {
                                        Task { await cheer(item) }
                                    } label: {
                                        Text("👏 \(item.cheers > 0 ? String(item.cheers) : "")")
                                            .font(.caption).bold()
                                            .padding(.horizontal, 10)
                                            .padding(.vertical, 6)
                                            .background(item.cheered_by_me
                                                        ? Color.green.opacity(0.25)
                                                        : Color(.secondarySystemBackground))
                                            .cornerRadius(14)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                    }

                    if !detail.is_participant && !detail.finished {
                        Button(busy ? "…" : (detail.kind == "duel" ? "⚔️ Anta duellen" : "Gå med")) {
                            Task { await join() }
                        }
                        .disabled(busy)
                        if detail.invited {
                            Button("Tacka nej", role: .destructive) {
                                Task { await decline() }
                            }
                            .disabled(busy)
                        }
                    }
                }
            }
            .navigationTitle(detail?.name ?? "Utmaning")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear { Task { await load() } }
    }

    private func name(for userId: String, _ board: [LeaderboardRow]) -> String {
        board.first { $0.user_id == userId }?.name ?? "?"
    }

    private func medal(_ rank: Int) -> String {
        rank == 1 ? "🥇" : rank == 2 ? "🥈" : rank == 3 ? "🥉" : "\(rank)."
    }

    private func trim(_ value: Double) -> String {
        value == value.rounded()
            ? String(Int(value)) : String(format: "%.1f", value)
    }

    private func load() async {
        do {
            detail = try await APIClient.shared.get("api/social/challenges/\(challengeId)")
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
        if detail?.is_participant == true {
            feed = (try? await APIClient.shared.get(
                "api/social/challenges/\(challengeId)/feed"
            )) ?? []
        }
    }

    private func cheer(_ item: FeedItem) async {
        struct OK: Decodable { let ok: Bool? }
        let _: OK? = try? await APIClient.shared.post(
            "api/social/challenges/\(challengeId)/cheer",
            body: ["item_kind": item.kind, "item_id": item.itemId,
                   "owner_id": item.user_id]
        )
        feed = (try? await APIClient.shared.get(
            "api/social/challenges/\(challengeId)/feed"
        )) ?? feed
    }

    private func join() async {
        busy = true
        defer { busy = false }
        do {
            struct OK: Decodable { let ok: Bool? }
            let _: OK = try await APIClient.shared.post(
                "api/social/challenges/\(challengeId)/join", body: [:]
            )
            onChanged()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func decline() async {
        busy = true
        defer { busy = false }
        do {
            try await APIClient.shared.delete("api/social/challenges/\(challengeId)/invite")
            onChanged()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

// MARK: - Skapa utmaning/duell

struct CreateChallengeSheet: View {
    @ObservedObject var session: SessionStore
    let opponentEmail: String?
    let onCreated: () -> Void

    @State private var kind = "standard"
    @State private var name = ""
    @State private var metric = "steps_total"
    @State private var opponent = ""
    @State private var stake = ""
    @State private var isOpen = false
    @State private var perWeek = 3
    @State private var endDate = Calendar.current.date(byAdding: .day, value: 30, to: Date()) ?? Date()
    @State private var busy = false
    @State private var errorMessage: String?

    private static let metrics: [(String, String)] = [
        ("steps_total", "👟 Flest steg"),
        ("workout_count", "🏋️ Flest pass"),
        ("distance_km", "🏃 Längst distans"),
        ("workout_minutes", "⏱ Flest träningsminuter"),
        ("active_days", "📅 Flest aktiva dagar"),
        ("sleep_score_avg", "😴 Bäst sömnpoäng"),
        ("sleep_hours_avg", "🛌 Mest sömn"),
        ("logged_days", "🥗 Flest loggade kostdagar"),
        ("weight_loss_kg", "⚖️ Störst viktnedgång"),
        ("fat_loss_percent", "📉 Störst fettnedgång"),
    ]

    var body: some View {
        NavigationView {
            Form {
                if let message = errorMessage {
                    ErrorBanner(message: message)
                }
                Picker("Typ", selection: $kind) {
                    Text("🏆 Tävling").tag("standard")
                    Text("⚔️ Duell").tag("duel")
                    Text("✅ Vana").tag("habit")
                }
                .pickerStyle(.segmented)

                TextField("Namn, t.ex. Stegduellen", text: $name)

                if kind == "duel" {
                    TextField("Motståndarens e-post", text: $opponent)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                }
                if kind == "habit" {
                    Stepper("\(perWeek) pass per vecka", value: $perWeek, in: 1...7)
                } else {
                    Picker("Mätetal", selection: $metric) {
                        ForEach(Self.metrics, id: \.0) { key, label in
                            Text(label).tag(key)
                        }
                    }
                }
                DatePicker("Slutdatum", selection: $endDate, displayedComponents: .date)
                TextField("🎁 Insats (valfritt)", text: $stake)
                if kind == "standard" {
                    Toggle("Öppen för alla på Shapiqo", isOn: $isOpen)
                }
                Button(busy ? "Skapar…" : (kind == "duel" ? "⚔️ Skicka utmaningen" : "Skapa")) {
                    Task { await create() }
                }
                .disabled(busy || name.trimmingCharacters(in: .whitespaces).isEmpty
                          || (kind == "duel" && !opponent.contains("@")))
            }
            .navigationTitle(kind == "duel" ? "Ny duell" : "Ny utmaning")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear {
            if let email = opponentEmail {
                kind = "duel"
                opponent = email
            }
        }
    }

    private func create() async {
        busy = true
        errorMessage = nil
        defer { busy = false }
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        var body: [String: Any] = [
            "name": name.trimmingCharacters(in: .whitespaces),
            "metric": metric,
            "starts_on": f.string(from: Date()),
            "ends_on": f.string(from: endDate),
            "kind": kind,
            "is_open": kind == "standard" ? isOpen : false,
        ]
        if kind == "habit" { body["target_per_week"] = perWeek }
        if kind == "duel" {
            body["opponent_email"] = opponent.trimmingCharacters(in: .whitespaces)
        }
        let trimmedStake = stake.trimmingCharacters(in: .whitespaces)
        if !trimmedStake.isEmpty { body["stake"] = trimmedStake }
        do {
            let _: ChallengeItem = try await APIClient.shared.post(
                "api/social/challenges", body: body
            )
            onCreated()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

// MARK: - Shapiqo-ligan

struct LeagueList: View {
    let entries: [LeagueEntry]

    var body: some View {
        List {
            Section(footer: Text("Vinn utmaningar och dueller för att klättra — vinst mot högre rankade ger mer Elo-poäng.")) {
                ForEach(entries) { entry in
                    HStack {
                        Text(entry.rank == 1 ? "🥇" : entry.rank == 2 ? "🥈"
                             : entry.rank == 3 ? "🥉" : "\(entry.rank).")
                            .frame(width: 34)
                        Text(entry.name + (entry.is_me ? " (du)" : ""))
                            .fontWeight(entry.is_me ? .bold : .regular)
                        Spacer()
                        Text("\(entry.elo)").bold().monospacedDigit()
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
    }
}

// MARK: - Vänner

struct FriendsList: View {
    @ObservedObject var session: SessionStore
    let data: FriendsData?
    let onDuel: (String) -> Void
    let reload: () async -> Void

    @State private var email = ""
    @State private var errorMessage: String?

    var body: some View {
        List {
            if let message = errorMessage {
                ErrorBanner(message: message)
            }
            Section("Lägg till vän") {
                HStack {
                    TextField("väns e-postadress", text: $email)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                    Button("Lägg till") { Task { await add() } }
                        .disabled(!email.contains("@"))
                }
            }
            if let incoming = data?.incoming, !incoming.isEmpty {
                Section("Förfrågningar") {
                    ForEach(incoming) { friend in
                        HStack {
                            Text("\(friend.name) vill bli din vän")
                            Spacer()
                            Button("Acceptera") { Task { await accept(friend) } }
                        }
                    }
                }
            }
            Section("Vänner") {
                ForEach(data?.friends ?? []) { friend in
                    HStack {
                        Text("👤 \(friend.name)")
                        Spacer()
                        Button("⚔️ Utmana") {
                            if let email = friend.email { onDuel(email) }
                        }
                        .buttonStyle(.bordered)
                        .font(.caption)
                    }
                }
                if (data?.friends ?? []).isEmpty {
                    Text("Inga vänner ännu — bjud in med e-postadressen de loggar in med.")
                        .font(.footnote).foregroundColor(.secondary)
                }
            }
        }
        .listStyle(.insetGrouped)
        .refreshable { await reload() }
    }

    private func add() async {
        do {
            struct OK: Decodable { let id: String? }
            let _: OK = try await APIClient.shared.post(
                "api/social/friends", body: ["email": email.trimmingCharacters(in: .whitespaces)]
            )
            email = ""
            await reload()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func accept(_ friend: FriendBrief) async {
        struct OK: Decodable { let ok: Bool? }
        let _: OK? = try? await APIClient.shared.post(
            "api/social/friends/\(friend.friendship_id)/accept", body: [:]
        )
        await reload()
    }
}

// MARK: - Egna ligor

struct ClubsList: View {
    @ObservedObject var session: SessionStore
    let clubs: [ClubItem]
    let reload: () async -> Void

    @State private var joinCode = ""
    @State private var newName = ""
    @State private var errorMessage: String?
    @State private var detail: ClubItem?

    var body: some View {
        List {
            if let message = errorMessage {
                ErrorBanner(message: message)
            }
            Section("Gå med / skapa") {
                HStack {
                    TextField("inbjudningskod", text: $joinCode)
                        .autocapitalization(.allCharacters)
                        .disableAutocorrection(true)
                    Button("Gå med") { Task { await join() } }
                        .disabled(joinCode.trimmingCharacters(in: .whitespaces).count < 4)
                }
                HStack {
                    TextField("Ny liga, t.ex. Lunchligan", text: $newName)
                    Button("Skapa") { Task { await create() } }
                        .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            Section("Mina ligor") {
                ForEach(clubs) { club in
                    Button {
                        Task { await open(club) }
                    } label: {
                        HStack {
                            Text("🏟 \(club.name)").foregroundColor(.primary)
                            Spacer()
                            Text("\(club.member_count) medl.")
                                .font(.caption).foregroundColor(.secondary)
                        }
                    }
                }
                if clubs.isEmpty {
                    Text("Du är inte med i någon liga ännu.")
                        .font(.footnote).foregroundColor(.secondary)
                }
            }
        }
        .listStyle(.insetGrouped)
        .refreshable { await reload() }
        .sheet(item: Binding(get: { detail }, set: { detail = $0 })) { club in
            ClubDetailSheet(club: club)
        }
    }

    private func open(_ club: ClubItem) async {
        detail = (try? await APIClient.shared.get("api/social/clubs/\(club.id)")) ?? club
    }

    private func join() async {
        do {
            let _: ClubItem = try await APIClient.shared.post(
                "api/social/clubs/join",
                body: ["code": joinCode.trimmingCharacters(in: .whitespaces)]
            )
            joinCode = ""
            await reload()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }

    private func create() async {
        do {
            let _: ClubItem = try await APIClient.shared.post(
                "api/social/clubs",
                body: ["name": newName.trimmingCharacters(in: .whitespaces)]
            )
            newName = ""
            await reload()
        } catch {
            handleAPIError(error, session: session, message: &errorMessage)
        }
    }
}

struct ClubDetailSheet: View {
    let club: ClubItem

    var body: some View {
        NavigationView {
            List {
                if let description = club.description {
                    Text(description).font(.footnote).foregroundColor(.secondary)
                }
                if let code = club.invite_code {
                    Section("Inbjudningskod") {
                        Text(code).font(.system(.title3, design: .monospaced)).bold()
                        Text("Dela koden — andra går med under Ligor → Gå med.")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
                Section("Ligatabell") {
                    ForEach(club.members ?? []) { member in
                        HStack {
                            Text(member.rank == 1 ? "🥇" : member.rank == 2 ? "🥈"
                                 : member.rank == 3 ? "🥉" : "\(member.rank).")
                                .frame(width: 34)
                            Text(member.name
                                 + (member.role == "admin" ? " ⭐" : "")
                                 + (member.is_me ? " (du)" : ""))
                            Spacer()
                            Text("\(member.elo)").bold().monospacedDigit()
                        }
                    }
                }
            }
            .navigationTitle("🏟 \(club.name)")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
