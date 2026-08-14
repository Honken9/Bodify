"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

type Brief = { friendship_id: string; id: string; name: string; email: string };
type FriendsData = { friends: Brief[]; incoming: Brief[]; outgoing: Brief[] };

type Challenge = {
  id: string;
  name: string;
  metric: string;
  metric_label: string;
  unit: string;
  kind: string;
  target: { per_week?: number } | null;
  is_open: boolean;
  stake: string | null;
  club_id: string | null;
  club_name: string | null;
  starts_on: string;
  ends_on: string;
  days_left: number;
  finished: boolean;
  participant_count: number;
  is_participant: boolean;
  is_creator: boolean;
  invited: boolean;
  active: boolean;
  leaderboard?: LeaderboardRow[];
  history?: RaceHistory;
  habit?: { completed: number; total: number };
  stages?: Stage[];
  head_to_head?: H2H;
};

type Stage = {
  index: number;
  start: string;
  end: string;
  completed: boolean;
  current: boolean;
  winner: string | null;
  value: number | null;
};

type H2H = {
  a: { user_id: string; wins: number };
  b: { user_id: string; wins: number };
  duels: number;
};

type LeagueRow = {
  rank: number;
  user_id: string;
  name: string;
  elo: number;
  is_me: boolean;
};

type Club = {
  id: string;
  name: string;
  description: string | null;
  invite_code: string | null;
  member_count: number;
  is_member: boolean;
  is_admin: boolean;
};

type ClubDetail = Club & {
  members: {
    user_id: string;
    name: string;
    elo: number;
    role: string;
    is_me: boolean;
    rank: number;
  }[];
  challenges: Challenge[];
};

type LeaderboardRow = {
  user_id: string;
  name: string;
  value: number;
  rank: number;
};

type RaceHistory = {
  days: string[];
  series: { user_id: string; name: string; values: number[] }[];
};

type FeedItem = {
  kind: string;
  id: string;
  user_id: string;
  user_name: string;
  title: string;
  when: string;
  detail: string | null;
  cheers: number;
  cheered_by_me: boolean;
};

const METRIC_OPTIONS = [
  ["steps_total", "👟 Flest steg"],
  ["workout_count", "🏋️ Flest pass"],
  ["distance_km", "🏃 Längst distans"],
  ["workout_minutes", "⏱ Flest träningsminuter"],
  ["active_days", "📅 Flest aktiva dagar"],
  ["sleep_score_avg", "😴 Bäst sömnpoäng (snitt)"],
  ["sleep_hours_avg", "🛌 Mest sömn (snitt/natt)"],
  ["logged_days", "🥗 Flest loggade kostdagar"],
  ["weight_loss_kg", "⚖️ Störst viktnedgång (kg)"],
  ["fat_loss_percent", "📉 Störst fettnedgång (%-enheter)"],
] as const;

const RACE_COLORS = [
  "#23588a",
  "#7fc22b",
  "#dc2626",
  "#8b5cf6",
  "#f59e0b",
  "#0d9488",
];

function medal(rank: number): string {
  return rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : `${rank}.`;
}

function nameFor(challenge: Challenge, userId: string): string {
  return (
    challenge.leaderboard?.find((r) => r.user_id === userId)?.name ?? "?"
  );
}

/** Race-kurvor: en linje per deltagare, från nattliga snapshots. */
function RaceChart({ history }: { history: RaceHistory }) {
  if (history.days.length < 2 || history.series.length === 0) {
    return (
      <p className="mt-2 rounded-lg bg-cream-deep px-3 py-2 text-xs text-muted dark:bg-night-shell/60 dark:text-faint">
        📈 Race-kurvorna ritas när utmaningen samlat några dagars data.
      </p>
    );
  }
  const W = 300;
  const H = 110;
  const max = Math.max(...history.series.flatMap((s) => s.values), 1);
  const x = (i: number) => (i / (history.days.length - 1)) * (W - 10) + 5;
  const y = (v: number) => H - 8 - (v / max) * (H - 16);

  return (
    <div className="mt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {history.series.map((s, si) => (
          <polyline
            key={s.user_id}
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
            fill="none"
            stroke={RACE_COLORS[si % RACE_COLORS.length]}
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {history.series.map((s, si) => {
          const last = s.values[s.values.length - 1];
          return (
            <circle
              key={`d${s.user_id}`}
              cx={x(s.values.length - 1)}
              cy={y(last)}
              r="3.5"
              fill={RACE_COLORS[si % RACE_COLORS.length]}
            />
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {history.series.map((s, si) => (
          <span key={s.user_id} className="flex items-center gap-1 text-xs">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: RACE_COLORS[si % RACE_COLORS.length] }}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Aktivitetsflöde med 👏 i en utmaning. */
function ChallengeFeed({ challengeId }: { challengeId: string }) {
  const [items, setItems] = useState<FeedItem[] | null>(null);

  const load = useCallback(() => {
    api<FeedItem[]>(`/api/social/challenges/${challengeId}/feed`)
      .then(setItems)
      .catch(() => setItems([]));
  }, [challengeId]);
  useEffect(load, [load]);

  async function cheer(item: FeedItem) {
    setItems(
      (prev) =>
        prev?.map((i) =>
          i.id === item.id
            ? {
                ...i,
                cheered_by_me: !i.cheered_by_me,
                cheers: i.cheers + (i.cheered_by_me ? -1 : 1),
              }
            : i
        ) ?? null
    );
    try {
      await api(`/api/social/challenges/${challengeId}/cheer`, {
        method: "POST",
        body: JSON.stringify({
          item_kind: item.kind,
          item_id: item.id,
          owner_id: item.user_id,
        }),
      });
    } catch {
      load();
    }
  }

  if (!items || items.length === 0) return null;
  const fmt = new Intl.DateTimeFormat("sv-SE", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  return (
    <div className="mt-3 border-t border-line pt-2 dark:border-night-shell">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">
        Senaste passen
      </p>
      <ul className="space-y-1">
        {items.slice(0, 8).map((item) => (
          <li
            key={`${item.kind}-${item.id}`}
            className="flex items-center gap-2 text-sm"
          >
            <span className="min-w-0 flex-1 truncate">
              <strong>{item.user_name}</strong>{" "}
              {item.kind === "strength" ? "🏋️" : "🏃"} {item.title}
              <span className="text-xs text-faint">
                {" "}
                · {fmt.format(new Date(item.when))}
                {item.detail ? ` · ${item.detail}` : ""}
              </span>
            </span>
            <button
              onClick={() => cheer(item)}
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                item.cheered_by_me
                  ? "bg-lime text-lime-ink"
                  : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
              }`}
            >
              👏 {item.cheers > 0 ? item.cheers : ""}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Shapiqo-ligan: Elo-rankning som uppdateras när tävlingar avgörs. */
function LeagueSection() {
  const [rows, setRows] = useState<LeagueRow[] | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    api<LeagueRow[]>("/api/social/league").then(setRows).catch(() => {});
  }, []);

  if (!rows || rows.length < 2) return null;
  const myIndex = rows.findIndex((r) => r.is_me);
  const visible = showAll
    ? rows
    : rows.slice(0, Math.max(5, myIndex >= 0 ? myIndex + 1 : 0));

  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">🏆 Shapiqo-ligan</h2>
        <span className="text-xs text-faint">Elo-poäng</span>
      </div>
      <p className="mt-0.5 text-xs text-muted dark:text-faint">
        Vinn utmaningar och dueller för att klättra — vinst mot högre rankade
        ger mer poäng.
      </p>
      <ol className="mt-2 space-y-1">
        {visible.map((r) => (
          <li
            key={r.user_id}
            className={`flex items-center justify-between rounded-lg px-2 py-1 text-sm ${
              r.is_me
                ? "bg-navy-soft font-semibold dark:bg-night-shell"
                : ""
            }`}
          >
            <span>
              <span className="mr-2 inline-block w-6 font-bold">
                {medal(r.rank)}
              </span>
              {r.name}
              {r.is_me ? " (du)" : ""}
            </span>
            <span className="font-semibold tabular-nums">{r.elo}</span>
          </li>
        ))}
      </ol>
      {rows.length > visible.length && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-2 text-xs font-semibold text-navy dark:text-lime"
        >
          Visa alla {rows.length} →
        </button>
      )}
    </section>
  );
}

/** Egna ligor: skapa, gå med via kod, medlemsliga på Elo, ligautmaningar. */
function ClubsSection({
  onStartChallenge,
  refreshKey,
  onError,
}: {
  onStartChallenge: (club: { id: string; name: string }) => void;
  refreshKey: number;
  onError: (m: string) => void;
}) {
  const [clubs, setClubs] = useState<Club[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClubDetail | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    api<Club[]>("/api/social/clubs").then(setClubs).catch(() => {});
  }, []);
  useEffect(load, [load, refreshKey]);

  useEffect(() => {
    if (expanded) {
      api<ClubDetail>(`/api/social/clubs/${expanded}`)
        .then(setDetail)
        .catch(() => setDetail(null));
    } else {
      setDetail(null);
    }
  }, [expanded, refreshKey]);

  async function create() {
    try {
      await api("/api/social/clubs", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      setName("");
      setDescription("");
      setShowCreate(false);
      load();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function join() {
    try {
      await api("/api/social/clubs/join", {
        method: "POST",
        body: JSON.stringify({ code: joinCode.trim() }),
      });
      setJoinCode("");
      load();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function inviteMember(clubId: string) {
    const email = window.prompt(
      "Vem vill du bjuda in? Ange e-postadressen personen loggar in med:"
    );
    if (!email?.includes("@")) return;
    try {
      await api(`/api/social/clubs/${clubId}/invite`, {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      window.alert(`Inbjudan skickad till ${email.trim()}! 🏟`);
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function leave(club: ClubDetail) {
    const doomed = club.member_count === 1;
    if (
      !window.confirm(
        doomed
          ? `Du är sista medlemmen — ligan ${club.name} raderas. Fortsätta?`
          : `Lämna ligan ${club.name}?`
      )
    )
      return;
    try {
      await api(`/api/social/clubs/${club.id}/leave`, { method: "POST" });
      setExpanded(null);
      load();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function removeClub(club: ClubDetail) {
    if (
      !window.confirm(
        `Radera ligan ${club.name}? Utmaningarna finns kvar men kopplingen försvinner.`
      )
    )
      return;
    try {
      await api(`/api/social/clubs/${club.id}`, { method: "DELETE" });
      setExpanded(null);
      load();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  function copyCode(code: string) {
    navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const inputCls =
    "min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong";

  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">🏟 Egna ligor</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-sm text-navy dark:text-lime"
        >
          + Ny liga
        </button>
      </div>
      <p className="mt-0.5 text-xs text-muted dark:text-faint">
        Skapa en liga för gänget, jobbet eller familjen — egen Elo-tabell och
        utmaningar som når alla medlemmar.
      </p>

      {showCreate && (
        <div className="mt-2 space-y-2 rounded-xl bg-sand p-3 dark:bg-night-shell">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Namn, t.ex. Lunchligan"
            className={`${inputCls} w-full`}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Beskrivning (valfritt)"
            className={`${inputCls} w-full`}
          />
          <button
            disabled={!name.trim()}
            onClick={create}
            className="w-full rounded-xl bg-navy py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            Skapa ligan
          </button>
        </div>
      )}

      <div className="mt-2 flex gap-2">
        <input
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
          placeholder="inbjudningskod, t.ex. KX7M2P"
          maxLength={8}
          className={`${inputCls} uppercase tracking-widest`}
        />
        <button
          disabled={joinCode.trim().length < 4}
          onClick={join}
          className="rounded-xl bg-navy px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          Gå med
        </button>
      </div>

      <ul className="mt-2 space-y-2">
        {clubs?.map((club) => (
          <li
            key={club.id}
            className="rounded-xl border border-line p-3 dark:border-night-shell"
          >
            <button
              className="w-full text-left"
              onClick={() =>
                setExpanded(expanded === club.id ? null : club.id)
              }
            >
              <div className="flex items-center justify-between">
                <p className="font-semibold">🏟 {club.name}</p>
                <span className="text-xs text-faint">
                  {club.member_count}{" "}
                  {club.member_count === 1 ? "medlem" : "medlemmar"}
                </span>
              </div>
              {club.description && (
                <p className="mt-0.5 text-xs text-muted dark:text-faint">
                  {club.description}
                </p>
              )}
            </button>

            {expanded === club.id && detail && (
              <div className="mt-2 border-t border-line pt-2 dark:border-night-shell">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">
                  Ligatabell
                </p>
                <ol className="space-y-0.5">
                  {detail.members.map((m) => (
                    <li
                      key={m.user_id}
                      className={`flex items-center justify-between rounded-lg px-2 py-1 text-sm ${
                        m.is_me
                          ? "bg-navy-soft font-semibold dark:bg-night-shell"
                          : ""
                      }`}
                    >
                      <span>
                        <span className="mr-2 inline-block w-6 font-bold">
                          {medal(m.rank)}
                        </span>
                        {m.name}
                        {m.role === "admin" ? " ⭐" : ""}
                        {m.is_me ? " (du)" : ""}
                      </span>
                      <span className="font-semibold tabular-nums">
                        {m.elo}
                      </span>
                    </li>
                  ))}
                </ol>

                {detail.challenges.filter((c) => !c.finished).length > 0 && (
                  <>
                    <p className="mb-1 mt-2 text-xs font-semibold uppercase tracking-wide text-faint">
                      Ligans utmaningar
                    </p>
                    <ul className="space-y-0.5 text-sm">
                      {detail.challenges
                        .filter((c) => !c.finished)
                        .map((c) => (
                          <li
                            key={c.id}
                            className="flex items-center justify-between"
                          >
                            <span className="truncate">
                              {c.active ? "🔥" : "📅"} {c.name}
                            </span>
                            <span className="shrink-0 text-xs text-faint">
                              {c.active
                                ? `${c.days_left} d kvar`
                                : c.starts_on}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </>
                )}

                {detail.invite_code && (
                  <button
                    onClick={() => copyCode(detail.invite_code!)}
                    className="mt-2 w-full rounded-xl bg-sand py-2 text-sm font-semibold text-sand-ink dark:bg-night-shell dark:text-lime"
                  >
                    {copied
                      ? "✅ Kopierad!"
                      : `📋 Inbjudningskod: ${detail.invite_code}`}
                  </button>
                )}

                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() =>
                      onStartChallenge({ id: club.id, name: club.name })
                    }
                    className="flex-1 rounded-xl bg-navy py-2 text-sm font-semibold text-white"
                  >
                    🏆 Ny ligautmaning
                  </button>
                  <button
                    onClick={() => inviteMember(club.id)}
                    className="rounded-xl border border-navy-line px-3 py-2 text-sm font-semibold text-navy-deep dark:border-night-strong dark:text-lime"
                  >
                    ➕ Bjud in
                  </button>
                </div>
                <div className="mt-1.5 flex justify-end gap-3 text-xs">
                  <button
                    onClick={() => leave(detail)}
                    className="text-muted underline dark:text-night-muted"
                  >
                    Lämna ligan
                  </button>
                  {detail.is_admin && (
                    <button
                      onClick={() => removeClub(detail)}
                      className="text-red-600 underline dark:text-red-400"
                    >
                      Radera
                    </button>
                  )}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      {clubs && clubs.length === 0 && (
        <p className="mt-2 text-sm text-faint">
          Du är inte med i någon liga ännu — skapa en eller gå med via kod.
        </p>
      )}
    </section>
  );
}

export default function SocialPage() {
  const [friends, setFriends] = useState<FriendsData | null>(null);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [email, setEmail] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Challenge | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [duelTarget, setDuelTarget] = useState<Brief | null>(null);
  const [clubTarget, setClubTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [clubRefresh, setClubRefresh] = useState(0);
  const [showFinished, setShowFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<FriendsData>("/api/social/friends").then(setFriends).catch(() => {});
    api<Challenge[]>("/api/social/challenges")
      .then(setChallenges)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  useEffect(() => {
    if (expanded) {
      api<Challenge>(`/api/social/challenges/${expanded}`)
        .then(setDetail)
        .catch(() => setDetail(null));
    } else {
      setDetail(null);
    }
  }, [expanded]);

  async function addFriend() {
    setError(null);
    try {
      await api("/api/social/friends", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      setEmail("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function accept(friendshipId: string) {
    await api(`/api/social/friends/${friendshipId}/accept`, { method: "POST" });
    refresh();
  }

  async function join(challengeId: string) {
    setError(null);
    try {
      await api(`/api/social/challenges/${challengeId}/join`, {
        method: "POST",
      });
      refresh();
      if (expanded === challengeId) {
        api<Challenge>(`/api/social/challenges/${challengeId}`).then(setDetail);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function invite(challengeId: string) {
    const inviteEmail = window.prompt(
      "Vem vill du bjuda in? Ange e-postadressen personen loggar in med:"
    );
    if (!inviteEmail?.includes("@")) return;
    setError(null);
    try {
      await api(`/api/social/challenges/${challengeId}/invite`, {
        method: "POST",
        body: JSON.stringify({ email: inviteEmail.trim() }),
      });
      window.alert(`Inbjudan skickad till ${inviteEmail.trim()}! 🏆`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function decline(challengeId: string) {
    setError(null);
    try {
      await api(`/api/social/challenges/${challengeId}/invite`, {
        method: "DELETE",
      });
      setExpanded(null);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function startRematch(challengeId: string) {
    setError(null);
    try {
      await api(`/api/social/challenges/${challengeId}/rematch`, {
        method: "POST",
      });
      setExpanded(null);
      refresh();
      window.alert("Revanschen är igång — alla deltagare har bjudits in! 🔄");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const current = challenges.filter((c) => !c.finished);
  const finished = challenges.filter((c) => c.finished);
  const visible = showFinished ? finished : current;

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Socialt</h1>
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
        <h2 className="font-bold">Vänner</h2>
        <div className="mt-2 flex gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="väns e-postadress"
            className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong"
          />
          <button
            disabled={!email.includes("@")}
            onClick={addFriend}
            className="rounded-xl bg-navy px-4 text-sm font-semibold text-white disabled:opacity-40"
          >
            Lägg till
          </button>
        </div>

        {friends?.incoming.map((f) => (
          <div
            key={f.friendship_id}
            className="mt-2 flex items-center justify-between rounded-xl bg-sand px-3 py-2 text-sm dark:bg-night-shell"
          >
            <span>
              <strong>{f.name}</strong> vill bli din vän
            </span>
            <button
              onClick={() => accept(f.friendship_id)}
              className="rounded-lg bg-navy px-3 py-1 text-xs font-semibold text-white"
            >
              Acceptera
            </button>
          </div>
        ))}

        <ul className="mt-2 space-y-1">
          {friends?.friends.map((f) => (
            <li
              key={f.friendship_id}
              className="flex items-center justify-between gap-2 py-1 text-sm"
            >
              <span className="min-w-0 flex-1 truncate font-medium">
                👤 {f.name}
              </span>
              <button
                onClick={() => setDuelTarget(f)}
                className="shrink-0 rounded-full bg-shell px-2.5 py-1 text-xs font-semibold text-navy-deep dark:bg-night-shell dark:text-lime"
              >
                ⚔️ Utmana
              </button>
            </li>
          ))}
          {friends && friends.friends.length === 0 && (
            <p className="mt-2 text-sm text-faint">
              Inga vänner ännu — bjud in med e-postadressen de loggar in med.
            </p>
          )}
          {friends?.outgoing.map((f) => (
            <li key={f.friendship_id} className="py-1 text-sm text-faint">
              ⏳ {f.name} (väntar på svar)
            </li>
          ))}
        </ul>
      </section>

      <ClubsSection
        onStartChallenge={setClubTarget}
        refreshKey={clubRefresh}
        onError={setError}
      />

      <LeagueSection />

      <section>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex gap-1.5">
            {(
              [
                [false, "Pågående"],
                [true, "🏆 Avgjorda"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={String(key)}
                onClick={() => setShowFinished(key)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                  showFinished === key
                    ? "bg-navy text-white"
                    : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="text-sm text-navy dark:text-lime"
          >
            + Ny utmaning
          </button>
        </div>

        {visible.length === 0 && (
          <p className="rounded-xl border border-dashed border-line-strong p-4 text-center text-sm text-faint dark:border-night-strong">
            {showFinished
              ? "Inga avgjorda utmaningar ännu."
              : "Skapa en utmaning och bjud in vännerna — steg, pass, sömn, distans… 🏆"}
          </p>
        )}

        <ul className="space-y-2 desktop:grid desktop:grid-cols-2 desktop:gap-3 desktop:space-y-0">
          {visible.map((c) => (
            <li
              key={c.id}
              className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card"
            >
              <button
                className="w-full text-left"
                onClick={() => setExpanded(expanded === c.id ? null : c.id)}
              >
                <div className="flex items-center justify-between">
                  <p className="font-bold">
                    {c.kind === "duel"
                      ? "⚔️ "
                      : c.finished
                        ? "🏁 "
                        : c.active
                          ? "🔥 "
                          : "📅 "}
                    {c.name}
                  </p>
                  <span className="shrink-0 text-xs text-faint">
                    {c.kind === "duel" ? "duell" : `${c.participant_count} deltagare`}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted dark:text-faint">
                  {c.metric_label}
                  {c.club_name ? ` · 🏟 ${c.club_name}` : ""}
                  {c.is_open ? " · öppen för alla" : ""}
                  {c.active
                    ? ` · ${c.days_left === 0 ? "sista dagen!" : `${c.days_left} d kvar`}`
                    : ` · ${c.starts_on} → ${c.ends_on}`}
                </p>
                {c.stake && (
                  <p className="mt-1 text-xs font-medium text-sand-ink dark:text-lime">
                    🎁 Insats: {c.stake}
                  </p>
                )}
              </button>

              {c.active && c.days_left === 0 && c.is_participant && (
                <p className="mt-2 animate-pulse rounded-lg bg-red-50 px-3 py-1.5 text-xs font-bold text-red-700 dark:bg-red-950 dark:text-red-300">
                  🏁 Slutspurt — sista dagen, allt kan hända!
                </p>
              )}

              {c.invited && !c.is_participant && (
                <p className="mt-2 rounded-lg bg-navy-soft px-3 py-1.5 text-xs font-medium text-navy-deep dark:bg-night-shell dark:text-lime">
                  {c.kind === "duel"
                    ? "⚔️ Du är utmanad till duell!"
                    : "🎟 Du är inbjuden till den här utmaningen!"}
                </p>
              )}

              {!c.is_participant && !c.finished && (
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => join(c.id)}
                    className="flex-1 rounded-xl bg-navy py-2 text-sm font-semibold text-white"
                  >
                    {c.kind === "duel" ? "⚔️ Anta duellen" : "Gå med"}
                  </button>
                  {c.invited && (
                    <button
                      onClick={() => decline(c.id)}
                      className="rounded-xl border border-line-strong px-3 py-2 text-sm font-semibold text-muted dark:border-night-strong dark:text-night-muted"
                    >
                      Tacka nej
                    </button>
                  )}
                </div>
              )}

              {c.is_participant && !c.finished && (
                <button
                  onClick={() => invite(c.id)}
                  className="mt-2 w-full rounded-xl border border-navy-line py-2 text-sm font-semibold text-navy-deep dark:border-night-strong dark:text-lime"
                >
                  ➕ Bjud in till utmaningen
                </button>
              )}

              {expanded === c.id && detail && (
                <div className="mt-3 border-t border-line pt-3 dark:border-night-shell">
                  {detail.finished && detail.leaderboard?.[0] && (
                    <p className="mb-2 rounded-xl bg-sand p-3 text-center text-sm font-bold text-sand-ink dark:bg-night-shell dark:text-lime">
                      🏆 {detail.leaderboard[0].name} vann med{" "}
                      {detail.leaderboard[0].value} {detail.unit}!
                    </p>
                  )}

                  {detail.habit && (
                    <p className="mb-2 rounded-lg bg-cream-deep px-3 py-2 text-sm dark:bg-night-shell/60">
                      ✅ Du har klarat{" "}
                      <strong>
                        {detail.habit.completed} av {detail.habit.total}
                      </strong>{" "}
                      veckor
                    </p>
                  )}

                  {detail.head_to_head && detail.head_to_head.duels > 0 && (
                    <p className="mb-2 rounded-lg bg-cream-deep px-3 py-2 text-center text-sm dark:bg-night-shell/60">
                      ⚔️ Inbördes möten:{" "}
                      <strong>
                        {nameFor(detail, detail.head_to_head.a.user_id)}{" "}
                        {detail.head_to_head.a.wins}–
                        {detail.head_to_head.b.wins}{" "}
                        {nameFor(detail, detail.head_to_head.b.user_id)}
                      </strong>{" "}
                      ({detail.head_to_head.duels} dueller)
                    </p>
                  )}

                  <ol className="space-y-1">
                    {detail.leaderboard?.map((row) => (
                      <li
                        key={row.user_id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>
                          <span className="mr-2 inline-block w-6 font-bold">
                            {medal(row.rank)}
                          </span>
                          {row.name}
                        </span>
                        <span className="font-semibold">
                          {row.value} {detail.unit}
                        </span>
                      </li>
                    ))}
                  </ol>

                  {detail.history && <RaceChart history={detail.history} />}

                  {detail.stages && detail.stages.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">
                        🏁 Etapper — en vinnare varje vecka
                      </p>
                      <ul className="space-y-1">
                        {detail.stages.map((s) => (
                          <li
                            key={s.index}
                            className={`flex items-center justify-between rounded-lg px-2 py-1 text-sm ${
                              s.current
                                ? "bg-navy-soft font-medium dark:bg-night-shell"
                                : ""
                            }`}
                          >
                            <span>
                              Etapp {s.index}
                              {s.current ? " · pågår 🔥" : ""}
                            </span>
                            <span className="text-xs">
                              {s.winner ? (
                                <>
                                  {s.completed ? "🥇 " : "leder: "}
                                  <strong>{s.winner}</strong> · {s.value}{" "}
                                  {detail.unit}
                                </>
                              ) : s.completed || s.current ? (
                                <span className="text-faint">ingen data</span>
                              ) : (
                                <span className="text-faint">
                                  {s.start.slice(5)} →
                                </span>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {c.is_participant && <ChallengeFeed challengeId={c.id} />}

                  {detail.finished && c.is_participant && (
                    <button
                      onClick={() => startRematch(c.id)}
                      className="mt-3 w-full rounded-xl bg-navy py-2.5 text-sm font-semibold text-white"
                    >
                      🔄 Revansch — kör igen!
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      {(showCreate || duelTarget || clubTarget) && (
        <CreateChallenge
          duelOpponent={duelTarget}
          club={clubTarget}
          onClose={() => {
            setShowCreate(false);
            setDuelTarget(null);
            setClubTarget(null);
          }}
          onCreated={() => {
            setShowCreate(false);
            setDuelTarget(null);
            setClubTarget(null);
            setClubRefresh((n) => n + 1);
            refresh();
          }}
          onError={setError}
        />
      )}
    </main>
  );
}

function CreateChallenge({
  duelOpponent,
  club,
  onClose,
  onCreated,
  onError,
}: {
  duelOpponent: Brief | null;
  club: { id: string; name: string } | null;
  onClose: () => void;
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const today = new Date().toLocaleDateString("sv-SE");
  const monthAhead = new Date(Date.now() + 30 * 86400_000).toLocaleDateString(
    "sv-SE"
  );
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"standard" | "habit" | "duel">(
    duelOpponent ? "duel" : "standard"
  );
  const [opponent, setOpponent] = useState(duelOpponent?.email ?? "");
  const [metric, setMetric] = useState("steps_total");
  const [perWeek, setPerWeek] = useState("3");
  const [stake, setStake] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(monthAhead);
  const [saving, setSaving] = useState(false);

  const inputCls =
    "w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong";

  async function save() {
    setSaving(true);
    try {
      await api("/api/social/challenges", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          metric,
          starts_on: start,
          ends_on: end,
          kind,
          target_per_week: kind === "habit" ? Number(perWeek) || 3 : null,
          is_open: kind === "duel" || club ? false : isOpen,
          stake: stake.trim() || null,
          opponent_email: kind === "duel" ? opponent.trim() : null,
          club_id: club?.id ?? null,
        }),
      });
      onCreated();
    } catch (e) {
      onError((e as Error).message);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-lg font-bold">
          {club
            ? `🏟 Ny utmaning i ${club.name}`
            : kind === "duel"
              ? "⚔️ Ny duell"
              : "Ny utmaning"}
        </h3>
        <div className="space-y-3">
          <div className="flex gap-1.5">
            {(
              club
                ? ([
                    ["standard", "🏆 Tävling"],
                    ["habit", "✅ Vana"],
                  ] as const)
                : ([
                    ["standard", "🏆 Tävling"],
                    ["duel", "⚔️ Duell"],
                    ["habit", "✅ Vana"],
                  ] as const)
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setKind(key)}
                className={`flex-1 rounded-xl py-2.5 text-sm font-semibold ${
                  kind === key
                    ? "bg-navy text-white"
                    : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {kind === "duel" && (
            <input
              type="email"
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
              placeholder="motståndarens e-postadress"
              className={inputCls}
            />
          )}

          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={
              kind === "habit"
                ? "Namn, t.ex. Träningsvanan"
                : kind === "duel"
                  ? "Namn, t.ex. Stegduellen"
                  : "Namn, t.ex. Sommarslaget"
            }
            className={inputCls}
          />

          {kind !== "habit" ? (
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
              className={inputCls}
            >
              {METRIC_OPTIONS.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          ) : (
            <label className="flex items-center gap-3">
              <input
                inputMode="numeric"
                value={perWeek}
                onChange={(e) => setPerWeek(e.target.value)}
                className="w-20 rounded-xl border border-line-strong bg-transparent px-3 py-2.5 text-center font-semibold dark:border-night-strong"
              />
              <span className="text-sm text-muted dark:text-faint">
                pass per vecka — alla som håller det hela perioden klarar
                utmaningen
              </span>
            </label>
          )}

          <div className="flex gap-2">
            <label className="flex-1">
              <span className="text-xs text-faint">Start</span>
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="flex-1">
              <span className="text-xs text-faint">Slut</span>
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className={inputCls}
              />
            </label>
          </div>

          <label className="block">
            <span className="text-xs text-faint">
              🎁 Insats (valfritt) — vad vinnaren får
            </span>
            <input
              value={stake}
              onChange={(e) => setStake(e.target.value)}
              maxLength={200}
              placeholder="t.ex. förloraren bjuder på lunch"
              className={inputCls}
            />
          </label>

          {kind !== "duel" && !club && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isOpen}
                onChange={(e) => setIsOpen(e.target.checked)}
                className="h-4 w-4 accent-[#23588a]"
              />
              Öppen för alla på Shapiqo (ingen inbjudan behövs)
            </label>
          )}

          <button
            disabled={
              saving ||
              !name.trim() ||
              (kind === "duel" && !opponent.includes("@"))
            }
            onClick={save}
            className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
          >
            {kind === "duel" ? "⚔️ Skicka utmaningen" : "Skapa utmaning"}
          </button>
        </div>
      </div>
    </div>
  );
}
