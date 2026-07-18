"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import GenerateWorkout from "../components/GenerateWorkout";
import { api } from "../lib/api";
import {
  LEVEL_LABELS,
  type CardioActivity,
  type Program,
  type SessionDetail,
  type UserProgram,
} from "../lib/types";

type Category = "gym" | "cardio" | "single" | "other";

const CATEGORIES: [Category, string][] = [
  ["gym", "🏋️ Gym"],
  ["cardio", "🏃 Kondition"],
  ["single", "⚡ Pass"],
  ["other", "🎾 Övrigt"],
];

export default function TrainingPage() {
  const [category, setCategory] = useState<Category>("gym");
  const [error, setError] = useState<string | null>(null);

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Träning</h1>
        <div className="flex gap-3">
          <a href="/map" className="text-sm text-navy dark:text-lime">
            🗺️ Karta
          </a>
          <a href="/exercises" className="text-sm text-navy dark:text-lime">
            Övningsbibliotek ›
          </a>
        </div>
      </div>

      <div className="flex gap-1.5">
        {CATEGORIES.map(([key, label]) => (
          <button
            key={key}
            onClick={() => {
              setCategory(key);
              setError(null);
            }}
            className={`flex-1 rounded-full py-2 text-xs font-semibold ${
              category === key
                ? "bg-navy text-white"
                : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      {category === "gym" && <GymSection onError={setError} />}
      {category === "cardio" && <CardioSection kind="cardio" onError={setError} />}
      {category === "single" && <SingleSection onError={setError} />}
      {category === "other" && <CardioSection kind="other" onError={setError} />}
    </main>
  );
}

// ── Gym: flerdagars program ───────────────────────────────────

function GymSection({ onError }: { onError: (msg: string) => void }) {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [active, setActive] = useState<UserProgram | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showGenerator, setShowGenerator] = useState(false);

  useEffect(() => {
    Promise.all([
      api<Program[]>("/api/programs"),
      api<UserProgram | null>("/api/user-programs/active"),
    ])
      .then(([programs, active]) => {
        setPrograms(programs.filter((p) => p.kind === "program"));
        setActive(active);
      })
      .catch((e: Error) => onError(e.message));
  }, [onError]);

  async function activate(programId: string) {
    try {
      setActive(
        await api<UserProgram>(`/api/programs/${programId}/activate`, {
          method: "POST",
        })
      );
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return (
    <>
      <button
        onClick={() => setShowGenerator(true)}
        className="rounded-2xl border-2 border-dashed border-navy-line bg-navy-soft p-4 text-left dark:border-night-strong dark:bg-night-shell"
      >
        <p className="font-bold">✨ Generera ett pass</p>
        <p className="text-sm text-muted dark:text-faint">
          Ont om tid eller begränsad utrustning? Låt AI:n sätta ihop dagens
          pass.
        </p>
      </button>

      {showGenerator && (
        <GenerateWorkout onClose={() => setShowGenerator(false)} />
      )}

      {programs.map((p) => {
        const isActive = active?.program.id === p.id;
        const isOpen = expanded === p.id;
        return (
          <section
            key={p.id}
            className={`rounded-2xl border bg-white p-5 shadow-card dark:bg-night-card ${
              isActive
                ? "border-navy dark:border-lime"
                : "border-line dark:border-night-shell"
            }`}
          >
            <button
              className="w-full text-left"
              onClick={() => setExpanded(isOpen ? null : p.id)}
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-lg font-bold">{p.name}</h2>
                <span className="shrink-0 rounded-full bg-shell px-2 py-0.5 text-xs font-medium text-muted dark:bg-night-shell dark:text-night-muted">
                  {LEVEL_LABELS[p.level]}
                </span>
              </div>
              {p.description && (
                <p className="mt-1 text-sm text-muted dark:text-faint">
                  {p.description}
                </p>
              )}
              <p className="mt-1 text-xs text-faint">
                {p.days.length} pass i rotationen
                {p.days_per_week ? ` · ${p.days_per_week} dagar/vecka` : ""}
                {isActive ? " · ✅ Aktivt" : ""}
              </p>
            </button>

            {isOpen && (
              <div className="mt-3 space-y-3 border-t border-line pt-3 dark:border-night-shell">
                {p.days.map((day) => (
                  <div key={day.id}>
                    <p className="text-sm font-semibold">{day.name}</p>
                    <ul className="mt-1 space-y-0.5 text-sm text-muted dark:text-night-muted">
                      {day.exercises.map((ex) => (
                        <li key={ex.id}>
                          {ex.exercise.name} · {ex.target_sets} ×{" "}
                          {ex.target_reps} · vila {ex.rest_seconds} s
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                {!isActive && (
                  <button
                    onClick={() => activate(p.id)}
                    className="w-full rounded-xl bg-navy py-2.5 font-semibold text-white active:bg-navy-deep"
                  >
                    Aktivera programmet
                  </button>
                )}
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}

// ── Pass: fristående pass som startas direkt ──────────────────

function SingleSection({ onError }: { onError: (msg: string) => void }) {
  const router = useRouter();
  const [workouts, setWorkouts] = useState<Program[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);

  useEffect(() => {
    api<Program[]>("/api/programs")
      .then((programs) =>
        setWorkouts(programs.filter((p) => p.kind === "single"))
      )
      .catch((e: Error) => onError(e.message));
  }, [onError]);

  async function start(p: Program) {
    if (!p.days[0]) return;
    setStarting(p.id);
    try {
      const session = await api<SessionDetail>("/api/sessions/start", {
        method: "POST",
        body: JSON.stringify({ program_day_id: p.days[0].id }),
      });
      router.push(`/workout/${session.id}`);
    } catch (e) {
      onError((e as Error).message);
      setStarting(null);
    }
  }

  return (
    <>
      <p className="text-sm text-muted dark:text-faint">
        Fristående pass — starta direkt utan att aktivera ett program.
        Timern och loggningen funkar precis som vanligt.
      </p>
      {workouts.map((p) => {
        const isOpen = expanded === p.id;
        const exercises = p.days[0]?.exercises ?? [];
        return (
          <section
            key={p.id}
            className="rounded-2xl border border-line bg-white p-5 shadow-card dark:border-night-shell dark:bg-night-card"
          >
            <button
              className="w-full text-left"
              onClick={() => setExpanded(isOpen ? null : p.id)}
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-lg font-bold">{p.name}</h2>
                <span className="shrink-0 rounded-full bg-shell px-2 py-0.5 text-xs font-medium text-muted dark:bg-night-shell dark:text-night-muted">
                  {LEVEL_LABELS[p.level]}
                </span>
              </div>
              {p.description && (
                <p className="mt-1 text-sm text-muted dark:text-faint">
                  {p.description}
                </p>
              )}
              <p className="mt-1 text-xs text-faint">
                {exercises.length} övningar
              </p>
            </button>

            {isOpen && (
              <div className="mt-3 border-t border-line pt-3 dark:border-night-shell">
                <ul className="space-y-0.5 text-sm text-muted dark:text-night-muted">
                  {exercises.map((ex) => (
                    <li key={ex.id}>
                      {ex.exercise.name} · {ex.target_sets} × {ex.target_reps} ·
                      vila {ex.rest_seconds} s
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              disabled={starting === p.id}
              onClick={() => start(p)}
              className="mt-3 w-full rounded-xl bg-navy py-2.5 font-semibold text-white active:bg-navy-deep disabled:opacity-50"
            >
              {starting === p.id ? "Startar…" : "▶ Starta passet"}
            </button>
          </section>
        );
      })}
    </>
  );
}

// ── Kondition & Övrigt: logga aktiviteter ─────────────────────

type Suggestion = {
  label: string;
  type: CardioActivity["type"];
  name: string;
  km?: number;
  min: number;
};

const CARDIO_SUGGESTIONS: Suggestion[] = [
  { label: "🏃 Löpning 3 km", type: "run", name: "Löpning", km: 3, min: 20 },
  { label: "🏃 Löpning 5 km", type: "run", name: "Löpning", km: 5, min: 32 },
  { label: "🏃 Löpning 10 km", type: "run", name: "Löpning", km: 10, min: 65 },
  {
    label: "⚡ Intervaller 4×4",
    type: "run",
    name: "Intervaller 4×4 min",
    min: 30,
  },
  { label: "🚶 Promenad 45 min", type: "walk", name: "Promenad", km: 4, min: 45 },
  { label: "🚴 Cykling 45 min", type: "ride", name: "Cykling", km: 15, min: 45 },
  { label: "🏊 Simning 30 min", type: "swim", name: "Simning", km: 1, min: 30 },
];

const OTHER_SUGGESTIONS: Suggestion[] = [
  { label: "🎾 Padel 60 min", type: "other", name: "Padel", min: 60 },
  { label: "🧘 Yoga 30 min", type: "other", name: "Yoga", min: 30 },
  { label: "🤸 Gruppträning", type: "other", name: "Gruppträning", min: 45 },
  { label: "🥾 Vandring", type: "other", name: "Vandring", min: 90 },
  { label: "⛷️ Skidåkning", type: "other", name: "Skidåkning", min: 120 },
  { label: "🧗 Klättring", type: "other", name: "Klättring", min: 60 },
  { label: "⛳ Golfrunda", type: "other", name: "Golf", min: 180 },
  { label: "🏒 Innebandy", type: "other", name: "Innebandy", min: 60 },
];

const TYPE_LABELS: Record<CardioActivity["type"], string> = {
  run: "Löpning",
  ride: "Cykling",
  walk: "Promenad",
  swim: "Simning",
  other: "Övrigt",
};

const TYPE_ICONS: Record<CardioActivity["type"], string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  other: "🎾",
};

function nowLocalInput(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function CardioSection({
  kind,
  onError,
}: {
  kind: "cardio" | "other";
  onError: (msg: string) => void;
}) {
  const suggestions = kind === "cardio" ? CARDIO_SUGGESTIONS : OTHER_SUGGESTIONS;
  const [activities, setActivities] = useState<CardioActivity[]>([]);
  const [form, setForm] = useState({
    type: (kind === "cardio" ? "run" : "other") as CardioActivity["type"],
    name: "",
    km: "",
    min: "",
    at: nowLocalInput(),
  });
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  const isMine = (a: CardioActivity) =>
    kind === "other" ? a.type === "other" : a.type !== "other";

  useEffect(() => {
    api<CardioActivity[]>("/api/cardio?limit=60")
      .then((rows) => setActivities(rows))
      .catch((e: Error) => onError(e.message));
  }, [onError]);

  function applySuggestion(s: Suggestion) {
    setForm({
      type: s.type,
      name: s.name,
      km: s.km != null ? String(s.km) : "",
      min: String(s.min),
      at: nowLocalInput(),
    });
  }

  async function save() {
    const minutes = Number(form.min);
    if (!minutes || minutes <= 0) {
      onError("Ange hur många minuter aktiviteten tog.");
      return;
    }
    setSaving(true);
    try {
      const created = await api<CardioActivity>("/api/cardio", {
        method: "POST",
        body: JSON.stringify({
          type: form.type,
          name: form.name.trim() || TYPE_LABELS[form.type],
          started_at: new Date(form.at).toISOString(),
          duration_s: Math.round(minutes * 60),
          distance_m: form.km ? Number(form.km) * 1000 : null,
        }),
      });
      setActivities((prev) => [created, ...prev]);
      setForm((f) => ({ ...f, name: "", km: "", min: "", at: nowLocalInput() }));
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/api/cardio/${id}`, { method: "DELETE" });
      setActivities((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      onError((e as Error).message);
    }
  }

  const mine = activities.filter(isMine);

  return (
    <>
      <section className="rounded-2xl border border-line bg-white p-5 shadow-card dark:border-night-shell dark:bg-night-card">
        <h2 className="font-bold">
          {kind === "cardio" ? "Logga konditionspass" : "Logga aktivitet"}
        </h2>
        <p className="mt-0.5 text-xs text-faint">
          Välj ett förslag eller fyll i själv — sprang du t.ex. 4 km i morse
          loggar du det här.
        </p>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s.label}
              onClick={() => applySuggestion(s)}
              className="rounded-full bg-navy-soft px-3 py-1.5 text-xs font-semibold text-navy-deep dark:bg-night-shell dark:text-lime"
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-3">
          {kind === "cardio" && (
            <div className="flex gap-1.5">
              {(["run", "ride", "walk", "swim"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setForm({ ...form, type: t })}
                  className={`flex-1 rounded-lg py-2 text-xs font-semibold ${
                    form.type === t
                      ? "bg-navy text-white"
                      : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
                  }`}
                >
                  {TYPE_ICONS[t]} {TYPE_LABELS[t]}
                </button>
              ))}
            </div>
          )}

          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder={
              kind === "cardio"
                ? "Namn (t.ex. Morgonrunda)"
                : "Aktivitet (t.ex. Padel med Alex)"
            }
            className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 text-sm dark:border-night-strong"
          />

          <div className="grid grid-cols-3 gap-2">
            <label className="block">
              <span className="text-[10px] text-faint">Distans km</span>
              <input
                inputMode="decimal"
                value={form.km}
                onChange={(e) => setForm({ ...form, km: e.target.value })}
                placeholder="—"
                className="mt-0.5 w-full rounded-lg border border-line-strong bg-transparent px-2 py-2 text-center text-sm dark:border-night-strong"
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-faint">Tid min</span>
              <input
                inputMode="numeric"
                value={form.min}
                onChange={(e) => setForm({ ...form, min: e.target.value })}
                placeholder="30"
                className="mt-0.5 w-full rounded-lg border border-line-strong bg-transparent px-2 py-2 text-center text-sm dark:border-night-strong"
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-faint">När</span>
              <input
                type="datetime-local"
                value={form.at}
                onChange={(e) => setForm({ ...form, at: e.target.value })}
                className="mt-0.5 w-full rounded-lg border border-line-strong bg-transparent px-1 py-2 text-center text-xs dark:border-night-strong"
              />
            </label>
          </div>

          <button
            disabled={saving}
            onClick={save}
            className="w-full rounded-xl bg-navy py-3 font-semibold text-white active:bg-navy-deep disabled:opacity-50"
          >
            {saving ? "Sparar…" : savedFlash ? "✅ Loggat!" : "Logga aktiviteten"}
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-2 font-bold">Senaste</h2>
        {mine.length === 0 && (
          <p className="py-4 text-center text-sm text-faint">
            Inget loggat ännu.
          </p>
        )}
        <ul className="space-y-2">
          {mine.slice(0, 15).map((a) => {
            const km = a.distance_m ? a.distance_m / 1000 : null;
            const pace =
              a.avg_pace_s_per_km != null
                ? `${Math.floor(a.avg_pace_s_per_km / 60)}:${String(
                    Math.round(a.avg_pace_s_per_km % 60)
                  ).padStart(2, "0")} /km`
                : null;
            return (
              <li
                key={a.id}
                className="flex items-center gap-3 rounded-2xl border border-line bg-white px-4 py-3 shadow-card dark:border-night-shell dark:bg-night-card"
              >
                <span className="text-xl">{TYPE_ICONS[a.type]}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">
                    {a.name ?? TYPE_LABELS[a.type]}
                  </p>
                  <p className="text-xs text-faint">
                    {new Date(a.started_at).toLocaleDateString("sv-SE", {
                      day: "numeric",
                      month: "short",
                    })}
                    {" · "}
                    {Math.round(a.duration_s / 60)} min
                    {km ? ` · ${km.toLocaleString("sv-SE")} km` : ""}
                    {pace ? ` · ${pace}` : ""}
                    {a.source !== "manual" ? ` · ${a.source}` : ""}
                  </p>
                </div>
                {a.source === "manual" && (
                  <button
                    onClick={() => remove(a.id)}
                    className="px-1 text-faint hover:text-red-500"
                    aria-label="Ta bort"
                  >
                    ✕
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}
