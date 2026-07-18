"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { quickPosition } from "../lib/geo";
import type { SessionDetail } from "../lib/types";

type Plan = {
  name: string;
  exercises: {
    exercise_id: string;
    name: string;
    sets: number;
    reps: string;
    rest_seconds: number;
  }[];
};

const EQUIPMENT = [
  "skivstång",
  "hantlar",
  "maskin",
  "kabel",
  "kroppsvikt",
  "kettlebell",
];

export default function GenerateWorkout({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [minutes, setMinutes] = useState(45);
  const [equipment, setEquipment] = useState<string[]>([...EQUIPMENT]);
  const [focus, setFocus] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggle(eq: string) {
    setEquipment((prev) =>
      prev.includes(eq) ? prev.filter((e) => e !== eq) : [...prev, eq]
    );
  }

  async function generate() {
    setBusy("Genererar pass…");
    setError(null);
    try {
      const result = await api<Plan>("/api/ai/generate-workout", {
        method: "POST",
        body: JSON.stringify({
          minutes,
          equipment,
          focus: focus.trim() || null,
        }),
      });
      setPlan(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function startPlan() {
    if (!plan) return;
    setBusy("Startar passet…");
    try {
      const { program_day_id } = await api<{ program_day_id: string }>(
        "/api/ai/generate-workout/accept",
        { method: "POST", body: JSON.stringify({ plan }) }
      );
      const pos = await quickPosition();
      const session = await api<SessionDetail>("/api/sessions/start", {
        method: "POST",
        body: JSON.stringify({ program_day_id, ...pos }),
      });
      router.push(`/workout/${session.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
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
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">✨ Generera pass</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>

        {error && (
          <p className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        {!plan ? (
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-sm font-medium text-muted dark:text-faint">
                Hur mycket tid har du?
              </p>
              <div className="flex gap-1.5">
                {[20, 30, 45, 60, 90].map((m) => (
                  <button
                    key={m}
                    onClick={() => setMinutes(m)}
                    className={`flex-1 rounded-lg py-2 text-sm font-semibold ${
                      minutes === m
                        ? "bg-navy text-white"
                        : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-sm font-medium text-muted dark:text-faint">
                Tillgänglig utrustning
              </p>
              <div className="flex flex-wrap gap-1.5">
                {EQUIPMENT.map((eq) => (
                  <button
                    key={eq}
                    onClick={() => toggle(eq)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize ${
                      equipment.includes(eq)
                        ? "bg-navy text-white"
                        : "bg-shell text-muted dark:bg-night-shell"
                    }`}
                  >
                    {eq}
                  </button>
                ))}
              </div>
            </div>

            <input
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="Fokus (valfritt), t.ex. ben & säte"
              className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong"
            />

            <button
              disabled={!!busy || equipment.length === 0}
              onClick={generate}
              className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-50"
            >
              {busy ?? "Generera"}
            </button>
          </div>
        ) : (
          <div>
            <h4 className="font-bold">{plan.name}</h4>
            <ul className="mt-2 space-y-1.5">
              {plan.exercises.map((e) => (
                <li
                  key={e.exercise_id}
                  className="flex items-center justify-between rounded-lg bg-cream-deep px-3 py-2 text-sm dark:bg-night-shell/60"
                >
                  <span className="font-medium">{e.name}</span>
                  <span className="text-muted dark:text-faint">
                    {e.sets} × {e.reps} · vila {e.rest_seconds} s
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex gap-2">
              <button
                onClick={() => setPlan(null)}
                className="flex-1 rounded-xl border border-line-strong py-3 font-semibold text-muted dark:border-night-strong dark:text-night-muted"
              >
                Gör om
              </button>
              <button
                disabled={!!busy}
                onClick={startPlan}
                className="flex-1 rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-50"
              >
                {busy ?? "Kör passet ▶"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
