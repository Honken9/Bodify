"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, formatDate } from "./lib/api";
import type { Me, SessionSummary, UserProgram } from "./lib/types";

export default function Home() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [active, setActive] = useState<UserProgram | null>(null);
  const [recent, setRecent] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

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

      {ongoing && (
        <button
          onClick={() => router.push(`/workout/${ongoing.id}`)}
          className="flex items-center gap-3 rounded-2xl bg-sand p-4 text-left desktop:col-span-2 dark:bg-night-shell"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sand-strong text-[15px] font-bold text-sand-ink">
            ▸
          </span>
          <span className="min-w-0">
            <p className="text-sm font-bold">Pågående pass</p>
            <p className="text-xs text-sand-ink dark:text-lime">
              {ongoing.day_name ?? "Fritt pass"} · {ongoing.set_count} set
              loggade — tryck för att fortsätta
            </p>
          </span>
        </button>
      )}

      {me && <StepsCard />}

      {me && <TodayCard />}

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

function StepsCard() {
  const [days, setDays] = useState<{ day: string; steps: number }[] | null>(
    null
  );

  useEffect(() => {
    api<MetricPoint[]>("/api/metrics/steps?days=8")
      .then((points) => {
        // En stapel per dag — högsta värdet vinner om flera källor rapporterar
        const byDay = new Map<string, number>();
        for (const p of points) {
          const day = p.measured_at.slice(0, 10);
          byDay.set(day, Math.max(byDay.get(day) ?? 0, p.value));
        }
        const result: { day: string; steps: number }[] = [];
        for (let i = 6; i >= 0; i--) {
          const d = new Date();
          d.setDate(d.getDate() - i);
          const key = d.toLocaleDateString("sv-SE");
          result.push({ day: key, steps: byDay.get(key) ?? 0 });
        }
        setDays(result);
      })
      .catch(() => {});
  }, []);

  if (!days) return null;
  const today = days[days.length - 1];
  const max = Math.max(...days.map((d) => d.steps), 1);
  const weekdays = ["sön", "mån", "tis", "ons", "tor", "fre", "lör"];

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card dark:border-night-shell dark:bg-night-card">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-faint">
            👟 Steg idag
          </p>
          <p className="text-3xl font-bold tabular-nums">
            {today.steps > 0
              ? Math.round(today.steps).toLocaleString("sv-SE")
              : "—"}
          </p>
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
          Inga steg registrerade idag ännu — synkas från Withings/Apple Health.
        </p>
      )}
    </section>
  );
}

type LatestMetrics = Record<
  string,
  { value: number; measured_at: string; source: string }
>;

/** Dagens kropp i korthet: puls, kondition och senaste nattens sömn. */
function TodayCard() {
  const [latest, setLatest] = useState<LatestMetrics | null>(null);

  useEffect(() => {
    api<LatestMetrics>("/api/metrics/latest").then(setLatest).catch(() => {});
  }, []);

  if (!latest) return null;
  const todayKey = new Date().toLocaleDateString("sv-SE");
  const isToday = (k: string) =>
    !!latest[k] &&
    new Date(latest[k].measured_at).toLocaleDateString("sv-SE") === todayKey;

  const hr = (k: string) =>
    isToday(k) ? String(Math.round(latest[k].value)) : "–";

  const sleep = latest["sleep_duration"];
  const sleepFresh =
    !!sleep &&
    Date.now() - new Date(sleep.measured_at).getTime() < 36 * 3600 * 1000;
  const sleepText = sleepFresh
    ? `${Math.floor(sleep.value)} h ${Math.round((sleep.value % 1) * 60)} min`
    : "–";
  const score = latest["sleep_score"];
  const vo2 = latest["vo2max"];

  const hasAnything =
    isToday("hr_avg") || isToday("hr_max") || sleepFresh || !!vo2;
  if (!hasAnything) return null;

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card dark:border-night-shell dark:bg-night-card">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold">Idag</h3>
        <a href="/health" className="text-xs text-navy dark:text-lime">
          Hälsa ›
        </a>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Stat label="❤️ Snittpuls" value={hr("hr_avg")} sub="bpm idag" />
        <Stat label="🔺 Maxpuls" value={hr("hr_max")} sub="bpm idag" />
        <Stat label="🔻 Lägsta" value={hr("hr_min")} sub="bpm idag" />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Stat
          label="😴 Sömn i natt"
          value={sleepText}
          sub={
            sleepFresh && score && isToday("sleep_score")
              ? `sömnpoäng ${Math.round(score.value)}/100`
              : "senaste natten"
          }
        />
        <Stat
          label="🫁 Kondition"
          value={vo2 ? vo2.value.toFixed(1) : "–"}
          sub={
            vo2
              ? `VO₂max · ${formatDate(vo2.measured_at)}`
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
