"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { Exercise } from "../lib/types";

const MUSCLES = [
  "bröst",
  "rygg",
  "ben",
  "säte",
  "axlar",
  "biceps",
  "triceps",
  "mage",
];

export default function ExercisesPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [search, setSearch] = useState("");
  const [muscle, setMuscle] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Exercise[]>("/api/exercises")
      .then(setExercises)
      .catch((e: Error) => setError(e.message));
  }, []);

  const filtered = useMemo(
    () =>
      exercises.filter(
        (e) =>
          (!search || e.name.toLowerCase().includes(search.toLowerCase())) &&
          (!muscle || e.muscle_groups.includes(muscle))
      ),
    [exercises, search, muscle]
  );

  async function createExercise() {
    if (!newName.trim()) return;
    try {
      const created = await api<Exercise>("/api/exercises", {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          muscle_groups: muscle ? [muscle] : [],
          equipment: [],
        }),
      });
      setExercises((prev) =>
        [...prev, created].sort((a, b) => a.name.localeCompare(b.name, "sv"))
      );
      setNewName("");
      setShowForm(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Övningar</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-xl bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white"
        >
          + Ny övning
        </button>
      </div>

      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      {showForm && (
        <div className="flex gap-2 rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Namn på övningen"
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
          />
          <button
            onClick={createExercise}
            className="rounded-lg bg-sky-600 px-4 text-sm font-semibold text-white"
          >
            Spara
          </button>
        </div>
      )}

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Sök övning…"
        className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-700 dark:bg-slate-900"
      />

      <div className="flex flex-wrap gap-1.5">
        {MUSCLES.map((m) => (
          <button
            key={m}
            onClick={() => setMuscle(muscle === m ? null : m)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
              muscle === m
                ? "bg-sky-600 text-white"
                : "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <ul className="space-y-2">
        {filtered.map((e) => (
          <li
            key={e.id}
            className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"
          >
            <p className="font-medium">
              {e.name}
              {!e.is_global && (
                <span className="ml-2 text-xs text-sky-600 dark:text-sky-400">
                  egen
                </span>
              )}
            </p>
            <p className="text-xs capitalize text-slate-500 dark:text-slate-400">
              {[...e.muscle_groups, ...e.equipment].join(" · ")}
            </p>
          </li>
        ))}
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">
            Inga övningar matchar.
          </p>
        )}
      </ul>
    </main>
  );
}
