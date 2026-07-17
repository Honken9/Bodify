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

// Signatur för en måltids innehåll — används för att veta om exakt
// denna kombination redan är sparad som favorit.
function mealSignature(items: { food_item_id: string; grams: number }[]): string {
  return items
    .map((i) => `${i.food_item_id}:${Math.round(i.grams * 10)}`)
    .sort()
    .join("|");
}

export default function FoodPage() {
  const [day, setDay] = useState(() => isoDate(new Date()));
  const [log, setLog] = useState<DayLog | null>(null);
  const [templates, setTemplates] = useState<MealTemplate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pickerMeal, setPickerMeal] = useState<MealKey | null>(null);
  const [editTargets, setEditTargets] = useState(false);

  const refresh = useCallback(() => {
    api<DayLog>(`/api/meals?day=${day}`)
      .then(setLog)
      .catch((e: Error) => setError(e.message));
    api<MealTemplate[]>("/api/meal-templates")
      .then(setTemplates)
      .catch(() => {});
  }, [day]);

  useEffect(refresh, [refresh]);

  async function removeEntry(id: string) {
    await api(`/api/meals/${id}`, { method: "DELETE" });
    refresh();
  }

  function savedTemplateFor(entries: MealEntry[]): MealTemplate | undefined {
    const sig = mealSignature(
      entries.map((e) => ({ food_item_id: e.food_item.id, grams: e.grams }))
    );
    return templates.find((t) => mealSignature(t.items) === sig);
  }

  async function toggleMealFavorite(meal: MealKey, entries: MealEntry[]) {
    try {
      const saved = savedTemplateFor(entries);
      if (saved) {
        await api(`/api/meal-templates/${saved.id}`, { method: "DELETE" });
      } else {
        // Namnet sätts automatiskt från innehållet — inget att fylla i
        const names = entries.map((e) => e.food_item.name);
        const name = (
          names.length === 1 ? names[0] : `${names[0]} +${names.length - 1}`
        ).slice(0, 120);
        await api("/api/meal-templates/from-meal", {
          method: "POST",
          body: JSON.stringify({ name, eaten_on: day, meal }),
        });
      }
      api<MealTemplate[]>("/api/meal-templates")
        .then(setTemplates)
        .catch(() => {});
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const isToday = day === isoDate(new Date());

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Kost</h1>
        <button
          onClick={() => setEditTargets(true)}
          className="text-sm text-sage dark:text-emerald-400"
        >
          Mål ⚙️
        </button>
      </div>

      <div className="flex items-center justify-between rounded-xl border border-line bg-white px-2 py-1.5 dark:border-stone-800 dark:bg-stone-900">
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
          <section className="rounded-2xl border border-line bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
            <MacroBar
              label="Kalorier"
              value={log.totals.kcal}
              target={log.targets.kcal}
              unit="kcal"
              color="bg-sage"
            />
            <div className="mt-3 grid grid-cols-3 gap-3">
              <MacroBar
                label="Protein"
                value={log.totals.protein_g}
                target={log.targets.protein_g}
                unit="g"
                color="bg-sage"
                compact
              />
              <MacroBar
                label="Kolhydrater"
                value={log.totals.carbs_g}
                target={log.targets.carbs_g}
                unit="g"
                color="bg-carb"
                compact
              />
              <MacroBar
                label="Fett"
                value={log.totals.fat_g}
                target={log.targets.fat_g}
                unit="g"
                color="bg-fat"
                compact
              />
            </div>
          </section>

          {log.micros.length > 0 && <MicrosSection micros={log.micros} />}

          <div className="flex flex-col gap-4 desktop:grid desktop:grid-cols-2 desktop:items-start">
          {(Object.keys(MEAL_LABELS) as MealKey[]).map((meal) => (
            <MealSection
              key={meal}
              meal={meal}
              entries={log.entries.filter((e) => e.meal === meal)}
              saved={
                !!savedTemplateFor(log.entries.filter((e) => e.meal === meal))
              }
              onAdd={() => setPickerMeal(meal)}
              onRemove={removeEntry}
              onToggleFavorite={() =>
                toggleMealFavorite(
                  meal,
                  log.entries.filter((e) => e.meal === meal)
                )
              }
            />
          ))}
          </div>
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
          className={`font-medium ${compact ? "text-xs" : "text-sm"} text-muted dark:text-faint`}
        >
          {label}
        </span>
        {!compact && (
          <span className="text-sm font-semibold">
            {Math.round(value)} / {target} {unit}
          </span>
        )}
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-shell dark:bg-stone-800">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {compact && (
        <p className="mt-0.5 text-xs text-muted dark:text-faint">
          {Math.round(value)}/{target} {unit}
        </p>
      )}
    </div>
  );
}

function MicrosSection({ micros }: { micros: import("../lib/types").Micro[] }) {
  const [open, setOpen] = useState(false);
  const lowCount = micros.filter(
    (m) => m.kind === "rdi" && m.percent < 50
  ).length;
  const overCount = micros.filter(
    (m) => m.kind === "max" && m.percent > 100
  ).length;

  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <button
        className="flex w-full items-center justify-between"
        onClick={() => setOpen((v) => !v)}
      >
        <h2 className="font-bold">Vitaminer & mineraler</h2>
        <span className="text-xs text-muted">
          {micros.length} ämnen
          {overCount > 0 && ` · ⚠️ ${overCount} över gräns`}
          {open ? " ▴" : " ▾"}
        </span>
      </button>

      {open && (
        <>
          <div className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 desktop:grid-cols-2">
            {micros.map((m) => {
              const over = m.kind === "max" && m.percent > 100;
              const bar =
                m.kind === "max"
                  ? over
                    ? "bg-red-400"
                    : "bg-sand-strong"
                  : "bg-sage";
              return (
                <div key={m.key}>
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="font-medium text-muted dark:text-faint">
                      {m.label}
                      {m.kind === "max" && (
                        <span className="ml-1 text-[10px] text-faint">
                          (max)
                        </span>
                      )}
                    </span>
                    <span
                      className={`font-semibold tabular-nums ${
                        over ? "text-red-600 dark:text-red-400" : ""
                      }`}
                    >
                      {m.amount} {m.unit} · {m.percent} %
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-shell dark:bg-stone-800">
                    <div
                      className={`h-full ${bar}`}
                      style={{ width: `${Math.min(100, m.percent)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] leading-snug text-faint">
            % av referensvärde för vuxna (NNR 2023). Visar bara ämnen där
            livsmedlens källdata finns — streckkodsvaror ger mest.
            {lowCount > 0 &&
              " Lågt värde kan bero på att data saknas för vissa livsmedel."}
          </p>
        </>
      )}
    </section>
  );
}

function MealSection({
  meal,
  entries,
  saved,
  onAdd,
  onRemove,
  onToggleFavorite,
}: {
  meal: MealKey;
  entries: MealEntry[];
  saved: boolean;
  onAdd: () => void;
  onRemove: (id: string) => void;
  onToggleFavorite: () => void;
}) {
  const kcal = Math.round(entries.reduce((sum, e) => sum + e.kcal, 0));
  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">{MEAL_LABELS[meal]}</h2>
        <div className="flex items-center gap-3">
          {entries.length > 0 && (
            <>
              <span className="text-sm text-faint">{kcal} kcal</span>
              <button
                onClick={onToggleFavorite}
                title={
                  saved
                    ? "Ta bort från favoritmåltider"
                    : "Spara som favoritmåltid"
                }
                aria-label={
                  saved
                    ? "Ta bort från favoritmåltider"
                    : "Spara som favoritmåltid"
                }
                className={`text-lg leading-none ${
                  saved ? "" : "text-faint"
                }`}
              >
                {saved ? "❤️" : "♡"}
              </button>
            </>
          )}
          <button
            onClick={onAdd}
            className="rounded-lg bg-sage px-2.5 py-1 text-sm font-bold text-white"
          >
            +
          </button>
        </div>
      </div>
      {entries.length > 0 && (
        <ul className="mt-2 divide-y divide-line dark:divide-stone-800">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center justify-between py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {e.food_item.name}
                  {e.food_item.brand && (
                    <span className="text-faint"> · {e.food_item.brand}</span>
                  )}
                </p>
                <p className="text-xs text-muted dark:text-faint">
                  {Math.round(e.grams)} g · {Math.round(e.kcal)} kcal ·{" "}
                  {Math.round(e.protein_g)} g protein
                </p>
              </div>
              <button
                onClick={() => onRemove(e.id)}
                className="px-2 text-faint hover:text-red-500"
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
        className="w-full max-w-md rounded-t-3xl bg-white p-5 dark:bg-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-4 text-lg font-bold">Dagliga mål</h3>
        <div className="mb-3 flex gap-1.5">
          {(
            [
              ["Deff", { kcal: 2000, protein_g: 180, carbs_g: 160, fat_g: 65 }],
              ["Underhåll", { kcal: 2500, protein_g: 160, carbs_g: 280, fat_g: 80 }],
              ["Bygg", { kcal: 3000, protein_g: 180, carbs_g: 360, fat_g: 95 }],
            ] as [string, NutritionTargets][]
          ).map(([label, preset]) => (
            <button
              key={label}
              onClick={() => setForm({ ...preset })}
              className="flex-1 rounded-lg bg-shell py-2 text-xs font-semibold text-muted dark:bg-stone-800 dark:text-stone-300"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="space-y-3">
          {fields.map(({ key, label }) => (
            <label key={key} className="block">
              <span className="text-sm text-muted dark:text-faint">
                {label}
              </span>
              <input
                inputMode="numeric"
                value={form[key]}
                onChange={(e) =>
                  setForm({ ...form, [key]: Number(e.target.value) || 0 })
                }
                className="mt-1 w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-stone-700"
              />
            </label>
          ))}
        </div>
        <button
          disabled={saving}
          onClick={save}
          className="mt-4 w-full rounded-xl bg-sage py-3 font-semibold text-white disabled:opacity-50"
        >
          Spara mål
        </button>
      </div>
    </div>
  );
}
