"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Me } from "../lib/types";

const QUESTIONS: { key: "fav_workout" | "fav_exercise" | "goal"; label: string; placeholder: string }[] = [
  {
    key: "fav_workout",
    label: "Vad tränar du helst?",
    placeholder: "t.ex. Gym & löpning",
  },
  {
    key: "fav_exercise",
    label: "Favoritövning?",
    placeholder: "t.ex. Marklyft",
  },
  {
    key: "goal",
    label: "Vad är målet just nu?",
    placeholder: "t.ex. Mila under 50 min",
  },
];

export default function ProfilePage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [form, setForm] = useState({
    display_name: "",
    city: "",
    fav_workout: "",
    fav_exercise: "",
    goal: "",
  });
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/api/me")
      .then((me) => {
        setMe(me);
        setForm({
          display_name: me.display_name ?? "",
          city: me.profile.city ?? "",
          fav_workout: me.profile.fav_workout ?? "",
          fav_exercise: me.profile.fav_exercise ?? "",
          goal: me.profile.goal ?? "",
        });
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const updated = await api<Me>("/api/me", {
        method: "PATCH",
        body: JSON.stringify({
          display_name: form.display_name.trim() || null,
          profile: {
            city: form.city.trim(),
            fav_workout: form.fav_workout.trim(),
            fav_exercise: form.fav_exercise.trim(),
            goal: form.goal.trim(),
          },
        }),
      });
      setMe(updated);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function uploadPhoto(file: File) {
    setUploading(true);
    setError(null);
    try {
      const { downscaleImage } = await import("../lib/image");
      const small = await downscaleImage(file, 512, 0.9);
      const form = new FormData();
      form.append("file", small, "avatar.jpg");
      const res = await fetch("/api/me/avatar", { method: "POST", body: form });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Fel ${res.status}`);
      setMe(body);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function removePhoto() {
    await api("/api/me/avatar", { method: "DELETE" }).catch(() => {});
    setMe((m) => (m ? { ...m, avatar_url: null } : m));
  }

  const inputCls =
    "mt-1 w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong";

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-2xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Min profil</h1>
        <a href="/settings" className="text-sm text-navy dark:text-lime">
          Kopplingar ⚙️
        </a>
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {/* Foto */}
      <section className="flex items-center gap-4 rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
        {me?.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={me.avatar_url}
            alt="Profilfoto"
            className="h-20 w-20 rounded-full border border-line object-cover dark:border-night-shell"
          />
        ) : (
          <span className="flex h-20 w-20 items-center justify-center rounded-full bg-navy-soft text-2xl font-bold text-navy dark:bg-night-shell dark:text-lime">
            {(me?.display_name ?? me?.email ?? "?")
              .split(/[\s.@_-]+/)
              .filter(Boolean)
              .slice(0, 2)
              .map((p) => p[0]!.toUpperCase())
              .join("")}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{me?.email ?? "…"}</p>
          <div className="mt-2 flex gap-2">
            <button
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              className="rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              {uploading ? "Laddar upp…" : me?.avatar_url ? "Byt foto" : "Ladda upp foto"}
            </button>
            {me?.avatar_url && (
              <button
                onClick={removePhoto}
                className="rounded-lg bg-shell px-3 py-1.5 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
              >
                Ta bort
              </button>
            )}
          </div>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadPhoto(f);
            e.target.value = "";
          }}
        />
      </section>

      {/* Uppgifter */}
      <section className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
        <label className="block">
          <span className="text-sm font-medium text-muted dark:text-faint">
            Visningsnamn
          </span>
          <input
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            placeholder="t.ex. Daniel"
            className={inputCls}
          />
        </label>
        <label className="mt-3 block">
          <span className="text-sm font-medium text-muted dark:text-faint">
            Bor i
          </span>
          <input
            value={form.city}
            onChange={(e) => setForm({ ...form, city: e.target.value })}
            placeholder="t.ex. Stockholm"
            className={inputCls}
          />
        </label>

        <h2 className="mt-5 text-xs font-bold uppercase tracking-wide text-faint">
          Tre snabba om träningen
        </h2>
        {QUESTIONS.map((q) => (
          <label key={q.key} className="mt-3 block">
            <span className="text-sm font-medium text-muted dark:text-faint">
              {q.label}
            </span>
            <input
              value={form[q.key]}
              onChange={(e) => setForm({ ...form, [q.key]: e.target.value })}
              placeholder={q.placeholder}
              className={inputCls}
            />
          </label>
        ))}

        <button
          disabled={saving}
          onClick={save}
          className="mt-5 w-full rounded-xl bg-navy py-3 font-semibold text-white active:bg-navy-deep disabled:opacity-50"
        >
          {saving ? "Sparar…" : savedFlash ? "✅ Sparat!" : "Spara profilen"}
        </button>
      </section>

      <BadgeWall />
      <TrophyCabinet />
    </main>
  );
}

type BadgeInfo = {
  key: string;
  emoji: string;
  title: string;
  description: string;
  earned: boolean;
  earned_at: string | null;
};

function BadgeWall() {
  const [badges, setBadges] = useState<BadgeInfo[] | null>(null);

  useEffect(() => {
    api<BadgeInfo[]>("/api/social/badges").then(setBadges).catch(() => {});
  }, []);

  if (!badges || badges.length === 0) return null;
  const earnedCount = badges.filter((b) => b.earned).length;

  return (
    <section className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">🎖 Märken</h2>
        <span className="text-xs text-faint">
          {earnedCount} av {badges.length}
        </span>
      </div>
      <ul className="mt-3 grid grid-cols-3 gap-2">
        {badges.map((b) => (
          <li
            key={b.key}
            title={b.description}
            className={`flex flex-col items-center rounded-xl px-1 py-3 text-center ${
              b.earned
                ? "bg-sand dark:bg-night-shell"
                : "bg-shell opacity-40 grayscale dark:bg-night-shell/50"
            }`}
          >
            <span className="text-2xl">{b.emoji}</span>
            <span className="mt-1 text-[11px] font-semibold leading-tight">
              {b.title}
            </span>
            <span className="mt-0.5 text-[10px] leading-tight text-muted dark:text-faint">
              {b.earned && b.earned_at
                ? b.earned_at.slice(0, 10)
                : b.description}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

type Trophy = {
  challenge_id: string;
  name: string;
  kind: string;
  ended_on: string;
  rank: number;
  value: number;
  participants: number;
  habit_completed?: boolean;
  habit_weeks?: string;
};

function TrophyCabinet() {
  const [trophies, setTrophies] = useState<Trophy[] | null>(null);

  useEffect(() => {
    api<Trophy[]>("/api/social/trophies").then(setTrophies).catch(() => {});
  }, []);

  if (!trophies || trophies.length === 0) return null;

  function icon(t: Trophy): string {
    if (t.kind === "habit") return t.habit_completed ? "🏆" : "🎖";
    return t.rank === 1 ? "🥇" : t.rank === 2 ? "🥈" : t.rank === 3 ? "🥉" : "🎖";
  }

  return (
    <section className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
      <h2 className="font-bold">🏆 Troféskåp</h2>
      <ul className="mt-2 space-y-2">
        {trophies.map((t) => (
          <li key={t.challenge_id} className="flex items-center gap-3">
            <span className="text-2xl">{icon(t)}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">
                {t.name}
              </span>
              <span className="block text-xs text-muted dark:text-faint">
                {t.kind === "habit"
                  ? `${t.habit_weeks} veckor klarade`
                  : `${t.rank}:a av ${t.participants}`}
                {" · "}
                {t.ended_on}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
