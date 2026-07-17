"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, formatDate } from "./lib/api";
import type { Me, SessionDetail, SessionSummary, UserProgram } from "./lib/types";

export default function Home() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [active, setActive] = useState<UserProgram | null>(null);
  const [recent, setRecent] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

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

  async function startSession(programDayId: string | null) {
    setStarting(true);
    try {
      const session = await api<SessionDetail>("/api/sessions/start", {
        method: "POST",
        body: JSON.stringify({ program_day_id: programDayId }),
      });
      router.push(`/workout/${session.id}`);
    } catch (e) {
      setError((e as Error).message);
      setStarting(false);
    }
  }

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

      {nextDay && !ongoing && (
        <section className="rounded-2xl border border-line bg-white p-5 shadow-card dark:border-night-shell dark:bg-night-card">
          <p className="text-xs font-semibold uppercase tracking-wide text-faint">
            Nästa pass · {active!.program.name}
          </p>
          <h2 className="mt-1 text-xl font-bold">{nextDay.name}</h2>
          <ul className="mt-3 space-y-1 text-sm text-muted dark:text-night-muted">
            {nextDay.exercises.map((ex) => (
              <li key={ex.id}>
                {ex.exercise.name} · {ex.target_sets} × {ex.target_reps}
              </li>
            ))}
          </ul>
          <button
            disabled={starting}
            onClick={() => startSession(nextDay.id)}
            className="mt-4 w-full rounded-xl bg-navy py-3 font-semibold text-white active:bg-navy-deep disabled:opacity-50"
          >
            {starting ? "Startar…" : "Starta passet"}
          </button>
        </section>
      )}

      {!active && !ongoing && me && (
        <section className="rounded-2xl border border-dashed border-line-strong p-5 text-center dark:border-night-strong">
          <p className="text-muted dark:text-night-muted">
            Du har inget aktivt program ännu.
          </p>
          <button
            onClick={() => router.push("/programs")}
            className="mt-3 rounded-xl bg-navy px-5 py-2 font-semibold text-white"
          >
            Välj program
          </button>
        </section>
      )}

      {!ongoing && me && (
        <button
          disabled={starting}
          onClick={() => startSession(null)}
          className="rounded-xl border border-line-strong py-3 font-semibold text-night-strong dark:border-night-strong dark:text-night-muted"
        >
          Starta fritt pass
        </button>
      )}

      {me && <ReadinessCard />}

      {me && <DashboardSection />}

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
