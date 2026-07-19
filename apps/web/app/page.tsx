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

      {me && <OnboardingCard hasProgram={!!active} />}

      {me && <ChallengePulse />}

      {me && <CalorieCard day={day} isToday={isToday} dayLabel={dayLabel} />}

      {me && <StepsCard day={day} isToday={isToday} />}

      {me && <WaterCard day={day} />}

      {me && <TodayCard day={day} isToday={isToday} dayLabel={dayLabel} />}

      {me && <DashboardSection />}

      {me && <WeeklyReportCard />}

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

type ChallengeSummary = {
  id: string;
  name: string;
  kind: string;
  metric_label: string;
  unit: string;
  days_left: number;
  my_rank: number;
  my_value: number;
  participants: number;
  gap_ahead: { name: string; diff: number } | null;
  gap_behind: { name: string; diff: number } | null;
  habit?: { completed: number; total: number; per_week: number };
};

/** Pågående utmaningar — placering och gapet till nästa. Dagens driv! */
function ChallengePulse() {
  const [items, setItems] = useState<ChallengeSummary[]>([]);

  useEffect(() => {
    api<ChallengeSummary[]>("/api/social/challenges/active-summary")
      .then(setItems)
      .catch(() => {});
  }, []);

  if (items.length === 0) return null;

  const fmt = (n: number) =>
    Math.abs(n) >= 1000
      ? Math.round(n).toLocaleString("sv-SE")
      : String(Math.round(n * 10) / 10);

  return (
    <a
      href="/social"
      className="block rounded-2xl border-2 border-navy-line bg-navy-soft p-4 dark:border-night-strong dark:bg-night-shell"
    >
      {items.map((c, i) => (
        <div key={c.id} className={i > 0 ? "mt-3 border-t border-navy-line/50 pt-3 dark:border-night-strong/50" : ""}>
          <div className="flex items-center justify-between">
            <p className="font-bold">🏆 {c.name}</p>
            <span className="shrink-0 text-xs font-semibold text-muted dark:text-faint">
              {c.days_left === 0 ? "🔥 sista dagen!" : `${c.days_left} d kvar`}
            </span>
          </div>
          {c.habit ? (
            <p className="mt-1 text-sm text-navy-deep dark:text-lime">
              ✅ {c.habit.completed} av {c.habit.total} veckor klarade (
              {c.habit.per_week} pass/vecka)
            </p>
          ) : c.my_rank === 1 ? (
            <p className="mt-1 text-sm text-navy-deep dark:text-lime">
              🥇 Du leder med {fmt(c.my_value)} {c.unit}
              {c.gap_behind
                ? ` — ${c.gap_behind.name} är ${fmt(c.gap_behind.diff)} ${c.unit} bakom`
                : ""}
            </p>
          ) : (
            <p className="mt-1 text-sm text-navy-deep dark:text-lime">
              {c.my_rank === 2 ? "🥈" : c.my_rank === 3 ? "🥉" : `${c.my_rank}.`}{" "}
              {c.my_rank}:a av {c.participants}
              {c.gap_ahead
                ? ` — ${fmt(c.gap_ahead.diff)} ${c.unit} från att gå om ${c.gap_ahead.name}!`
                : ""}
            </p>
          )}
        </div>
      ))}
    </a>
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

type WeeklyReport = {
  week: number;
  monday: string;
  sunday: string;
  current: WeekStats;
  previous: WeekStats;
};
type WeekStats = {
  strength_sessions: number;
  cardio_sessions: number;
  cardio_km: number;
  workout_minutes: number;
  steps: number;
  sleep_hours_avg: number | null;
  sleep_score_avg: number | null;
  weight_last: number | null;
  weight_delta: number | null;
  kcal_avg: number | null;
  logged_days: number;
};

/** 📊 Förra veckans facit, jämfört med veckan innan. */
function WeeklyReportCard() {
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api<WeeklyReport>("/api/reports/weekly").then(setReport).catch(() => {});
  }, []);

  if (!report) return null;
  const c = report.current;
  const p = report.previous;
  const totalPass = c.strength_sessions + c.cardio_sessions;
  const prevPass = p.strength_sessions + p.cardio_sessions;
  if (totalPass === 0 && c.steps === 0 && prevPass === 0) return null;

  const arrow = (now: number | null, prev: number | null, invert = false) => {
    if (now == null || prev == null || now === prev) return "→";
    const up = now > prev;
    return (invert ? !up : up) ? "↑" : "↓";
  };
  const fmtN = (n: number) => Math.round(n).toLocaleString("sv-SE");

  const rows: [string, string, string][] = [
    ["🏋️ Pass", `${totalPass}`, arrow(totalPass, prevPass)],
    ["👟 Steg", fmtN(c.steps), arrow(c.steps, p.steps)],
    ...(c.cardio_km > 0 || p.cardio_km > 0
      ? ([["🏃 Distans", `${c.cardio_km} km`, arrow(c.cardio_km, p.cardio_km)]] as [string, string, string][])
      : []),
    ...(c.sleep_hours_avg != null
      ? ([["😴 Sömn/natt", `${c.sleep_hours_avg} h`, arrow(c.sleep_hours_avg, p.sleep_hours_avg)]] as [string, string, string][])
      : []),
    ...(c.weight_delta != null
      ? ([["⚖️ Vikt", `${c.weight_delta > 0 ? "+" : ""}${c.weight_delta} kg`, "→"]] as [string, string, string][])
      : []),
    ...(c.kcal_avg != null
      ? ([["🥗 Kost/dag", `${fmtN(c.kcal_avg)} kcal (${c.logged_days} d)`, "→"]] as [string, string, string][])
      : []),
  ];

  return (
    <section className="rounded-2xl border border-line bg-white p-4 dark:border-night-shell dark:bg-night-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="font-bold">📊 Veckorapport · v.{report.week}</h3>
        <span className="text-sm text-faint">{open ? "▾" : "▸"}</span>
      </button>
      {!open && (
        <p className="mt-0.5 text-sm text-muted dark:text-faint">
          {totalPass} pass · {fmtN(c.steps)} steg
          {c.sleep_hours_avg != null ? ` · sömn ${c.sleep_hours_avg} h` : ""} —
          tryck för detaljer
        </p>
      )}
      {open && (
        <div className="mt-2 space-y-1.5">
          {rows.map(([label, value, dir]) => (
            <div
              key={label}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-muted dark:text-night-muted">{label}</span>
              <span className="font-semibold">
                {value}{" "}
                <span
                  className={
                    dir === "↑"
                      ? "text-lime-deep"
                      : dir === "↓"
                        ? "text-red-500"
                        : "text-faint"
                  }
                >
                  {dir}
                </span>
              </span>
            </div>
          ))}
          <p className="pt-1 text-xs text-faint">
            Pilarna jämför med veckan innan · {report.monday} – {report.sunday}
          </p>
        </div>
      )}
    </section>
  );
}

/** Kom igång-checklista för nya användare — döljs när allt är klart. */
function OnboardingCard({ hasProgram }: { hasProgram: boolean }) {
  const [state, setState] = useState<{
    connected: boolean;
    hasMeals: boolean;
    inChallenge: boolean;
    dismissed: boolean;
  } | null>(null);

  useEffect(() => {
    Promise.all([
      api<{ providers: { connected: boolean }[]; apple_health_tokens: unknown[] }>(
        "/api/integrations"
      ).catch(() => null),
      api<{ kcal: number }[]>("/api/meals/summary?days=60").catch(() => []),
      api<{ is_participant: boolean }[]>("/api/social/challenges").catch(
        () => []
      ),
      api<{ profile?: { onboarding_done?: boolean } }>("/api/me").catch(
        () => null
      ),
    ]).then(([integrations, meals, challenges, meResp]) => {
      setState({
        connected: !!(
          integrations &&
          (integrations.providers.some((p) => p.connected) ||
            integrations.apple_health_tokens.length > 0)
        ),
        hasMeals: (meals ?? []).length > 0,
        inChallenge: (challenges ?? []).some((c) => c.is_participant),
        dismissed: meResp?.profile?.onboarding_done === true,
      });
    });
  }, []);

  if (!state || state.dismissed) return null;
  const steps: [boolean, string, string][] = [
    [state.connected, "Koppla Withings, Strava eller Apple Health", "/settings"],
    [hasProgram, "Välj ett träningsprogram", "/programs"],
    [state.hasMeals, "Logga din första måltid", "/food"],
    [state.inChallenge, "Gå med i en utmaning", "/social"],
  ];
  const doneCount = steps.filter(([done]) => done).length;
  if (doneCount === steps.length) return null;

  async function dismiss() {
    setState((s) => (s ? { ...s, dismissed: true } : s));
    api("/api/me", {
      method: "PATCH",
      body: JSON.stringify({ profile: { onboarding_done: true } }),
    }).catch(() => {});
  }

  return (
    <section className="rounded-2xl border-2 border-sand-strong bg-sand p-4 dark:border-night-strong dark:bg-night-shell">
      <div className="flex items-center justify-between">
        <h3 className="font-bold">👋 Kom igång ({doneCount}/{steps.length})</h3>
        <button onClick={dismiss} className="p-1 text-xs text-faint">
          Dölj ✕
        </button>
      </div>
      <ul className="mt-2 space-y-1.5">
        {steps.map(([done, label, href]) => (
          <li key={label}>
            <a
              href={href}
              className={`flex items-center gap-2 text-sm ${
                done
                  ? "text-faint line-through"
                  : "font-medium text-sand-ink dark:text-lime"
              }`}
            >
              <span>{done ? "✅" : "⬜"}</span>
              {label}
              {!done && <span className="ml-auto">›</span>}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

const WATER_GOAL_ML = 2000;
const GLASS_ML = 250;

/** 💧 Vattenintag — en rad per dag som räknas upp glas för glas. */
function WaterCard({ day }: { day: string }) {
  const [ml, setMl] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<MetricPoint[]>(`/api/metrics/water_ml?start=${day}&end=${day}`)
      .then((points) => setMl(points.length ? points[points.length - 1].value : 0))
      .catch(() => setMl(0));
  }, [day]);

  if (ml === null) return null;

  async function add(amount: number) {
    const next = Math.max((ml ?? 0) + amount, 0);
    setSaving(true);
    setMl(next);
    try {
      await api("/api/metrics", {
        method: "POST",
        body: JSON.stringify({
          metric: "water_ml",
          value: next,
          // Dagstämplad → samma rad uppdateras hela dagen
          measured_at: `${day}T00:00:00Z`,
        }),
      });
    } catch {
      setMl(ml);
    } finally {
      setSaving(false);
    }
  }

  const glasses = Math.round((ml / GLASS_ML) * 10) / 10;
  const pct = Math.min(ml / WATER_GOAL_ML, 1);

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card dark:border-night-shell dark:bg-night-card">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-faint">
            💧 Vatten
          </p>
          <p className="text-2xl font-bold tabular-nums">
            {(ml / 1000).toLocaleString("sv-SE", {
              maximumFractionDigits: 2,
            })}{" "}
            <span className="text-base font-semibold text-muted dark:text-faint">
              / 2 l
            </span>
          </p>
          <p className="text-xs text-muted dark:text-faint">
            {glasses.toLocaleString("sv-SE")} glas
          </p>
        </div>
        <div className="flex gap-1.5">
          <button
            disabled={saving || ml <= 0}
            onClick={() => add(-GLASS_ML)}
            className="h-11 w-11 rounded-xl bg-shell text-lg font-bold disabled:opacity-30 dark:bg-night-shell"
            aria-label="Ta bort ett glas"
          >
            −
          </button>
          <button
            disabled={saving}
            onClick={() => add(GLASS_ML)}
            className="h-11 rounded-xl bg-navy px-4 text-sm font-bold text-white disabled:opacity-50"
          >
            + 1 glas
          </button>
        </div>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-shell dark:bg-night-shell">
        <div
          className="h-2 rounded-full bg-navy transition-all"
          style={{ width: `${pct * 100}%`, background: pct >= 1 ? "#7fc22b" : undefined }}
        />
      </div>
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
