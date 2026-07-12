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
    <main className="mx-auto flex max-w-md flex-col gap-5 p-5">
      <header className="flex items-start justify-between pt-2">
        <div>
          <h1 className="text-2xl font-bold">
            {me ? `Hej ${me.display_name ?? me.email.split("@")[0]}! 👋` : "…"}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Redo för dagens pass?
          </p>
        </div>
        <a href="/settings" className="p-1 text-xl" aria-label="Kopplingar">
          ⚙️
        </a>
      </header>

      {ongoing && (
        <button
          onClick={() => router.push(`/workout/${ongoing.id}`)}
          className="rounded-2xl border-2 border-amber-400 bg-amber-50 p-5 text-left dark:border-amber-600 dark:bg-amber-950"
        >
          <p className="font-semibold">⏳ Pågående pass</p>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {ongoing.day_name ?? "Fritt pass"} · {ongoing.set_count} set loggade
            — tryck för att fortsätta
          </p>
        </button>
      )}

      {nextDay && !ongoing && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Nästa pass · {active!.program.name}
          </p>
          <h2 className="mt-1 text-xl font-bold">{nextDay.name}</h2>
          <ul className="mt-3 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            {nextDay.exercises.map((ex) => (
              <li key={ex.id}>
                {ex.exercise.name} · {ex.target_sets} × {ex.target_reps}
              </li>
            ))}
          </ul>
          <button
            disabled={starting}
            onClick={() => startSession(nextDay.id)}
            className="mt-4 w-full rounded-xl bg-sky-600 py-3 font-semibold text-white active:bg-sky-700 disabled:opacity-50"
          >
            {starting ? "Startar…" : "Starta passet"}
          </button>
        </section>
      )}

      {!active && !ongoing && me && (
        <section className="rounded-2xl border border-dashed border-slate-300 p-5 text-center dark:border-slate-700">
          <p className="text-slate-600 dark:text-slate-300">
            Du har inget aktivt program ännu.
          </p>
          <button
            onClick={() => router.push("/programs")}
            className="mt-3 rounded-xl bg-sky-600 px-5 py-2 font-semibold text-white"
          >
            Välj program
          </button>
        </section>
      )}

      {!ongoing && me && (
        <button
          disabled={starting}
          onClick={() => startSession(null)}
          className="rounded-xl border border-slate-300 py-3 font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
        >
          Starta fritt pass
        </button>
      )}

      {me && <DashboardSection />}

      {recent.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Senaste passen
          </h3>
          <ul className="space-y-2">
            {recent.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <span className="font-medium">
                  {s.day_name ?? "Fritt pass"}
                </span>
                <span className="text-slate-500 dark:text-slate-400">
                  {formatDate(s.started_at)} · {s.set_count} set
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {me && (
        <a
          href="/photos"
          className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium dark:border-slate-800 dark:bg-slate-900"
        >
          📸 Progressfoton — jämför före & efter ›
        </a>
      )}
    </main>
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
    <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <h3 className="font-bold">Din översikt</h3>
        <div className="flex gap-1">
          {(Object.keys(PERIOD_LABELS) as (keyof typeof PERIOD_LABELS)[]).map(
            (p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`rounded-lg px-2 py-1 text-xs font-medium ${
                  period === p
                    ? "bg-sky-600 text-white"
                    : "bg-slate-100 text-slate-500 dark:bg-slate-800"
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
          <div className="mt-3 grid grid-cols-2 gap-2">
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
                      ? "bg-emerald-500"
                      : d.strength
                        ? "bg-sky-500"
                        : d.cardio
                          ? "bg-amber-400"
                          : "bg-slate-100 dark:bg-slate-800"
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
    <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="text-lg font-bold">{value}</p>
      <p className="truncate text-xs text-slate-500 dark:text-slate-400">{sub}</p>
    </div>
  );
}
