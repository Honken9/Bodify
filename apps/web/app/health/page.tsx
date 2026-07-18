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

type View = "day" | "week" | "month" | "year";

const VIEW_LABELS: Record<View, string> = {
  day: "Dag",
  week: "Vecka",
  month: "Månad",
  year: "År",
};

function isoDay(d: Date): string {
  return d.toLocaleDateString("sv-SE");
}

/** Fönstrets [start, slut] (inklusive) för en vy runt ett ankardatum. */
function windowFor(view: View, anchor: Date): [Date, Date] {
  const a = new Date(anchor);
  if (view === "day") return [a, a];
  if (view === "week") {
    const start = new Date(a);
    start.setDate(a.getDate() - ((a.getDay() + 6) % 7)); // måndag
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return [start, end];
  }
  if (view === "month")
    return [
      new Date(a.getFullYear(), a.getMonth(), 1),
      new Date(a.getFullYear(), a.getMonth() + 1, 0),
    ];
  return [new Date(a.getFullYear(), 0, 1), new Date(a.getFullYear(), 11, 31)];
}

function shiftAnchor(view: View, anchor: Date, delta: number): Date {
  const a = new Date(anchor);
  if (view === "day") a.setDate(a.getDate() + delta);
  else if (view === "week") a.setDate(a.getDate() + delta * 7);
  else if (view === "month") a.setMonth(a.getMonth() + delta);
  else a.setFullYear(a.getFullYear() + delta);
  return a;
}

function windowLabel(view: View, start: Date, end: Date): string {
  const today = isoDay(new Date());
  if (view === "day") {
    if (isoDay(start) === today) return "Idag";
    return new Intl.DateTimeFormat("sv-SE", {
      weekday: "long",
      day: "numeric",
      month: "short",
    }).format(start);
  }
  if (view === "week") {
    const fmt = (d: Date) =>
      new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "short" }).format(d);
    return `${fmt(start)} – ${fmt(end)}`;
  }
  if (view === "month")
    return new Intl.DateTimeFormat("sv-SE", {
      month: "long",
      year: "numeric",
    }).format(start);
  return String(start.getFullYear());
}

export default function HealthPage() {
  const [latest, setLatest] = useState<Latest>({});
  const [selected, setSelected] = useState("weight");
  const [series, setSeries] = useState<
    { measured_at: string; value: number; source?: string }[]
  >([]);
  const [view, setView] = useState<View>("month");
  const [anchor, setAnchor] = useState(() => new Date());
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Latest>("/api/metrics/latest").then(setLatest).catch((e) => setError(e.message));
    api<Goal[]>("/api/goals").then(setGoals).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  const [winStart, winEnd] = windowFor(view, anchor);

  useEffect(() => {
    api<{ measured_at: string; value: number; source?: string }[]>(
      `/api/metrics/${selected}?start=${isoDay(winStart)}&end=${isoDay(winEnd)}`
    )
      .then(setSeries)
      .catch(() => setSeries([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, view, anchor]);

  const meta = METRIC_META[selected];
  const atPresent = winEnd >= new Date(new Date().setHours(0, 0, 0, 0));

  // Sammanfattning för fönstret — steg summeras, övrigt visar snitt/min/max
  const values = series.map((p) => p.value);
  const mean =
    values.length > 0
      ? values.reduce((a, b) => a + b, 0) / values.length
      : null;
  const summary =
    values.length === 0
      ? null
      : selected === "steps"
        ? `Totalt ${Math.round(values.reduce((a, b) => a + b, 0)).toLocaleString("sv-SE")} · snitt ${Math.round(
            values.reduce((a, b) => a + b, 0) / values.length
          ).toLocaleString("sv-SE")}/dag`
        : `Snitt ${(values.reduce((a, b) => a + b, 0) / values.length).toFixed(
            meta?.decimals ?? 1
          )} · lägst ${Math.min(...values).toFixed(meta?.decimals ?? 1)} · högst ${Math.max(
            ...values
          ).toFixed(meta?.decimals ?? 1)} ${meta?.unit ?? ""}`;
  const goalForSelected = goals.find(
    (g) => g.kind === "body_metric" && g.target.metric === selected
  );

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Hälsa</h1>
        <button
          onClick={() => setShowManual(true)}
          className="text-sm text-navy dark:text-lime"
        >
          + Mätning
        </button>
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="grid grid-cols-3 gap-2 desktop:grid-cols-5">
        {Object.entries(METRIC_META).map(([key, m]) => {
          const v = latest[key];
          return (
            <button
              key={key}
              onClick={() => setSelected(key)}
              className={`rounded-xl border p-2.5 text-left ${
                selected === key
                  ? "border-navy bg-navy-soft dark:border-lime dark:bg-night-shell"
                  : "border-line bg-white dark:border-night-shell dark:bg-night-card"
              }`}
            >
              <p className="truncate text-[10px] font-medium uppercase tracking-wide text-faint">
                {m.label}
              </p>
              <p className="text-sm font-bold">
                {v ? v.value.toFixed(m.decimals) : "–"}
                <span className="ml-0.5 text-[10px] font-normal text-faint">
                  {m.unit}
                </span>
              </p>
            </button>
          );
        })}
      </div>

      <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-bold">
            {meta?.label}
            <button
              onClick={() => setExpanded(true)}
              className="ml-2 align-middle text-sm text-faint"
              aria-label="Förstora grafen"
              title="Förstora grafen"
            >
              ⤢
            </button>
          </h2>
          <div className="flex gap-1">
            {(Object.keys(VIEW_LABELS) as View[]).map((v) => (
              <button
                key={v}
                onClick={() => {
                  setView(v);
                  setAnchor(new Date());
                }}
                className={`rounded-lg px-2 py-1 text-xs font-medium ${
                  view === v
                    ? "bg-navy text-white"
                    : "bg-shell text-muted dark:bg-night-shell"
                }`}
              >
                {VIEW_LABELS[v]}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-2 flex items-center justify-between rounded-xl bg-cream-deep px-1 py-0.5 dark:bg-night-shell/60">
          <button
            onClick={() => setAnchor(shiftAnchor(view, anchor, -1))}
            className="px-3 py-1.5 text-lg leading-none"
            aria-label="Föregående period"
          >
            ‹
          </button>
          <span className="text-sm font-semibold first-letter:uppercase">
            {windowLabel(view, winStart, winEnd)}
          </span>
          <button
            onClick={() => setAnchor(shiftAnchor(view, anchor, 1))}
            disabled={atPresent}
            className="px-3 py-1.5 text-lg leading-none disabled:opacity-30"
            aria-label="Nästa period"
          >
            ›
          </button>
        </div>

        {view === "day" && series.length > 0 ? (
          <ul className="divide-y divide-line text-sm dark:divide-night-shell">
            {series.map((p, i) => (
              <li key={i} className="flex items-center justify-between py-2">
                <span className="text-muted dark:text-night-muted">
                  {new Date(p.measured_at).toLocaleTimeString("sv-SE", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                  {p.source ? ` · ${p.source}` : ""}
                </span>
                <span className="font-semibold tabular-nums">
                  {p.value.toFixed(meta?.decimals ?? 1)} {meta?.unit}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <LineChart
            data={series}
            unit={meta?.unit}
            bars={selected === "steps"}
            decimals={meta?.decimals ?? 1}
            meanValue={mean}
            goalValue={
              goalForSelected ? Number(goalForSelected.target.value) : null
            }
          />
        )}

        {series.length === 0 && view === "day" && (
          <p className="py-4 text-center text-sm text-faint">
            Inga mätningar den här dagen.
          </p>
        )}
        {summary && (
          <p className="mt-2 text-xs text-muted dark:text-faint">{summary}</p>
        )}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-faint">
            Mål
          </h3>
          <button
            onClick={() => setShowGoalForm(true)}
            className="text-sm text-navy dark:text-lime"
          >
            + Nytt mål
          </button>
        </div>
        {goals.length === 0 && (
          <p className="rounded-xl border border-dashed border-line-strong p-4 text-center text-sm text-faint dark:border-night-strong">
            Inga mål ännu — t.ex. &quot;10 km på 45 min&quot; eller &quot;11 %
            kroppsfett&quot;.
          </p>
        )}
        <ul className="space-y-2">
          {goals.map((g) => (
            <li
              key={g.id}
              className="rounded-xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card"
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
                  className="px-1 text-faint"
                >
                  ✕
                </button>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-shell dark:bg-night-shell">
                <div
                  className={`h-full ${g.achieved_at ? "bg-navy" : "bg-navy"}`}
                  style={{ width: `${Math.round(g.progress * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-muted dark:text-faint">
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

      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3"
          onClick={() => setExpanded(false)}
        >
          <div
            className="w-full max-w-2xl rounded-3xl bg-white p-5 dark:bg-night-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-lg font-bold">
                {meta?.label} · {windowLabel(view, winStart, winEnd)}
              </h3>
              <button onClick={() => setExpanded(false)} className="p-1 text-faint">
                ✕
              </button>
            </div>
            <LineChart
              data={series}
              height={300}
              unit={meta?.unit}
              bars={selected === "steps"}
              decimals={meta?.decimals ?? 1}
              meanValue={mean}
              goalValue={
                goalForSelected ? Number(goalForSelected.target.value) : null
              }
            />
            {summary && (
              <p className="mt-2 text-sm text-muted dark:text-faint">
                {summary} · {series.length} mätningar
              </p>
            )}
          </div>
        </div>
      )}

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
        className="w-full max-w-md rounded-t-3xl bg-white p-5 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="p-1 text-faint">
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
    "w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong";

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
                ? "bg-navy text-white"
                : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
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
            <span className="text-xs text-faint">Distans (km)</span>
            <input
              inputMode="decimal"
              value={distanceKm}
              onChange={(e) => setDistanceKm(e.target.value)}
              className={inputCls}
            />
          </label>
          <label className="flex-1">
            <span className="text-xs text-faint">Tid (minuter)</span>
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
          <span className="text-xs text-faint">Pass per vecka</span>
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
        className="mt-4 w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
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
          className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong"
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
          className="w-full rounded-xl border border-line-strong bg-transparent px-4 py-2.5 dark:border-night-strong"
        />
        <button
          disabled={saving || !value}
          onClick={save}
          className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
        >
          Spara
        </button>
      </div>
    </Sheet>
  );
}
