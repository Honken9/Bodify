"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, formatDate } from "./lib/api";
import { sourceLabel } from "./lib/sources";
import type { Me, SessionSummary, UserProgram } from "./lib/types";

function isoDay(d: Date): string {
  return d.toLocaleDateString("sv-SE");
}

export default function Home() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [active, setActive] = useState<UserProgram | null>(null);
  const [recent, setRecent] = useState<SessionSummary[]>([]);
  const [dayOffset, setDayOffset] = useState(0); // 0 = idag, -1 = igår …
  const [error, setError] = useState<string | null>(null);

  const selectedDay = new Date();
  selectedDay.setDate(selectedDay.getDate() + dayOffset);
  const day = isoDay(selectedDay);
  const isToday = dayOffset === 0;
  const dayLabel =
    dayOffset === 0
      ? "Idag"
      : dayOffset === -1
        ? "Igår"
        : dayOffset === -2
          ? "I förrgår"
          : new Intl.DateTimeFormat("sv-SE", {
              weekday: "long",
              day: "numeric",
              month: "long",
            }).format(selectedDay);

  useEffect(() => {
    Promise.all([
      api<Me>("/api/me"),
      api<UserProgram | null>("/api/user-programs/active"),
      api<SessionSummary[]>("/api/sessions?limit=5"),
    ])
      .then(([me, active, recent]) => {
        setMe(me);
        setActive(active);
        setRecent(recent);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const ongoing = recent.find((s) => s.finished_at === null);
  const nextDay = active
    ? active.program.days[active.next_day_position % active.program.days.length]
    : null;

  if (error) {
    return (
      <main className="mx-auto max-w-md p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl desktop:grid desktop:grid-cols-2 desktop:items-start gap-5 p-5">
      <header className="desktop:col-span-2">
        <h1 className="text-[22px] font-bold tracking-tight">
          {me ? `Hej ${me.display_name ?? me.email.split("@")[0]}! 👋` : "…"}
        </h1>
        <p className="text-sm text-muted dark:text-faint">
          Redo för dagens pass?
        </p>
      </header>

      {/* Dagbläddring — jämför idag med igår, förrgår osv. */}
      {me && (
        <div className="flex items-center justify-between rounded-xl bg-cream-deep px-1 py-1 dark:bg-night-shell/60 desktop:col-span-2">
          <button
            onClick={() => setDayOffset((o) => o - 1)}
            className="px-4 py-1 text-lg leading-none"
            aria-label="Föregående dag"
          >
            ‹
          </button>
          <span className="text-sm font-semibold capitalize">
            {dayLabel}
            {!isToday && (
              <button
                onClick={() => setDayOffset(0)}
                className="ml-2 rounded-full bg-shell px-2 py-0.5 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
              >
                Idag
              </button>
            )}
          </span>
          <button
            onClick={() => setDayOffset((o) => Math.min(0, o + 1))}
            disabled={isToday}
            className="px-4 py-1 text-lg leading-none disabled:opacity-30"
            aria-label="Nästa dag"
          >
            ›
          </button>
        </div>
      )}

      {me && <CalorieCard day={day} isToday={isToday} dayLabel={dayLabel} />}

      {me && <StepsCard day={day} isToday={isToday} />}

      {me && <TodayCard day={day} isToday={isToday} dayLabel={dayLabel} />}

      {me && <DashboardSection />}

      {nextDay && !ongoing && (
        <button
          onClick={() => router.push("/programs")}
          className="flex items-center justify-between rounded-2xl border border-line bg-white px-5 py-4 text-left shadow-card dark:border-night-shell dark:bg-night-card"
        >
          <span>
            <p className="text-xs font-semibold uppercase tracking-wide text-faint">
              Nästa pass · {active!.program.name}
            </p>
            <p className="mt-0.5 font-bold">{nextDay.name}</p>
          </span>
          <span className="text-faint">›</span>
        </button>
      )}

      {me && <ReadinessCard />}

      {recent.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-faint">
            Senaste passen
          </h3>
          <ul className="space-y-2">
            {recent.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between rounded-xl border border-line bg-white px-4 py-3 text-sm dark:border-night-shell dark:bg-night-card"
              >
                <span className="font-medium">
                  {s.day_name ?? "Fritt pass"}
                </span>
                <span className="text-muted dark:text-faint">
                  {formatDate(s.started_at)} · {s.set_count} set
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {me && (
        <div className="flex flex-col gap-2">
          <a
            href="/social"
            className="rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium dark:border-night-shell dark:bg-night-card"
          >
            🏆 Vänner & utmaningar ›
          </a>
          <a
            href="/photos"
            className="rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium dark:border-night-shell dark:bg-night-card"
          >
            📸 Progressfoton — jämför före & efter ›
          </a>
          {me.is_admin && (
            <a
              href="/admin"
              className="rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium dark:border-night-shell dark:bg-night-card"
            >
              🛠️ Admin ›
            </a>
          )}
        </div>
      )}
    </main>
  );
}

type MetricPoint = { measured_at: string; value: number; source: string };

function StepsCard({ day, isToday }: { day: string; isToday: boolean }) {
  const [days, setDays] = useState<
    { day: string; steps: number; source: string }[] | null
  >(null);

  useEffect(() => {
    // Fönster: 7 dagar som slutar på vald dag
    const end = new Date(day);
    const start = new Date(day);
    start.setDate(start.getDate() - 6);
    api<MetricPoint[]>(
      `/api/metrics/steps?start=${isoDay(start)}&end=${isoDay(end)}`
    )
      .then((points) => {
        // En stapel per dag — högsta värdet vinner om flera källor rapporterar
        const byDay = new Map<string, { steps: number; source: string }>();
        for (const p of points) {
          const key = p.measured_at.slice(0, 10);
          const prev = byDay.get(key);
          if (!prev || p.value > prev.steps) {
            byDay.set(key, { steps: p.value, source: p.source });
          }
        }
        const result: { day: string; steps: number; source: string }[] = [];
        for (let i = 6; i >= 0; i--) {
          const d = new Date(day);
          d.setDate(d.getDate() - i);
          const key = isoDay(d);
          const best = byDay.get(key);
          result.push({
            day: key,
            steps: best?.steps ?? 0,
            source: best?.source ?? "",
          });
        }
        setDays(result);
      })
      .catch(() => {});
  }, [day]);

  if (!days) return null;
  const today = days[days.length - 1];
  const max = Math.max(...days.map((d) => d.steps), 1);
  const weekdays = ["sön", "mån", "tis", "ons", "tor", "fre", "lör"];

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card dark:border-night-shell dark:bg-night-card">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-faint">
            👟 Steg
          </p>
          <p className="text-3xl font-bold tabular-nums">
            {today.steps > 0
              ? Math.round(today.steps).toLocaleString("sv-SE")
              : "—"}
          </p>
          {today.steps > 0 && today.source && (
            <p className="text-[10px] text-faint">
              via {sourceLabel(today.source)}
            </p>
          )}
        </div>
        <div className="flex items-end gap-1.5">
          {days.map((d, i) => (
            <div key={d.day} className="flex flex-col items-center gap-0.5">
              <div
                title={`${d.day}: ${Math.round(d.steps).toLocaleString("sv-SE")} steg`}
                className={`w-5 rounded-sm ${
                  i === days.length - 1
                    ? "bg-lime"
                    : "bg-shell dark:bg-night-shell"
                }`}
                style={{
                  height: `${Math.max(6, Math.round((d.steps / max) * 48))}px`,
                }}
              />
              <span className="text-[9px] text-faint">
                {weekdays[new Date(d.day).getDay()]}
              </span>
            </div>
          ))}
        </div>
      </div>
      {today.steps === 0 && (
        <p className="mt-2 text-xs text-faint">
          {isToday
            ? "Inga steg registrerade idag ännu — synkas från Withings/Apple Health."
            : "Inga steg registrerade den här dagen."}
        </p>
      )}
    </section>
  );
}

type DayLogLite = {
  totals: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
  targets: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
};

/** Kaloriräknaren — appens nav: ätit, målet och vad som är kvar. */
function CalorieCard({
  day,
  isToday,
  dayLabel,
}: {
  day: string;
  isToday: boolean;
  dayLabel: string;
}) {
  const [log, setLog] = useState<DayLogLite | null>(null);
  const [editing, setEditing] = useState(false);
  const [goal, setGoal] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    () =>
      api<DayLogLite>(`/api/meals?day=${day}`)
        .then(setLog)
        .catch(() => {}),
    [day]
  );
  useEffect(() => {
    load();
  }, [load]);

  if (!log) return null;
  const eaten = Math.round(log.totals.kcal);
  const target = log.targets.kcal;
  const left = target - eaten;
  const over = left < 0;
  const pct = Math.min(eaten / Math.max(target, 1), 1);

  // Ring: 2πr med r=44
  const CIRC = 2 * Math.PI * 44;

  async function saveGoal() {
    const kcal = parseInt(goal, 10);
    if (!kcal || kcal < 500 || kcal > 10000 || !log) return;
    setSaving(true);
    try {
      await api("/api/nutrition-targets", {
        method: "PUT",
        body: JSON.stringify({ ...log.targets, kcal }),
      });
      setEditing(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border-2 border-navy-line bg-white p-4 shadow-card dark:border-night-strong dark:bg-night-card">
      <div className="flex items-center gap-4">
        <div className="relative h-28 w-28 shrink-0">
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              strokeWidth="10"
              className="stroke-shell dark:stroke-night-shell"
            />
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              strokeWidth="10"
              strokeLinecap="round"
              stroke={over ? "#dc2626" : "#7fc22b"}
              strokeDasharray={`${pct * CIRC} ${CIRC}`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span
              className={`text-xl font-bold tabular-nums ${over ? "text-red-600 dark:text-red-400" : ""}`}
            >
              {Math.abs(left).toLocaleString("sv-SE")}
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-faint">
              {over ? "över målet" : isToday ? "kcal kvar" : "under målet"}
            </span>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-faint">
            🔥 Kalorier · {dayLabel}
          </p>
          <p className="text-2xl font-bold tabular-nums">
            {eaten.toLocaleString("sv-SE")}
            <span className="text-base font-semibold text-muted dark:text-faint">
              {" "}
              / {target.toLocaleString("sv-SE")}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-muted dark:text-faint">
            {Math.round(log.totals.protein_g)} g protein ·{" "}
            {Math.round(log.totals.carbs_g)} g kolh ·{" "}
            {Math.round(log.totals.fat_g)} g fett
          </p>
          <div className="mt-2 flex gap-2">
            <a
              href="/food"
              className="rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white"
            >
              + Logga måltid
            </a>
            <button
              onClick={() => {
                setGoal(String(target));
                setEditing((v) => !v);
              }}
              className="rounded-lg bg-shell px-3 py-1.5 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
            >
              🎯 Ändra mål
            </button>
          </div>
        </div>
      </div>

      {editing && (
        <div className="mt-3 flex items-center gap-2 border-t border-line pt-3 dark:border-night-shell">
          <input
            type="number"
            inputMode="numeric"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            className="w-28 rounded-xl border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong"
            placeholder="kcal/dag"
          />
          <span className="text-xs text-faint">kcal per dag</span>
          <button
            onClick={saveGoal}
            disabled={saving}
            className="ml-auto rounded-lg bg-navy px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            {saving ? "Sparar…" : "Spara mål"}
          </button>
        </div>
      )}
    </section>
  );
}

type LatestMetrics = Record<
  string,
  { value: number; measured_at: string; source: string }
>;

/** Dagens kropp i korthet: puls, sömn och kondition — för vald dag. */
function TodayCard({
  day,
  isToday,
  dayLabel,
}: {
  day: string;
  isToday: boolean;
  dayLabel: string;
}) {
  const [data, setData] = useState<LatestMetrics | null>(null);
  const [latest, setLatest] = useState<LatestMetrics | null>(null);

  useEffect(() => {
    api<LatestMetrics>(`/api/metrics/day?day=${day}`)
      .then(setData)
      .catch(() => {});
  }, [day]);
  useEffect(() => {
    // VO2max mäts glest — visa senaste kända värdet oavsett dag
    api<LatestMetrics>("/api/metrics/latest").then(setLatest).catch(() => {});
  }, []);

  if (!data) return null;
  const hr = (k: string) => (data[k] ? String(Math.round(data[k].value)) : "–");
  const srcSub = (k: string, base: string) =>
    data[k] ? `${base} · ${sourceLabel(data[k].source)}` : base;

  const sleep = data["sleep_duration"];
  const sleepText = sleep
    ? `${Math.floor(sleep.value)} h ${Math.round((sleep.value % 1) * 60)} min`
    : "–";
  const score = data["sleep_score"];
  const vo2 = latest?.["vo2max"];

  const hasAnything = !!(data["hr_avg"] || data["hr_max"] || sleep || vo2);
  if (isToday && !hasAnything) return null;

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card dark:border-night-shell dark:bg-night-card">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold capitalize">{dayLabel}</h3>
        <a href="/health" className="text-xs text-navy dark:text-lime">
          Hälsa ›
        </a>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Stat
          label="❤️ Snittpuls"
          value={hr("hr_avg")}
          sub={srcSub("hr_avg", "bpm")}
        />
        <Stat
          label="🔺 Maxpuls"
          value={hr("hr_max")}
          sub={srcSub("hr_max", "bpm")}
        />
        <Stat
          label="🔻 Lägsta"
          value={hr("hr_min")}
          sub={srcSub("hr_min", "bpm")}
        />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Stat
          label={isToday ? "😴 Sömn i natt" : "😴 Sömn den natten"}
          value={sleepText}
          sub={
            (sleep && score
              ? `sömnpoäng ${Math.round(score.value)}/100`
              : "natten till denna dag") +
            (sleep ? ` · ${sourceLabel(sleep.source)}` : "")
          }
        />
        <Stat
          label="🫁 Kondition"
          value={vo2 ? vo2.value.toFixed(1) : "–"}
          sub={
            vo2
              ? `VO₂max · ${formatDate(vo2.measured_at)} · ${sourceLabel(vo2.source)}`
              : "VO₂max saknas ännu"
          }
        />
      </div>
    </section>
  );
}

type Readiness = {
  status: "green" | "yellow" | "red" | "unknown";
  factors: { name: string; status: string; detail: string }[];
  recommendation: string;
};

const READINESS_STYLE: Record<string, { bg: string; icon: string; label: string }> = {
  green: {
    bg: "border-navy-line bg-navy-soft dark:border-night-strong dark:bg-night-shell",
    icon: "🟢",
    label: "Bra återhämtning",
  },
  yellow: {
    bg: "border-sand-strong bg-sand dark:border-night-strong dark:bg-night-shell",
    icon: "🟡",
    label: "Lite sliten",
  },
  red: {
    bg: "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950",
    icon: "🔴",
    label: "Behöver vila",
  },
};

function ReadinessCard() {
  const [data, setData] = useState<Readiness | null>(null);
  const [showFactors, setShowFactors] = useState(false);

  useEffect(() => {
    api<Readiness>("/api/ai/readiness").then(setData).catch(() => {});
  }, []);

  if (!data || data.status === "unknown") return null;
  const style = READINESS_STYLE[data.status];

  return (
    <section className={`rounded-2xl border-2 p-4 ${style.bg}`}>
      <button
        className="w-full text-left"
        onClick={() => setShowFactors((v) => !v)}
      >
        <p className="font-bold">
          {style.icon} Coachen: {style.label}
        </p>
        <p className="mt-1 text-sm text-muted dark:text-night-muted">
          {data.recommendation}
        </p>
      </button>
      {showFactors && (
        <ul className="mt-2 space-y-0.5 border-t border-black/5 pt-2 text-xs text-muted dark:border-white/10 dark:text-faint">
          {data.factors.map((f) => (
            <li key={f.name}>
              {f.status === "green" ? "🟢" : f.status === "yellow" ? "🟡" : "🔴"}{" "}
              <strong>{f.name}:</strong> {f.detail}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type Dashboard = {
  period: string;
  strength_sessions: number;
  total_volume_kg: number;
  cardio_sessions: number;
  cardio_distance_km: number;
  avg_kcal: number | null;
  avg_protein_g: number | null;
  logged_days: number;
  weight_delta_kg: number | null;
  active_days: number;
  activity: { day: string; strength: boolean; cardio: boolean }[];
};

const PERIOD_LABELS = { week: "Vecka", month: "Månad", year: "År" } as const;

function DashboardSection() {
  const [period, setPeriod] = useState<keyof typeof PERIOD_LABELS>("week");
  const [dash, setDash] = useState<Dashboard | null>(null);

  useEffect(() => {
    api<Dashboard>(`/api/dashboard?period=${period}`)
      .then(setDash)
      .catch(() => {});
  }, [period]);

  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
      <div className="flex items-center justify-between">
        <h3 className="font-bold">Din översikt</h3>
        <div className="flex gap-1">
          {(Object.keys(PERIOD_LABELS) as (keyof typeof PERIOD_LABELS)[]).map(
            (p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  period === p
                    ? "bg-navy text-white"
                    : "bg-shell text-muted dark:bg-night-shell"
                }`}
              >
                {PERIOD_LABELS[p]}
              </button>
            )
          )}
        </div>
      </div>

      {dash && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 desktop:grid-cols-4">
            <Stat
              label="Styrkepass"
              value={String(dash.strength_sessions)}
              sub={`${Math.round(dash.total_volume_kg / 1000)} ton volym`}
            />
            <Stat
              label="Konditionspass"
              value={String(dash.cardio_sessions)}
              sub={`${dash.cardio_distance_km} km`}
            />
            <Stat
              label="Kost (snitt/dag)"
              value={dash.avg_kcal != null ? `${dash.avg_kcal} kcal` : "–"}
              sub={
                dash.avg_protein_g != null
                  ? `${dash.avg_protein_g} g protein · ${dash.logged_days} loggade dagar`
                  : "inga loggade dagar"
              }
            />
            <Stat
              label="Vikt"
              value={
                dash.weight_delta_kg != null
                  ? `${dash.weight_delta_kg > 0 ? "+" : ""}${dash.weight_delta_kg} kg`
                  : "–"
              }
              sub={`${dash.active_days} aktiva dagar`}
            />
          </div>

          {dash.activity.length > 0 && (
            <div className="mt-3 flex gap-[3px]">
              {dash.activity.map((d) => (
                <div
                  key={d.day}
                  title={d.day}
                  className={`h-6 flex-1 rounded-sm ${
                    d.strength && d.cardio
                      ? "bg-navy-deep"
                      : d.strength
                        ? "bg-navy"
                        : d.cardio
                          ? "bg-sand-strong"
                          : "bg-shell dark:bg-night-shell"
                  }`}
                />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl bg-cream-deep p-3 dark:bg-night-shell/60">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
        {label}
      </p>
      <p className="text-lg font-bold">{value}</p>
      <p className="truncate text-xs text-muted dark:text-faint">{sub}</p>
    </div>
  );
}
