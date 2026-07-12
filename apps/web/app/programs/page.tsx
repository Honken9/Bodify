"use client";

import { useEffect, useState } from "react";
import GenerateWorkout from "../components/GenerateWorkout";
import { api } from "../lib/api";
import { LEVEL_LABELS, type Program, type UserProgram } from "../lib/types";

export default function ProgramsPage() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [active, setActive] = useState<UserProgram | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showGenerator, setShowGenerator] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<Program[]>("/api/programs"),
      api<UserProgram | null>("/api/user-programs/active"),
    ])
      .then(([programs, active]) => {
        setPrograms(programs);
        setActive(active);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function activate(programId: string) {
    try {
      setActive(
        await api<UserProgram>(`/api/programs/${programId}/activate`, {
          method: "POST",
        })
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Program</h1>
        <a href="/exercises" className="text-sm text-sky-600 dark:text-sky-400">
          Övningsbibliotek ›
        </a>
      </div>
      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      <button
        onClick={() => setShowGenerator(true)}
        className="rounded-2xl border-2 border-dashed border-sky-300 bg-sky-50 p-4 text-left dark:border-sky-800 dark:bg-sky-950"
      >
        <p className="font-bold">✨ Generera ett pass</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
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
            className={`rounded-2xl border bg-white p-5 shadow-sm dark:bg-slate-900 ${
              isActive
                ? "border-sky-400 dark:border-sky-600"
                : "border-slate-200 dark:border-slate-800"
            }`}
          >
            <button
              className="w-full text-left"
              onClick={() => setExpanded(isOpen ? null : p.id)}
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-lg font-bold">{p.name}</h2>
                <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {LEVEL_LABELS[p.level]}
                </span>
              </div>
              {p.description && (
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {p.description}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-400">
                {p.days.length} pass i rotationen
                {p.days_per_week ? ` · ${p.days_per_week} dagar/vecka` : ""}
                {isActive ? " · ✅ Aktivt" : ""}
              </p>
            </button>

            {isOpen && (
              <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                {p.days.map((day) => (
                  <div key={day.id}>
                    <p className="text-sm font-semibold">{day.name}</p>
                    <ul className="mt-1 space-y-0.5 text-sm text-slate-600 dark:text-slate-300">
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
                    className="w-full rounded-xl bg-sky-600 py-2.5 font-semibold text-white active:bg-sky-700"
                  >
                    Aktivera programmet
                  </button>
                )}
              </div>
            )}
          </section>
        );
      })}
    </main>
  );
}
