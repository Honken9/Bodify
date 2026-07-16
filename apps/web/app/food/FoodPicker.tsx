"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

// Skannern (html5-qrcode) laddas först när fliken öppnas
const BarcodeScanner = dynamic(() => import("../components/BarcodeScanner"), {
  ssr: false,
  loading: () => (
    <p className="py-6 text-center text-sm text-faint">Laddar skannern…</p>
  ),
});
import type { FoodItem, MealKey, MealTemplate } from "../lib/types";

type Tab = "search" | "scan" | "templates" | "new";

export default function FoodPicker({
  day,
  meal,
  onClose,
  onLogged,
  onError,
}: {
  day: string;
  meal: MealKey;
  onClose: () => void;
  onLogged: () => void;
  onError: (msg: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("search");
  const [selected, setSelected] = useState<FoodItem | null>(null);

  async function logFood(food: FoodItem, grams: number) {
    try {
      await api("/api/meals", {
        method: "POST",
        body: JSON.stringify({
          eaten_on: day,
          meal,
          food_item_id: food.id,
          grams,
        }),
      });
      onLogged();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85dvh] w-full max-w-md flex-col rounded-t-3xl bg-white p-5 dark:bg-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">Lägg till livsmedel</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>

        {selected ? (
          <GramsForm
            food={selected}
            onBack={() => setSelected(null)}
            onLog={logFood}
          />
        ) : (
          <>
            <div className="mb-3 flex gap-1.5">
              {(
                [
                  ["search", "🔍 Sök"],
                  ["scan", "📷 Skanna"],
                  ["templates", "📄 Mallar"],
                  ["new", "＋ Eget"],
                ] as [Tab, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex-1 rounded-lg py-2 text-xs font-semibold ${
                    tab === key
                      ? "bg-sage text-white"
                      : "bg-shell text-muted dark:bg-stone-800 dark:text-stone-300"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {tab === "search" && <SearchTab onPick={setSelected} />}
              {tab === "scan" && (
                <ScanTab onPick={setSelected} onError={onError} />
              )}
              {tab === "templates" && (
                <TemplatesTab
                  day={day}
                  meal={meal}
                  onApplied={onLogged}
                  onError={onError}
                />
              )}
              {tab === "new" && (
                <NewFoodTab onCreated={setSelected} onError={onError} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function GramsForm({
  food,
  onBack,
  onLog,
}: {
  food: FoodItem;
  onBack: () => void;
  onLog: (food: FoodItem, grams: number) => void;
}) {
  const [grams, setGrams] = useState("100");
  const g = Number(grams) || 0;
  const per = food.per_100g;
  const kcal = Math.round(((per.kcal ?? 0) * g) / 100);
  const protein = Math.round(((per.protein_g ?? 0) * g) / 100);

  return (
    <div>
      <button onClick={onBack} className="mb-2 text-sm text-sage">
        ‹ Tillbaka
      </button>
      <p className="font-semibold">{food.name}</p>
      {food.brand && <p className="text-sm text-faint">{food.brand}</p>}
      <div className="mt-3 flex items-center gap-3">
        <input
          autoFocus
          inputMode="numeric"
          value={grams}
          onChange={(e) => setGrams(e.target.value)}
          className="w-28 rounded-xl border border-line-strong bg-transparent px-4 py-2.5 text-center text-lg font-semibold dark:border-stone-700"
        />
        <span className="text-muted">gram</span>
        <span className="ml-auto text-sm text-muted">
          {kcal} kcal · {protein} g protein
        </span>
      </div>
      <div className="mt-2 flex gap-1.5">
        {[50, 100, 150, 200, 250].map((v) => (
          <button
            key={v}
            onClick={() => setGrams(String(v))}
            className="flex-1 rounded-lg bg-shell py-1.5 text-xs font-medium dark:bg-stone-800"
          >
            {v} g
          </button>
        ))}
      </div>
      <button
        disabled={g <= 0}
        onClick={() => onLog(food, g)}
        className="mt-4 w-full rounded-xl bg-sage py-3 font-semibold text-white disabled:opacity-40"
      >
        Logga
      </button>
    </div>
  );
}

function SearchTab({ onPick }: { onPick: (f: FoodItem) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<FoodItem[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(() => {
      setLoading(true);
      api<FoodItem[]>(`/api/food/search?q=${encodeURIComponent(query.trim())}`)
        .then(setResults)
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 350);
  }, [query]);

  return (
    <div>
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Sök livsmedel…"
        className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-stone-700"
      />
      {loading && (
        <p className="py-4 text-center text-sm text-faint">Söker…</p>
      )}
      <ul className="mt-2 divide-y divide-line dark:divide-stone-800">
        {results.map((f) => (
          <li key={f.id}>
            <button onClick={() => onPick(f)} className="w-full py-2.5 text-left">
              <p className="text-sm font-medium">
                {f.name}
                {f.source === "custom" && (
                  <span className="ml-1.5 text-xs text-sage">egen</span>
                )}
              </p>
              <p className="text-xs text-faint">
                {f.brand ? `${f.brand} · ` : ""}
                {Math.round(f.per_100g.kcal ?? 0)} kcal/100 g
              </p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScanTab({
  onPick,
  onError,
}: {
  onPick: (f: FoodItem) => void;
  onError: (msg: string) => void;
}) {
  const [status, setStatus] = useState<string | null>(null);

  async function handleDetected(code: string) {
    setStatus(`Slår upp ${code}…`);
    try {
      const food = await api<FoodItem>(`/api/food/barcode/${code}`);
      onPick(food);
    } catch (e) {
      setStatus((e as Error).message);
    }
  }

  return (
    <div>
      {status && (
        <p className="mb-2 rounded-lg bg-shell p-2 text-center text-sm dark:bg-stone-800">
          {status}
        </p>
      )}
      <BarcodeScanner onDetected={handleDetected} onError={onError} />
    </div>
  );
}

function TemplatesTab({
  day,
  meal,
  onApplied,
  onError,
}: {
  day: string;
  meal: MealKey;
  onApplied: () => void;
  onError: (msg: string) => void;
}) {
  const [templates, setTemplates] = useState<MealTemplate[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api<MealTemplate[]>("/api/meal-templates")
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  async function apply(id: string) {
    try {
      await api(`/api/meal-templates/${id}/apply`, {
        method: "POST",
        body: JSON.stringify({ eaten_on: day, meal }),
      });
      onApplied();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  if (loaded && templates.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-faint">
        Inga mallar ännu. Logga en måltid och tryck 💾 för att spara den som
        mall.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line dark:divide-stone-800">
      {templates.map((t) => {
        const foodById = new Map(t.foods.map((f) => [f.id, f]));
        const kcal = Math.round(
          t.items.reduce(
            (sum, i) =>
              sum +
              ((foodById.get(i.food_item_id)?.per_100g.kcal ?? 0) * i.grams) /
                100,
            0
          )
        );
        return (
          <li key={t.id} className="flex items-center justify-between py-2.5">
            <div>
              <p className="text-sm font-medium">{t.name}</p>
              <p className="text-xs text-faint">
                {t.items.length} livsmedel · {kcal} kcal
              </p>
            </div>
            <button
              onClick={() => apply(t.id)}
              className="rounded-lg bg-sage px-3 py-1.5 text-sm font-semibold text-white"
            >
              Logga
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function NewFoodTab({
  onCreated,
  onError,
}: {
  onCreated: (f: FoodItem) => void;
  onError: (msg: string) => void;
}) {
  const [form, setForm] = useState({
    name: "",
    kcal: "",
    protein_g: "",
    carbs_g: "",
    fat_g: "",
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const food = await api<FoodItem>("/api/food", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          per_100g: {
            kcal: Number(form.kcal) || 0,
            protein_g: Number(form.protein_g) || 0,
            carbs_g: Number(form.carbs_g) || 0,
            fat_g: Number(form.fat_g) || 0,
          },
        }),
      });
      onCreated(food);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const fields: { key: keyof typeof form; label: string }[] = [
    { key: "kcal", label: "kcal / 100 g" },
    { key: "protein_g", label: "Protein g" },
    { key: "carbs_g", label: "Kolh. g" },
    { key: "fat_g", label: "Fett g" },
  ];

  return (
    <div className="space-y-3">
      <input
        autoFocus
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        placeholder="Namn (t.ex. Mammas köttbullar)"
        className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-stone-700"
      />
      <div className="grid grid-cols-4 gap-2">
        {fields.map(({ key, label }) => (
          <label key={key} className="block">
            <span className="text-[10px] text-faint">{label}</span>
            <input
              inputMode="decimal"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="mt-0.5 w-full rounded-lg border border-line-strong bg-transparent px-2 py-2 text-center text-sm dark:border-stone-700"
            />
          </label>
        ))}
      </div>
      <button
        disabled={saving || !form.name.trim()}
        onClick={save}
        className="w-full rounded-xl bg-sage py-3 font-semibold text-white disabled:opacity-40"
      >
        Spara & välj mängd
      </button>
    </div>
  );
}
