"use client";

import { useCallback, useEffect, useState } from "react";
import LineChart from "../components/LineChart";
import { api, formatDate } from "../lib/api";

const METRIC_META: Record<
  string,
  { label: string; unit: string; decimals: number }
> = {
  weight: { label: "Vikt", unit: "kg", decimals: 1 },
  fat_percent: { label: "Kroppsfett", unit: "%", decimals: 1 },
  muscle_mass: { label: "Muskelmassa", unit: "kg", decimals: 1 },
  hydration: { label: "Vattenmängd", unit: "kg", decimals: 1 },
  pwv: { label: "Pulsvågshastighet", unit: "m/s", decimals: 1 },
  resting_hr: { label: "Vilopuls", unit: "bpm", decimals: 0 },
  hrv: { label: "HRV", unit: "ms", decimals: 0 },
  vo2max: { label: "VO₂max", unit: "ml/kg/min", decimals: 1 },
  steps: { label: "Steg", unit: "/dag", decimals: 0 },
};

type Latest = Record<
  string,
  { value: number; measured_at: string; source: string }
>;

type Goal = {
  id: string;
  kind: string;
  title: string;
  target: Record<string, unknown>;
  progress: number;
  achieved_at: string | null;
  current: Record<string, unknown>;
};

export default function HealthPage() {
  const [latest, setLatest] = useState<Latest>({});
  const [selected, setSelected] = useState("weight");
  const [series, setSeries] = useState<
    { measured_at: string; value: number }[]
  >([]);
  const [days, setDays] = useState(90);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Latest>("/api/metrics/latest").then(setLatest).catch((e) => setError(e.message));
    api<Goal[]>("/api/goals").then(setGoals).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  useEffect(() => {
    api<{ measured_at: string; value: number }[]>(
      `/api/metrics/${selected}?days=${days}`
    )
      .then(setSeries)
      .catch(() => setSeries([]));
  }, [selected, days]);

  const meta = METRIC_META[selected];
  const goalForSelected = goals.find(
    (g) => g.kind === "body_metric" && g.target.metric === selected
  );

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Hälsa</h1>
        <button
          onClick={() => setShowManual(true)}
          className="text-sm text-emerald-600 dark:text-emerald-400"
        >
          + Mätning
        </button>
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="grid grid-cols-3 gap-2">
        {Object.entries(METRIC_META).map(([key, m]) => {
          const v = latest[key];
          return (
            <button
              key={key}
              onClick={() => setSelected(key)}
              className={`rounded-xl border p-2.5 text-left ${
                selected === key
                  ? "border-emerald-400 bg-emerald-50 dark:border-emerald-600 dark:bg-emerald-950"
                  : "border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900"
              }`}
            >
              <p className="truncate text-[10px] font-medium uppercase tracking-wide text-stone-400">
                {m.label}
              </p>
              <p className="text-sm font-bold">
                {v ? v.value.toFixed(m.decimals) : "–"}
                <span className="ml-0.5 text-[10px] font-normal text-stone-400">
                  {m.unit}
                </span>
              </p>
            </button>
          );
        })}
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-bold">{meta?.label}</h2>
          <div className="flex gap-1">
            {[30, 90, 365].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`rounded-lg px-2 py-1 text-xs font-medium ${
                  days === d
                    ? "bg-emerald-600 text-white"
                    : "bg-stone-100 text-stone-500 dark:bg-stone-800"
                }`}
              >
                {d === 365 ? "1 år" : `${d} d`}
              </button>
            ))}
          </div>
        </div>
        <LineChart
          data={series}
          unit={meta?.unit}
          goalValue={
            goalForSelected ? Number(goalForSelected.target.value) : null
          }
        />
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-400">
            Mål
          </h3>
          <button
            onClick={() => setShowGoalForm(true)}
            className="text-sm text-emerald-600 dark:text-emerald-400"
          >
            + Nytt mål
          </button>
        </div>
        {goals.length === 0 && (
          <p className="rounded-xl border border-dashed border-stone-300 p-4 text-center text-sm text-stone-400 dark:border-stone-700">
            Inga mål ännu — t.ex. &quot;10 km på 45 min&quot; eller &quot;11 %
            kroppsfett&quot;.
          </p>
        )}
        <ul className="space-y-2">
          {goals.map((g) => (
            <li
              key={g.id}
              className="rounded-xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900"
            >
              <div className="flex items-center justify-between">
                <p className="font-semibold">
                  {g.achieved_at ? "🏆 " : ""}
                  {g.title}
                </p>
                <button
                  onClick={async () => {
                    await api(`/api/goals/${g.id}`, { method: "DELETE" });
                    refresh();
                  }}
                  className="px-1 text-stone-400"
                >
                  ✕
                </button>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
                <div
                  className={`h-full ${g.achieved_at ? "bg-emerald-500" : "bg-emerald-500"}`}
                  style={{ width: `${Math.round(g.progress * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">
                {Math.round(g.progress * 100)} %
                {g.kind === "body_metric" &&
                  g.current.current_value != null &&
                  ` · nu ${g.current.current_value}`}
                {g.kind === "pace_distance" &&
                  g.current.best_time_s != null &&
                  ` · bästa ${formatTime(Number(g.current.best_time_s))}`}
                {g.kind === "frequency" &&
                  g.current.sessions_this_week != null &&
                  ` · ${g.current.sessions_this_week} pass denna vecka`}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {showGoalForm && (
        <GoalForm
          latest={latest}
          onClose={() => setShowGoalForm(false)}
          onSaved={() => {
            setShowGoalForm(false);
            refresh();
          }}
          onError={setError}
        />
      )}
      {showManual && (
        <ManualMetricForm
          onClose={() => setShowManual(false)}
          onSaved={() => {
            setShowManual(false);
            refresh();
          }}
        />
      )}
    </main>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function Sheet({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-white p-5 dark:bg-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="p-1 text-stone-400">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function GoalForm({
  latest,
  onClose,
  onSaved,
  onError,
}: {
  latest: Latest;
  onClose: () => void;
  onSaved: () => void;
  onError: (m: string) => void;
}) {
  const [kind, setKind] = useState<"body_metric" | "pace_distance" | "frequency">(
    "body_metric"
  );
  const [metric, setMetric] = useState("fat_percent");
  const [value, setValue] = useState("");
  const [distanceKm, setDistanceKm] = useState("10");
  const [minutes, setMinutes] = useState("45");
  const [perWeek, setPerWeek] = useState("4");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      let body: Record<string, unknown>;
      if (kind === "body_metric") {
        const label = METRIC_META[metric]?.label ?? metric;
        body = {
          kind,
          title: `${label} till ${value} ${METRIC_META[metric]?.unit ?? ""}`.trim(),
          target: { metric, value: Number(value) },
        };
      } else if (kind === "pace_distance") {
        body = {
          kind,
          title: `${distanceKm} km på ${minutes} min`,
          target: {
            distance_m: Number(distanceKm) * 1000,
            time_s: Number(minutes) * 60,
          },
        };
      } else {
        body = {
          kind,
          title: `${perWeek} pass i veckan`,
          target: { sessions_per_week: Number(perWeek) },
        };
      }
      await api("/api/goals", { method: "POST", body: JSON.stringify(body) });
      onSaved();
    } catch (e) {
      onError((e as Error).message);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-stone-300 bg-transparent px-4 py-2.5 dark:border-stone-700";

  return (
    <Sheet title="Nytt mål" onClose={onClose}>
      <div className="mb-3 flex gap-1.5">
        {(
          [
            ["body_metric", "Kroppsmått"],
            ["pace_distance", "Löpning"],
            ["frequency", "Frekvens"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setKind(k)}
            className={`flex-1 rounded-lg py-2 text-xs font-semibold ${
              kind === k
                ? "bg-emerald-600 text-white"
                : "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {kind === "body_metric" && (
        <div className="space-y-3">
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className={inputCls}
          >
            {Object.entries(METRIC_META).map(([key, m]) => (
              <option key={key} value={key}>
                {m.label}
                {latest[key] ? ` (nu ${latest[key].value})` : ""}
              </option>
            ))}
          </select>
          <input
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={`Målvärde (${METRIC_META[metric]?.unit})`}
            className={inputCls}
          />
        </div>
      )}
      {kind === "pace_distance" && (
        <div className="flex gap-2">
          <label className="flex-1">
            <span className="text-xs text-stone-400">Distans (km)</span>
            <input
              inputMode="decimal"
              value={distanceKm}
              onChange={(e) => setDistanceKm(e.target.value)}
              className={inputCls}
            />
          </label>
          <label className="flex-1">
            <span className="text-xs text-stone-400">Tid (minuter)</span>
            <input
              inputMode="numeric"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              className={inputCls}
            />
          </label>
        </div>
      )}
      {kind === "frequency" && (
        <label className="block">
          <span className="text-xs text-stone-400">Pass per vecka</span>
          <input
            inputMode="numeric"
            value={perWeek}
            onChange={(e) => setPerWeek(e.target.value)}
            className={inputCls}
          />
        </label>
      )}

      <button
        disabled={saving || (kind === "body_metric" && !value)}
        onClick={save}
        className="mt-4 w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white disabled:opacity-40"
      >
        Skapa mål
      </button>
    </Sheet>
  );
}

function ManualMetricForm({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [metric, setMetric] = useState("weight");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api("/api/metrics", {
        method: "POST",
        body: JSON.stringify({ metric, value: Number(value) }),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet title="Logga mätning" onClose={onClose}>
      <div className="space-y-3">
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="w-full rounded-xl border border-stone-300 bg-transparent px-4 py-2.5 dark:border-stone-700"
        >
          {Object.entries(METRIC_META).map(([key, m]) => (
            <option key={key} value={key}>
              {m.label} ({m.unit})
            </option>
          ))}
        </select>
        <input
          autoFocus
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Värde"
          className="w-full rounded-xl border border-stone-300 bg-transparent px-4 py-2.5 dark:border-stone-700"
        />
        <button
          disabled={saving || !value}
          onClick={save}
          className="w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white disabled:opacity-40"
        >
          Spara
        </button>
      </div>
    </Sheet>
  );
}
