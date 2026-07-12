"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  MEAL_LABELS,
  type DayLog,
  type FoodItem,
  type MealEntry,
  type MealKey,
  type MealTemplate,
  type NutritionTargets,
} from "../lib/types";
import FoodPicker from "./FoodPicker";

function isoDate(d: Date): string {
  return d.toLocaleDateString("sv-SE");
}

function shiftDay(day: string, delta: number): string {
  const d = new Date(day);
  d.setDate(d.getDate() + delta);
  return isoDate(d);
}

export default function FoodPage() {
  const [day, setDay] = useState(() => isoDate(new Date()));
  const [log, setLog] = useState<DayLog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pickerMeal, setPickerMeal] = useState<MealKey | null>(null);
  const [editTargets, setEditTargets] = useState(false);

  const refresh = useCallback(() => {
    api<DayLog>(`/api/meals?day=${day}`)
      .then(setLog)
      .catch((e: Error) => setError(e.message));
  }, [day]);

  useEffect(refresh, [refresh]);

  async function removeEntry(id: string) {
    await api(`/api/meals/${id}`, { method: "DELETE" });
    refresh();
  }

  async function saveAsTemplate(meal: MealKey) {
    const name = window.prompt("Namn på mallen?");
    if (!name) return;
    try {
      await api("/api/meal-templates/from-meal", {
        method: "POST",
        body: JSON.stringify({ name, eaten_on: day, meal }),
      });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const isToday = day === isoDate(new Date());

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Kost</h1>
        <button
          onClick={() => setEditTargets(true)}
          className="text-sm text-sky-600 dark:text-sky-400"
        >
          Mål ⚙️
        </button>
      </div>

      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-2 py-1.5 dark:border-slate-800 dark:bg-slate-900">
        <button onClick={() => setDay(shiftDay(day, -1))} className="p-2 text-lg">
          ‹
        </button>
        <span className="font-semibold">
          {isToday
            ? "Idag"
            : new Intl.DateTimeFormat("sv-SE", {
                weekday: "long",
                day: "numeric",
                month: "short",
              }).format(new Date(day))}
        </span>
        <button
          onClick={() => setDay(shiftDay(day, 1))}
          disabled={isToday}
          className="p-2 text-lg disabled:opacity-30"
        >
          ›
        </button>
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {log && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <MacroBar
              label="Kalorier"
              value={log.totals.kcal}
              target={log.targets.kcal}
              unit="kcal"
              color="bg-sky-500"
            />
            <div className="mt-3 grid grid-cols-3 gap-3">
              <MacroBar
                label="Protein"
                value={log.totals.protein_g}
                target={log.targets.protein_g}
                unit="g"
                color="bg-emerald-500"
                compact
              />
              <MacroBar
                label="Kolhydrater"
                value={log.totals.carbs_g}
                target={log.targets.carbs_g}
                unit="g"
                color="bg-amber-500"
                compact
              />
              <MacroBar
                label="Fett"
                value={log.totals.fat_g}
                target={log.targets.fat_g}
                unit="g"
                color="bg-rose-400"
                compact
              />
            </div>
          </section>

          {(Object.keys(MEAL_LABELS) as MealKey[]).map((meal) => (
            <MealSection
              key={meal}
              meal={meal}
              entries={log.entries.filter((e) => e.meal === meal)}
              onAdd={() => setPickerMeal(meal)}
              onRemove={removeEntry}
              onSaveTemplate={() => saveAsTemplate(meal)}
            />
          ))}
        </>
      )}

      {pickerMeal && log && (
        <FoodPicker
          day={day}
          meal={pickerMeal}
          onClose={() => setPickerMeal(null)}
          onLogged={() => {
            setPickerMeal(null);
            refresh();
          }}
          onError={setError}
        />
      )}

      {editTargets && log && (
        <TargetsEditor
          current={log.targets}
          onClose={() => setEditTargets(false)}
          onSaved={() => {
            setEditTargets(false);
            refresh();
          }}
        />
      )}
    </main>
  );
}

function MacroBar({
  label,
  value,
  target,
  unit,
  color,
  compact,
}: {
  label: string;
  value: number;
  target: number;
  unit: string;
  color: string;
  compact?: boolean;
}) {
  const pct = target > 0 ? Math.min(100, (value / target) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span
          className={`font-medium ${compact ? "text-xs" : "text-sm"} text-slate-500 dark:text-slate-400`}
        >
          {label}
        </span>
        {!compact && (
          <span className="text-sm font-semibold">
            {Math.round(value)} / {target} {unit}
          </span>
        )}
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {compact && (
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {Math.round(value)}/{target} {unit}
        </p>
      )}
    </div>
  );
}

function MealSection({
  meal,
  entries,
  onAdd,
  onRemove,
  onSaveTemplate,
}: {
  meal: MealKey;
  entries: MealEntry[];
  onAdd: () => void;
  onRemove: (id: string) => void;
  onSaveTemplate: () => void;
}) {
  const kcal = Math.round(entries.reduce((sum, e) => sum + e.kcal, 0));
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">{MEAL_LABELS[meal]}</h2>
        <div className="flex items-center gap-3">
          {entries.length > 0 && (
            <>
              <span className="text-sm text-slate-400">{kcal} kcal</span>
              <button
                onClick={onSaveTemplate}
                title="Spara som mall"
                className="text-sm text-slate-400"
              >
                💾
              </button>
            </>
          )}
          <button
            onClick={onAdd}
            className="rounded-lg bg-sky-600 px-2.5 py-1 text-sm font-bold text-white"
          >
            +
          </button>
        </div>
      </div>
      {entries.length > 0 && (
        <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center justify-between py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {e.food_item.name}
                  {e.food_item.brand && (
                    <span className="text-slate-400"> · {e.food_item.brand}</span>
                  )}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {Math.round(e.grams)} g · {Math.round(e.kcal)} kcal ·{" "}
                  {Math.round(e.protein_g)} g protein
                </p>
              </div>
              <button
                onClick={() => onRemove(e.id)}
                className="px-2 text-slate-400 hover:text-red-500"
                aria-label="Ta bort"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TargetsEditor({
  current,
  onClose,
  onSaved,
}: {
  current: NutritionTargets;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({ ...current });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api("/api/nutrition-targets", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  const fields: { key: keyof NutritionTargets; label: string }[] = [
    { key: "kcal", label: "Kalorier (kcal)" },
    { key: "protein_g", label: "Protein (g)" },
    { key: "carbs_g", label: "Kolhydrater (g)" },
    { key: "fat_g", label: "Fett (g)" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-white p-5 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-4 text-lg font-bold">Dagliga mål</h3>
        <div className="space-y-3">
          {fields.map(({ key, label }) => (
            <label key={key} className="block">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {label}
              </span>
              <input
                inputMode="numeric"
                value={form[key]}
                onChange={(e) =>
                  setForm({ ...form, [key]: Number(e.target.value) || 0 })
                }
                className="mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-4 py-2.5 dark:border-slate-700"
              />
            </label>
          ))}
        </div>
        <button
          disabled={saving}
          onClick={save}
          className="mt-4 w-full rounded-xl bg-sky-600 py-3 font-semibold text-white disabled:opacity-50"
        >
          Spara mål
        </button>
      </div>
    </div>
  );
}
