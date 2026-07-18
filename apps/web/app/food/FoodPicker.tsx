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
import CameraCapture from "../components/CameraCapture";
import type { FoodItem, MealKey, MealTemplate, RecentFood } from "../lib/types";

type Tab = "quick" | "search" | "scan" | "photo" | "templates" | "new";

type Picked = { food: FoodItem; grams?: number };

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
  const [tab, setTab] = useState<Tab>("quick");
  const [selected, setSelected] = useState<Picked | null>(null);

  // Favoriter delas mellan flikarna (stjärnan i Snabbval och Sök)
  const [favIds, setFavIds] = useState<Set<string>>(new Set());
  const [favorites, setFavorites] = useState<FoodItem[]>([]);

  useEffect(() => {
    api<FoodItem[]>("/api/food/favorites")
      .then((rows) => {
        setFavorites(rows);
        setFavIds(new Set(rows.map((f) => f.id)));
      })
      .catch(() => {});
  }, []);

  async function toggleFavorite(food: FoodItem) {
    const isFav = favIds.has(food.id);
    // Optimistisk uppdatering — stjärnan ska kännas direkt
    setFavIds((prev) => {
      const next = new Set(prev);
      if (isFav) next.delete(food.id);
      else next.add(food.id);
      return next;
    });
    setFavorites((prev) =>
      isFav ? prev.filter((f) => f.id !== food.id) : [food, ...prev]
    );
    try {
      await api(`/api/food/favorites/${food.id}`, {
        method: isFav ? "DELETE" : "PUT",
      });
    } catch (e) {
      onError((e as Error).message);
    }
  }

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
        className="flex max-h-[85dvh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-white p-5 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex shrink-0 items-center justify-between">
          <h3 className="text-lg font-bold">Lägg till livsmedel</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>

        {selected ? (
          <GramsForm
            food={selected.food}
            initialGrams={selected.grams}
            onBack={() => setSelected(null)}
            onLog={logFood}
          />
        ) : (
          <>
            <div className="mb-3 flex shrink-0 gap-1 overflow-x-auto">
              {(
                [
                  ["quick", "⭐ Snabb"],
                  ["search", "🔍 Sök"],
                  ["scan", "📷 Kod"],
                  ["photo", "🍽 Foto"],
                  ["templates", "❤️ Måltider"],
                  ["new", "＋ Eget"],
                ] as [Tab, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`shrink-0 rounded-lg px-2.5 py-2 text-xs font-semibold ${
                    tab === key
                      ? "bg-navy text-white"
                      : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {tab === "quick" && (
                <QuickTab
                  favorites={favorites}
                  favIds={favIds}
                  onToggleFavorite={toggleFavorite}
                  onPick={setSelected}
                />
              )}
              {tab === "search" && (
                <SearchTab
                  favIds={favIds}
                  onToggleFavorite={toggleFavorite}
                  onPick={(food) => setSelected({ food })}
                />
              )}
              {tab === "scan" && (
                <ScanTab
                  onPick={(food) => setSelected({ food })}
                  onError={onError}
                />
              )}
              {tab === "photo" && (
                <MealPhotoTab
                  day={day}
                  meal={meal}
                  onLogged={onLogged}
                  onError={onError}
                />
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
                <NewFoodTab
                  onCreated={(food) => setSelected({ food })}
                  onError={onError}
                />
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
  initialGrams,
  onBack,
  onLog,
}: {
  food: FoodItem;
  initialGrams?: number;
  onBack: () => void;
  onLog: (food: FoodItem, grams: number) => void;
}) {
  const [grams, setGrams] = useState(String(initialGrams ?? 100));
  const g = Number(grams) || 0;
  const per = food.per_100g;
  const kcal = Math.round(((per.kcal ?? 0) * g) / 100);
  const protein = Math.round(((per.protein_g ?? 0) * g) / 100);

  return (
    <div>
      <button onClick={onBack} className="mb-2 text-sm text-navy">
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
          className="w-28 rounded-xl border border-line-strong bg-transparent px-4 py-2.5 text-center text-lg font-semibold dark:border-night-strong"
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
            className="flex-1 rounded-lg bg-shell py-1.5 text-xs font-medium dark:bg-night-shell"
          >
            {v} g
          </button>
        ))}
      </div>
      <button
        disabled={g <= 0}
        onClick={() => onLog(food, g)}
        className="mt-4 w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
      >
        Logga
      </button>
    </div>
  );
}

function FoodRow({
  food,
  detail,
  isFav,
  onToggleFavorite,
  onPick,
}: {
  food: FoodItem;
  detail?: string;
  isFav: boolean;
  onToggleFavorite: (f: FoodItem) => void;
  onPick: () => void;
}) {
  return (
    <li className="flex items-center gap-1">
      <button onClick={onPick} className="min-w-0 flex-1 py-2.5 text-left">
        <p className="truncate text-sm font-medium">
          {food.name}
          {food.source === "custom" && (
            <span className="ml-1.5 text-xs text-navy">egen</span>
          )}
        </p>
        <p className="text-xs text-faint">
          {detail ??
            `${food.brand ? `${food.brand} · ` : ""}${Math.round(
              food.per_100g.kcal ?? 0
            )} kcal/100 g`}
        </p>
      </button>
      <button
        onClick={() => onToggleFavorite(food)}
        className="p-2 text-lg leading-none"
        aria-label={isFav ? "Ta bort favorit" : "Spara som favorit"}
      >
        {isFav ? "⭐" : "☆"}
      </button>
    </li>
  );
}

function QuickTab({
  favorites,
  favIds,
  onToggleFavorite,
  onPick,
}: {
  favorites: FoodItem[];
  favIds: Set<string>;
  onToggleFavorite: (f: FoodItem) => void;
  onPick: (p: Picked) => void;
}) {
  const [recent, setRecent] = useState<RecentFood[]>([]);
  const [suggestions, setSuggestions] = useState<FoodItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [showAllFavorites, setShowAllFavorites] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    Promise.all([
      api<RecentFood[]>("/api/food/recent"),
      api<FoodItem[]>("/api/food/suggestions"),
    ])
      .then(([recent, suggestions]) => {
        setRecent(recent);
        setSuggestions(suggestions);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const heading = (text: string) => (
    <h4 className="mb-1 mt-4 text-xs font-bold uppercase tracking-wide text-faint first:mt-0">
      {text}
    </h4>
  );

  // Kompakt: max 5 per sektion så listan inte växer förbi flikarna —
  // resten göms bakom "visa fler"
  const visibleFavorites = showAllFavorites ? favorites : favorites.slice(0, 5);

  return (
    <div>
      {recent.length > 0 && (
        <>
          {heading("Senaste")}
          <ul className="divide-y divide-line dark:divide-night-shell">
            {recent.slice(0, 5).map((r) => (
              <FoodRow
                key={r.food.id}
                food={r.food}
                detail={`Senast ${r.grams} g · ${Math.round(
                  ((r.food.per_100g.kcal ?? 0) * r.grams) / 100
                )} kcal`}
                isFav={favIds.has(r.food.id)}
                onToggleFavorite={onToggleFavorite}
                onPick={() => onPick({ food: r.food, grams: r.grams })}
              />
            ))}
          </ul>
        </>
      )}

      {favorites.length > 0 && (
        <>
          {heading("⭐ Favoriter")}
          <ul className="divide-y divide-line dark:divide-night-shell">
            {visibleFavorites.map((f) => (
              <FoodRow
                key={f.id}
                food={f}
                isFav={favIds.has(f.id)}
                onToggleFavorite={onToggleFavorite}
                onPick={() => onPick({ food: f })}
              />
            ))}
          </ul>
          {favorites.length > 5 && (
            <button
              onClick={() => setShowAllFavorites((v) => !v)}
              className="mt-1 w-full rounded-lg bg-shell py-2 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
            >
              {showAllFavorites
                ? "Visa färre ▴"
                : `Visa alla ${favorites.length} favoriter ▾`}
            </button>
          )}
        </>
      )}

      {loaded && recent.length === 0 && favorites.length === 0 && (
        <p className="rounded-lg bg-shell p-3 text-center text-sm text-muted dark:bg-night-shell dark:text-night-muted">
          Här samlas dina senast loggade livsmedel och favoriter (☆) för
          snabb loggning.
        </p>
      )}

      {suggestions.length > 0 && (
        <>
          <button
            onClick={() => setShowSuggestions((v) => !v)}
            className="mt-4 flex w-full items-center justify-between rounded-lg bg-shell px-3 py-2.5 text-sm font-semibold dark:bg-night-shell"
          >
            <span>💡 Vanliga livsmedel</span>
            <span className="text-xs text-muted">
              {suggestions.length} st {showSuggestions ? "▴" : "▾"}
            </span>
          </button>
          {showSuggestions && (
            <ul className="divide-y divide-line dark:divide-night-shell">
              {suggestions.map((f) => (
                <FoodRow
                  key={f.id}
                  food={f}
                  isFav={favIds.has(f.id)}
                  onToggleFavorite={onToggleFavorite}
                  onPick={() => onPick({ food: f })}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function SearchTab({
  favIds,
  onToggleFavorite,
  onPick,
}: {
  favIds: Set<string>;
  onToggleFavorite: (f: FoodItem) => void;
  onPick: (f: FoodItem) => void;
}) {
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
        className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong"
      />
      {loading && (
        <p className="py-4 text-center text-sm text-faint">Söker…</p>
      )}
      <ul className="mt-2 divide-y divide-line dark:divide-night-shell">
        {results.map((f) => (
          <FoodRow
            key={f.id}
            food={f}
            isFav={favIds.has(f.id)}
            onToggleFavorite={onToggleFavorite}
            onPick={() => onPick(f)}
          />
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
  const [missingCode, setMissingCode] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    kcal: "",
    protein_g: "",
    carbs_g: "",
    fat_g: "",
  });
  const [saving, setSaving] = useState(false);

  async function handleDetected(code: string) {
    if (missingCode) return; // formuläret är öppet — skanna inte vidare
    setStatus(`Slår upp ${code}…`);
    try {
      const food = await api<FoodItem>(`/api/food/barcode/${code}`);
      onPick(food);
    } catch (e) {
      const msg = (e as Error).message;
      setStatus(msg);
      if (msg.includes("finns inte")) setMissingCode(code); // 404 → lägg in själv
    }
  }

  async function saveMissing() {
    if (!missingCode || !form.name.trim() || !form.kcal) return;
    setSaving(true);
    try {
      const food = await api<FoodItem>("/api/food", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          barcode: missingCode,
          per_100g: {
            kcal: Number(form.kcal) || 0,
            protein_g: Number(form.protein_g) || 0,
            carbs_g: Number(form.carbs_g) || 0,
            fat_g: Number(form.fat_g) || 0,
          },
        }),
      });
      onPick(food); // nästa skanning av samma vara hittar den direkt
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (missingCode) {
    return (
      <div className="space-y-2">
        <p className="rounded-lg bg-sand p-2.5 text-sm text-sand-ink dark:bg-night-shell dark:text-lime">
          Streckkoden <strong>{missingCode}</strong> finns inte i databasen.
          Fyll i från förpackningens näringstabell (per 100 g) — nästa gång
          hittas varan direkt.
        </p>
        <input
          autoFocus
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Namn, t.ex. Kvarg vanilj"
          className="w-full rounded-xl border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong"
        />
        <div className="grid grid-cols-4 gap-2">
          {(
            [
              ["kcal", "kcal"],
              ["protein_g", "Protein"],
              ["carbs_g", "Kolh."],
              ["fat_g", "Fett"],
            ] as const
          ).map(([key, label]) => (
            <input
              key={key}
              type="number"
              inputMode="decimal"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={label}
              className="rounded-xl border border-line-strong bg-transparent px-2 py-2 text-sm dark:border-night-strong"
            />
          ))}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setMissingCode(null);
              setStatus(null);
            }}
            className="flex-1 rounded-xl border border-line-strong py-2.5 text-sm font-semibold text-muted dark:border-night-strong dark:text-night-muted"
          >
            Skanna igen
          </button>
          <button
            onClick={saveMissing}
            disabled={saving || !form.name.trim() || !form.kcal}
            className="flex-1 rounded-xl bg-navy py-2.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Sparar…" : "Spara & välj"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {status && (
        <p className="mb-2 rounded-lg bg-shell p-2 text-center text-sm dark:bg-night-shell">
          {status}
        </p>
      )}
      <BarcodeScanner onDetected={handleDetected} onError={onError} />
    </div>
  );
}

type AnalyzedItem = {
  name: string;
  grams: number;
  ai_grams?: number; // AI:ns ursprungliga gissning — för kalibrering
  per_100g: {
    kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
};

function MealPhotoTab({
  day,
  meal,
  onLogged,
  onError,
}: {
  day: string;
  meal: MealKey;
  onLogged: () => void;
  onError: (msg: string) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<AnalyzedItem[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [calibrated, setCalibrated] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [hasWebcam, setHasWebcam] = useState(false);

  useEffect(() => {
    // På datorer öppnar filväljaren inte kameran — visa webbkameraknapp
    setHasWebcam(
      typeof navigator !== "undefined" &&
        !!navigator.mediaDevices?.getUserMedia &&
        window.matchMedia("(pointer: fine)").matches
    );
  }, []);

  async function analyze(file: Blob) {
    setBusy("Analyserar fotot…");
    setItems(null);
    try {
      const { downscaleImage } = await import("../lib/image");
      const small = await downscaleImage(file);
      const form = new FormData();
      form.append("file", small, "mat.jpg");
      const res = await fetch("/api/ai/meal-vision", {
        method: "POST",
        body: form,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Fel ${res.status}`);
      setCalibrated(!!body.calibrated);
      setItems(
        (body.items as AnalyzedItem[]).map((it) => ({
          ...it,
          ai_grams: it.grams,
        }))
      );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function update(index: number, patch: Partial<AnalyzedItem>) {
    setItems((prev) =>
      prev ? prev.map((it, i) => (i === index ? { ...it, ...patch } : it)) : prev
    );
  }

  function remove(index: number) {
    setItems((prev) => (prev ? prev.filter((_, i) => i !== index) : prev));
  }

  const kcalOf = (it: AnalyzedItem) =>
    Math.round((it.per_100g.kcal * it.grams) / 100);
  const totalKcal = (items ?? []).reduce((sum, it) => sum + kcalOf(it), 0);
  const totalProtein = Math.round(
    (items ?? []).reduce(
      (sum, it) => sum + (it.per_100g.protein_g * it.grams) / 100,
      0
    )
  );

  async function logAll() {
    if (!items || items.length === 0) return;
    setBusy("Loggar måltiden…");
    try {
      await api("/api/meals/photo-log", {
        method: "POST",
        body: JSON.stringify({ eaten_on: day, meal, items }),
      });
      onLogged();
    } catch (e) {
      onError((e as Error).message);
      setBusy(null);
    }
  }

  return (
    <div>
      {!items && (
        <p className="mb-3 text-sm text-muted dark:text-faint">
          Fota tallriken så identifierar Shapiqo livsmedlen, uppskattar
          mängderna och räknar ut kalorier och makron. Tips: fota snett
          uppifrån med ett bestick i bild — det ger AI:n en storleksreferens.
        </p>
      )}

      <button
        disabled={!!busy}
        onClick={() => fileRef.current?.click()}
        className={`w-full rounded-xl py-3 font-semibold disabled:opacity-50 ${
          items
            ? "border border-line-strong text-muted dark:border-night-strong dark:text-night-muted"
            : "bg-navy text-white"
        }`}
      >
        {busy ?? (items ? "Ta nytt foto" : "🍽 Fota måltiden")}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) analyze(f);
          e.target.value = "";
        }}
      />

      {hasWebcam && !busy && (
        <button
          onClick={() => setShowCamera(true)}
          className="mt-2 w-full rounded-xl border border-line-strong py-2.5 text-sm font-semibold text-muted dark:border-night-strong dark:text-night-muted"
        >
          📷 Använd webbkameran
        </button>
      )}
      {showCamera && (
        <CameraCapture
          onCapture={(photo) => {
            setShowCamera(false);
            analyze(photo);
          }}
          onClose={() => setShowCamera(false)}
        />
      )}

      {items && (
        <div className="mt-3">
          <p className="mb-2 rounded-lg bg-sand px-3 py-2 text-xs text-sand-ink dark:bg-night-shell dark:text-lime">
            AI-uppskattning — justera namn och gram innan du loggar.
            Dina justeringar kalibrerar framtida gissningar.
            {calibrated && " (Mängderna är kalibrerade efter din historik.)"}
          </p>

          {items.length === 0 && (
            <p className="py-4 text-center text-sm text-faint">
              Inga livsmedel kvar — ta ett nytt foto.
            </p>
          )}

          <ul className="space-y-2">
            {items.map((it, i) => (
              <li key={i} className="flex items-center gap-2">
                <input
                  value={it.name}
                  onChange={(e) => update(i, { name: e.target.value })}
                  className="min-w-0 flex-1 rounded-lg border border-line-strong bg-transparent px-2.5 py-2 text-sm dark:border-night-strong"
                />
                <input
                  inputMode="numeric"
                  value={it.grams}
                  onChange={(e) =>
                    update(i, { grams: Number(e.target.value) || 0 })
                  }
                  className="w-16 rounded-lg border border-line-strong bg-transparent px-1 py-2 text-center text-sm dark:border-night-strong"
                />
                <span className="w-6 text-xs text-faint">g</span>
                <span className="w-14 text-right text-xs font-semibold tabular-nums">
                  {kcalOf(it)} kcal
                </span>
                <button
                  onClick={() => remove(i)}
                  className="px-1 text-faint hover:text-red-500"
                  aria-label="Ta bort"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          {items.length > 0 && (
            <>
              <div className="mt-3 flex items-center justify-between rounded-xl bg-cream-deep px-3 py-2 text-sm dark:bg-night-shell/60">
                <span className="font-semibold">Totalt</span>
                <span className="font-bold">
                  {totalKcal} kcal · {totalProtein} g protein
                </span>
              </div>
              <button
                disabled={!!busy || items.some((it) => it.grams <= 0)}
                onClick={logAll}
                className="mt-3 w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
              >
                {busy ?? `Logga måltiden (${totalKcal} kcal)`}
              </button>
            </>
          )}
        </div>
      )}
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
        Inga favoritmåltider ännu. Logga en måltid och tryck ♡ för att spara
        den — sen loggar du hela måltiden igen med ett tryck här.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line dark:divide-night-shell">
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
              className="rounded-lg bg-navy px-3 py-1.5 text-sm font-semibold text-white"
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
        className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong"
      />
      <div className="grid grid-cols-4 gap-2">
        {fields.map(({ key, label }) => (
          <label key={key} className="block">
            <span className="text-[10px] text-faint">{label}</span>
            <input
              inputMode="decimal"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="mt-0.5 w-full rounded-lg border border-line-strong bg-transparent px-2 py-2 text-center text-sm dark:border-night-strong"
            />
          </label>
        ))}
      </div>
      <button
        disabled={saving || !form.name.trim()}
        onClick={save}
        className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
      >
        Spara & välj mängd
      </button>
    </div>
  );
}
