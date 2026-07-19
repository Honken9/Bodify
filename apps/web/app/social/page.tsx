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

export default function SocialPage() {
  const [friends, setFriends] = useState<FriendsData | null>(null);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [email, setEmail] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Challenge | null>(null);
  const [showCreate, setShowCreate] = useState(false);
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
              className="flex items-center justify-between py-1 text-sm"
            >
              <span className="font-medium">👤 {f.name}</span>
              <span className="text-xs text-faint">{f.email}</span>
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
                    {c.finished ? "🏁 " : c.active ? "🔥 " : "📅 "}
                    {c.name}
                  </p>
                  <span className="shrink-0 text-xs text-faint">
                    {c.participant_count} deltagare
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted dark:text-faint">
                  {c.metric_label}
                  {c.is_open ? " · öppen för alla" : ""}
                  {c.active
                    ? ` · ${c.days_left === 0 ? "sista dagen!" : `${c.days_left} d kvar`}`
                    : ` · ${c.starts_on} → ${c.ends_on}`}
                </p>
              </button>

              {c.invited && !c.is_participant && (
                <p className="mt-2 rounded-lg bg-navy-soft px-3 py-1.5 text-xs font-medium text-navy-deep dark:bg-night-shell dark:text-lime">
                  🎟 Du är inbjuden till den här utmaningen!
                </p>
              )}

              {!c.is_participant && !c.finished && (
                <button
                  onClick={() => join(c.id)}
                  className="mt-2 w-full rounded-xl bg-navy py-2 text-sm font-semibold text-white"
                >
                  Gå med
                </button>
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

      {showCreate && (
        <CreateChallenge
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            refresh();
          }}
          onError={setError}
        />
      )}
    </main>
  );
}

function CreateChallenge({
  onClose,
  onCreated,
  onError,
}: {
  onClose: () => void;
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const today = new Date().toLocaleDateString("sv-SE");
  const monthAhead = new Date(Date.now() + 30 * 86400_000).toLocaleDateString(
    "sv-SE"
  );
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"standard" | "habit">("standard");
  const [metric, setMetric] = useState("steps_total");
  const [perWeek, setPerWeek] = useState("3");
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
          is_open: isOpen,
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
        <h3 className="mb-3 text-lg font-bold">Ny utmaning</h3>
        <div className="space-y-3">
          <div className="flex gap-1.5">
            {(
              [
                ["standard", "🏆 Tävling"],
                ["habit", "✅ Vana"],
              ] as const
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

          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={
              kind === "habit" ? "Namn, t.ex. Träningsvanan" : "Namn, t.ex. Sommarslaget"
            }
            className={inputCls}
          />

          {kind === "standard" ? (
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

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isOpen}
              onChange={(e) => setIsOpen(e.target.checked)}
              className="h-4 w-4 accent-[#23588a]"
            />
            Öppen för alla på Shapiqo (ingen inbjudan behövs)
          </label>

          <button
            disabled={saving || !name.trim()}
            onClick={save}
            className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
          >
            Skapa utmaning
          </button>
        </div>
      </div>
    </div>
  );
}
