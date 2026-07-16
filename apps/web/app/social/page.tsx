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
  starts_on: string;
  ends_on: string;
  participant_count: number;
  is_participant: boolean;
  is_creator: boolean;
  invited: boolean;
  active: boolean;
  leaderboard?: LeaderboardRow[];
};

type LeaderboardRow = {
  user_id: string;
  name: string;
  value: number;
  rank: number;
};

const METRIC_OPTIONS = [
  ["workout_count", "Flest pass"],
  ["distance_km", "Längst distans"],
  ["weight_loss_kg", "Störst viktnedgång (kg)"],
  ["fat_loss_percent", "Störst fettnedgång (%-enheter)"],
] as const;

function metricUnit(metric: string): string {
  switch (metric) {
    case "workout_count":
      return "pass";
    case "distance_km":
      return "km";
    case "weight_loss_kg":
      return "kg";
    case "fat_loss_percent":
      return "%-enheter";
    default:
      return "";
  }
}

export default function SocialPage() {
  const [friends, setFriends] = useState<FriendsData | null>(null);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [email, setEmail] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Challenge | null>(null);
  const [showCreate, setShowCreate] = useState(false);
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

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Socialt</h1>
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <section className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        <h2 className="font-bold">Vänner</h2>
        <div className="mt-2 flex gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="väns e-postadress"
            className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-transparent px-3 py-2 text-sm dark:border-stone-700"
          />
          <button
            disabled={!email.includes("@")}
            onClick={addFriend}
            className="rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-white disabled:opacity-40"
          >
            Lägg till
          </button>
        </div>

        {friends?.incoming.map((f) => (
          <div
            key={f.friendship_id}
            className="mt-2 flex items-center justify-between rounded-xl bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950"
          >
            <span>
              <strong>{f.name}</strong> vill bli din vän
            </span>
            <button
              onClick={() => accept(f.friendship_id)}
              className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white"
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
              <span className="text-xs text-stone-400">{f.email}</span>
            </li>
          ))}
          {friends && friends.friends.length === 0 && (
            <p className="mt-2 text-sm text-stone-400">
              Inga vänner ännu — bjud in med e-postadressen de loggar in med.
            </p>
          )}
          {friends?.outgoing.map((f) => (
            <li key={f.friendship_id} className="py-1 text-sm text-stone-400">
              ⏳ {f.name} (väntar på svar)
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-400">
            Utmaningar
          </h2>
          <button
            onClick={() => setShowCreate(true)}
            className="text-sm text-emerald-600 dark:text-emerald-400"
          >
            + Ny utmaning
          </button>
        </div>

        {challenges.length === 0 && (
          <p className="rounded-xl border border-dashed border-stone-300 p-4 text-center text-sm text-stone-400 dark:border-stone-700">
            Skapa en utmaning och bjud in vännerna — flest pass, mest
            viktnedgång eller störst fettnedgång. 🏆
          </p>
        )}

        <ul className="space-y-2">
          {challenges.map((c) => (
            <li
              key={c.id}
              className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900"
            >
              <button
                className="w-full text-left"
                onClick={() => setExpanded(expanded === c.id ? null : c.id)}
              >
                <div className="flex items-center justify-between">
                  <p className="font-bold">
                    {c.active ? "🔥 " : ""}
                    {c.name}
                  </p>
                  <span className="text-xs text-stone-400">
                    {c.participant_count} deltagare
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-stone-500 dark:text-stone-400">
                  {c.metric_label} · {c.starts_on} → {c.ends_on}
                </p>
              </button>

              {c.invited && !c.is_participant && (
                <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  🎟 Du är inbjuden till den här utmaningen!
                </p>
              )}

              {!c.is_participant && (
                <button
                  onClick={() => join(c.id)}
                  className="mt-2 w-full rounded-xl bg-emerald-600 py-2 text-sm font-semibold text-white"
                >
                  Gå med
                </button>
              )}

              {c.is_participant && (
                <button
                  onClick={() => invite(c.id)}
                  className="mt-2 w-full rounded-xl border border-emerald-300 py-2 text-sm font-semibold text-emerald-700 dark:border-emerald-800 dark:text-emerald-400"
                >
                  ➕ Bjud in till utmaningen
                </button>
              )}

              {expanded === c.id && detail?.leaderboard && (
                <ol className="mt-3 space-y-1 border-t border-stone-100 pt-3 dark:border-stone-800">
                  {detail.leaderboard.map((row) => (
                    <li
                      key={row.user_id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>
                        <span className="mr-2 inline-block w-6 font-bold">
                          {row.rank === 1
                            ? "🥇"
                            : row.rank === 2
                              ? "🥈"
                              : row.rank === 3
                                ? "🥉"
                                : `${row.rank}.`}
                        </span>
                        {row.name}
                      </span>
                      <span className="font-semibold">
                        {row.value} {metricUnit(c.metric)}
                      </span>
                    </li>
                  ))}
                </ol>
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
  const [metric, setMetric] = useState("workout_count");
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(monthAhead);
  const [saving, setSaving] = useState(false);

  const inputCls =
    "w-full rounded-xl border border-stone-300 bg-transparent px-4 py-2.5 dark:border-stone-700";

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
        className="w-full max-w-md rounded-t-3xl bg-white p-5 dark:bg-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-lg font-bold">Ny utmaning</h3>
        <div className="space-y-3">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Namn, t.ex. Sommarslaget"
            className={inputCls}
          />
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
          <div className="flex gap-2">
            <label className="flex-1">
              <span className="text-xs text-stone-400">Start</span>
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="flex-1">
              <span className="text-xs text-stone-400">Slut</span>
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className={inputCls}
              />
            </label>
          </div>
          <button
            disabled={saving || !name.trim()}
            onClick={save}
            className="w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white disabled:opacity-40"
          >
            Skapa utmaning
          </button>
        </div>
      </div>
    </div>
  );
}
