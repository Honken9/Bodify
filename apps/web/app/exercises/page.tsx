"use client";

import { useEffect, useMemo, useState } from "react";
import GymVision from "../components/GymVision";
import LineChart from "../components/LineChart";
import MuscleMap from "../components/MuscleMap";
import { api } from "../lib/api";
import type { Exercise } from "../lib/types";

type ProgressionData = {
  points: { day: string; best_weight: number; est_1rm: number; volume: number }[];
  records: {
    best_weight: number;
    best_1rm: number;
    best_volume: number;
    sessions: number;
  };
};

/** 📈 Personbästa + utvecklingskurva (uppskattat 1RM) för en övning. */
function Progression({ exerciseId }: { exerciseId: string }) {
  const [data, setData] = useState<ProgressionData | null>(null);

  useEffect(() => {
    api<ProgressionData>(`/api/exercises/${exerciseId}/progression`)
      .then(setData)
      .catch(() => {});
  }, [exerciseId]);

  if (!data || data.points.length === 0) return null;
  const r = data.records;

  return (
    <div className="mt-3 border-t border-line pt-3 dark:border-night-shell">
      <p className="text-xs font-semibold uppercase tracking-wide text-faint">
        📈 Din utveckling · {r.sessions} pass
      </p>
      <div className="mt-1.5 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-cream-deep p-2 dark:bg-night-shell/60">
          <p className="text-sm font-bold">{r.best_weight} kg</p>
          <p className="text-[10px] uppercase text-faint">Tyngsta set</p>
        </div>
        <div className="rounded-xl bg-cream-deep p-2 dark:bg-night-shell/60">
          <p className="text-sm font-bold">{Math.round(r.best_1rm)} kg</p>
          <p className="text-[10px] uppercase text-faint">Est. 1RM</p>
        </div>
        <div className="rounded-xl bg-cream-deep p-2 dark:bg-night-shell/60">
          <p className="text-sm font-bold">
            {Math.round(r.best_volume).toLocaleString("sv-SE")}
          </p>
          <p className="text-[10px] uppercase text-faint">Volym-PB (kg)</p>
        </div>
      </div>
      {data.points.length >= 2 && (
        <div className="mt-2">
          <LineChart
            data={data.points.map((p) => ({
              measured_at: p.day,
              value: p.est_1rm,
            }))}
            height={120}
            unit="kg"
            decimals={0}
          />
        </div>
      )}
    </div>
  );
}

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
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showVision, setShowVision] = useState(false);
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
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Övningar</h1>
        <div className="flex gap-1.5">
          <button
            onClick={() => setShowVision(true)}
            className="rounded-xl border border-line-strong px-3 py-1.5 text-sm font-semibold dark:border-night-strong"
          >
            📷 Gym-vision
          </button>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-xl bg-navy px-3 py-1.5 text-sm font-semibold text-white"
          >
            + Ny
          </button>
        </div>
      </div>

      {showVision && <GymVision onClose={() => setShowVision(false)} />}

      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      {showForm && (
        <div className="flex gap-2 rounded-2xl border border-line bg-white p-3 dark:border-night-shell dark:bg-night-card">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Namn på övningen"
            className="min-w-0 flex-1 rounded-lg border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong"
          />
          <button
            onClick={createExercise}
            className="rounded-lg bg-navy px-4 text-sm font-semibold text-white"
          >
            Spara
          </button>
        </div>
      )}

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Sök övning…"
        className="rounded-xl border border-line-strong bg-white px-4 py-2.5 dark:border-night-strong dark:bg-night-card"
      />

      <div className="flex flex-wrap gap-1.5">
        {MUSCLES.map((m) => (
          <button
            key={m}
            onClick={() => setMuscle(muscle === m ? null : m)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
              muscle === m
                ? "bg-navy text-white"
                : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <ul className="space-y-2 desktop:grid desktop:grid-cols-2 desktop:gap-3 desktop:space-y-0 desktop:items-start">
        {filtered.map((e) => {
          const isOpen = expanded === e.id;
          return (
            <li
              key={e.id}
              className="rounded-xl border border-line bg-white px-4 py-3 dark:border-night-shell dark:bg-night-card"
            >
              <button
                onClick={() => setExpanded(isOpen ? null : e.id)}
                className="w-full text-left"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium">
                    {e.name}
                    {!e.is_global && (
                      <span className="ml-2 text-xs text-navy dark:text-lime">
                        egen
                      </span>
                    )}
                  </p>
                  <span className="text-xs text-faint">
                    {isOpen ? "▴" : "▾"}
                  </span>
                </div>
                <p className="text-xs capitalize text-muted dark:text-faint">
                  {[...e.muscle_groups, ...e.equipment].join(" · ")}
                </p>
              </button>

              {isOpen && (
                <div className="mt-3 border-t border-line pt-3 dark:border-night-shell">
                  {e.muscle_groups.length > 0 && (
                    <>
                      <MuscleMap groups={e.muscle_groups} height={140} />
                      <p className="mt-1 text-center text-xs">
                        <span className="font-semibold">💪 Tränar: </span>
                        <span className="capitalize text-muted dark:text-night-muted">
                          {e.muscle_groups.join(", ")}
                        </span>
                        {e.equipment.length > 0 && (
                          <span className="capitalize text-faint">
                            {" · "}🏋️ {e.equipment.join(", ")}
                          </span>
                        )}
                      </p>
                    </>
                  )}
                  {e.description ? (
                    <p className="mt-2 text-sm leading-relaxed text-muted dark:text-night-muted">
                      {e.description}
                    </p>
                  ) : (
                    <p className="mt-2 text-xs text-faint">
                      Ingen beskrivning ännu för den här övningen.
                    </p>
                  )}
                  <Progression exerciseId={e.id} />
                </div>
              )}
            </li>
          );
        })}
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-faint">
            Inga övningar matchar.
          </p>
        )}
      </ul>
    </main>
  );
}
