"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, formatDate, formatWeight } from "../../lib/api";
import RestTimer from "../../components/RestTimer";
import type {
  Exercise,
  SessionDetail,
  SessionExercisePlan,
  WorkoutSet,
} from "../../lib/types";

export default function WorkoutPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restSeconds, setRestSeconds] = useState<number | null>(null);
  const [restKey, setRestKey] = useState(0);
  const [showPicker, setShowPicker] = useState(false);
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    api<SessionDetail>(`/api/sessions/${id}`)
      .then(setDetail)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  const readOnly = detail?.finished_at != null;

  function onSetLogged(set: WorkoutSet, rest: number | null) {
    setDetail((d) => (d ? { ...d, sets: [...d.sets, set] } : d));
    if (rest && rest > 0) {
      setRestSeconds(rest);
      setRestKey((k) => k + 1);
    }
  }

  async function deleteSet(setId: string) {
    await api(`/api/sessions/${id}/sets/${setId}`, { method: "DELETE" });
    setDetail((d) =>
      d ? { ...d, sets: d.sets.filter((s) => s.id !== setId) } : d
    );
  }

  async function finish() {
    setFinishing(true);
    try {
      await api(`/api/sessions/${id}/finish`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      router.push("/history");
    } catch (e) {
      setError((e as Error).message);
      setFinishing(false);
    }
  }

  function addExercise(exercise: Exercise) {
    setDetail((d) =>
      d
        ? {
            ...d,
            plan: [
              ...d.plan,
              {
                exercise,
                target_sets: null,
                target_reps: null,
                rest_seconds: 90,
                notes: null,
                previous: null,
              },
            ],
          }
        : d
    );
    setShowPicker(false);
  }

  if (error) {
    return (
      <main className="mx-auto max-w-md p-5">
        <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-center text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      </main>
    );
  }
  if (!detail) {
    return (
      <main className="mx-auto max-w-md p-5 text-center text-slate-400">
        Laddar…
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5 pb-32">
      <header className="pt-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {detail.program_name ?? "Eget pass"} · {formatDate(detail.started_at)}
          {readOnly && " · Avslutat"}
        </p>
        <h1 className="text-2xl font-bold">{detail.day_name ?? "Fritt pass"}</h1>
      </header>

      {detail.plan.map((plan) => (
        <ExerciseCard
          key={plan.exercise.id}
          sessionId={detail.id}
          plan={plan}
          sets={detail.sets.filter((s) => s.exercise_id === plan.exercise.id)}
          readOnly={readOnly}
          onSetLogged={onSetLogged}
          onDeleteSet={deleteSet}
          onError={setError}
        />
      ))}

      {!readOnly && (
        <>
          <button
            onClick={() => setShowPicker(true)}
            className="rounded-xl border border-dashed border-slate-300 py-3 font-medium text-slate-500 dark:border-slate-700 dark:text-slate-400"
          >
            + Lägg till övning
          </button>
          <button
            disabled={finishing}
            onClick={finish}
            className="rounded-xl bg-emerald-600 py-3.5 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
          >
            {finishing ? "Avslutar…" : "Avsluta passet ✓"}
          </button>
        </>
      )}

      {showPicker && (
        <ExercisePicker
          exclude={detail.plan.map((p) => p.exercise.id)}
          onPick={addExercise}
          onClose={() => setShowPicker(false)}
        />
      )}

      {restSeconds !== null && (
        <RestTimer
          key={restKey}
          seconds={restSeconds}
          onDone={() => setRestSeconds(null)}
        />
      )}
    </main>
  );
}

function ExerciseCard({
  sessionId,
  plan,
  sets,
  readOnly,
  onSetLogged,
  onDeleteSet,
  onError,
}: {
  sessionId: string;
  plan: SessionExercisePlan;
  sets: WorkoutSet[];
  readOnly: boolean;
  onSetLogged: (set: WorkoutSet, rest: number | null) => void;
  onDeleteSet: (setId: string) => void;
  onError: (msg: string) => void;
}) {
  const lastSet = sets[sets.length - 1];
  const prevSetForNext = plan.previous?.sets[sets.length] ?? null;

  const [weight, setWeight] = useState<string>("");
  const [reps, setReps] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // Förifyll med senast loggade set, annars föregående passets motsvarande set
  const placeholderWeight =
    lastSet?.weight_kg ?? prevSetForNext?.weight_kg ?? null;
  const placeholderReps = lastSet?.reps ?? prevSetForNext?.reps ?? null;

  const targetLabel = useMemo(() => {
    const parts: string[] = [];
    if (plan.target_sets && plan.target_reps)
      parts.push(`${plan.target_sets} × ${plan.target_reps}`);
    if (plan.rest_seconds) parts.push(`vila ${plan.rest_seconds} s`);
    return parts.join(" · ");
  }, [plan]);

  async function logSet() {
    const w = weight !== "" ? Number(weight.replace(",", ".")) : placeholderWeight;
    const r = reps !== "" ? Number(reps) : placeholderReps;
    if (r === null || Number.isNaN(r)) return;
    setSaving(true);
    try {
      const created = await api<WorkoutSet>(
        `/api/sessions/${sessionId}/sets`,
        {
          method: "POST",
          body: JSON.stringify({
            exercise_id: plan.exercise.id,
            weight_kg: w !== null && !Number.isNaN(w) ? w : null,
            reps: r,
          }),
        }
      );
      onSetLogged(created, plan.rest_seconds);
      setWeight("");
      setReps("");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-bold">{plan.exercise.name}</h2>
        {targetLabel && (
          <span className="shrink-0 text-xs text-slate-400">{targetLabel}</span>
        )}
      </div>

      {plan.previous && (
        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Förra passet · {formatDate(plan.previous.performed_at)}
          </p>
          <p className="mt-0.5 flex flex-wrap gap-x-3 text-sm text-slate-600 dark:text-slate-300">
            {plan.previous.sets.map((s) => (
              <span key={s.id}>
                {formatWeight(s.weight_kg)} × {s.reps}
              </span>
            ))}
          </p>
        </div>
      )}

      {sets.length > 0 && (
        <ul className="mt-3 space-y-1">
          {sets.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between text-sm"
            >
              <span>
                <span className="mr-2 inline-block w-6 text-slate-400">
                  #{s.set_number}
                </span>
                <span className="font-medium">
                  {formatWeight(s.weight_kg)} × {s.reps}
                </span>
              </span>
              {!readOnly && (
                <button
                  onClick={() => onDeleteSet(s.id)}
                  className="px-2 text-slate-400 hover:text-red-500"
                  aria-label="Ta bort set"
                >
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {!readOnly && (
        <div className="mt-3 flex gap-2">
          <input
            inputMode="decimal"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder={
              placeholderWeight !== null ? String(placeholderWeight) : "kg"
            }
            className="w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-3 py-2.5 text-center dark:border-slate-700"
          />
          <input
            inputMode="numeric"
            value={reps}
            onChange={(e) => setReps(e.target.value)}
            placeholder={
              placeholderReps !== null ? String(placeholderReps) : "reps"
            }
            className="w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-3 py-2.5 text-center dark:border-slate-700"
          />
          <button
            disabled={saving || (reps === "" && placeholderReps === null)}
            onClick={logSet}
            className="rounded-lg bg-sky-600 px-4 font-semibold text-white active:bg-sky-700 disabled:opacity-40"
          >
            Logga
          </button>
        </div>
      )}
    </section>
  );
}

function ExercisePicker({
  exclude,
  onPick,
  onClose,
}: {
  exclude: string[];
  onPick: (exercise: Exercise) => void;
  onClose: () => void;
}) {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api<Exercise[]>("/api/exercises").then(setExercises).catch(() => {});
  }, []);

  const filtered = exercises.filter(
    (e) =>
      !exclude.includes(e.id) &&
      (!search || e.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[70dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">Välj övning</h3>
          <button onClick={onClose} className="p-1 text-slate-400">
            ✕
          </button>
        </div>
        <input
          autoFocus
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Sök…"
          className="mb-3 w-full rounded-xl border border-slate-300 bg-transparent px-4 py-2.5 dark:border-slate-700"
        />
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {filtered.map((e) => (
            <li key={e.id}>
              <button
                onClick={() => onPick(e)}
                className="w-full py-3 text-left"
              >
                <p className="font-medium">{e.name}</p>
                <p className="text-xs capitalize text-slate-400">
                  {e.muscle_groups.join(" · ")}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
