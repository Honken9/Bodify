"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, formatDate } from "../lib/api";
import type { SessionSummary } from "../lib/types";

type CardioActivity = {
  id: string;
  type: string;
  source: string;
  name: string | null;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  avg_hr: number | null;
  avg_pace_s_per_km: number | null;
};

const TYPE_ICONS: Record<string, string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  other: "🏅",
};

function formatPace(s: number | null): string {
  if (!s) return "";
  const m = Math.floor(s / 60);
  const ss = Math.round(s % 60);
  return `${m}:${String(ss).padStart(2, "0")} /km`;
}

function formatDuration(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

export default function HistoryPage() {
  const [tab, setTab] = useState<"strength" | "cardio">("strength");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [cardio, setCardio] = useState<CardioActivity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<SessionSummary[]>("/api/sessions?limit=50")
      .then(setSessions)
      .catch((e: Error) => setError(e.message));
    api<CardioActivity[]>("/api/cardio?limit=50")
      .then(setCardio)
      .catch(() => {});
  }, []);

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Historik</h1>
      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      <div className="flex gap-1.5">
        {(
          [
            ["strength", "🏋️ Styrka"],
            ["cardio", "🏃 Kondition"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold ${
              tab === key
                ? "bg-sage text-white"
                : "bg-shell text-muted dark:bg-stone-800 dark:text-stone-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "strength" && (
        <>
          {sessions.length === 0 && !error && (
            <p className="py-8 text-center text-sm text-faint">
              Inga pass loggade ännu — dags att köra! 💪
            </p>
          )}
          <ul className="space-y-2">
            {sessions.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/workout/${s.id}`}
                  className="block rounded-xl border border-line bg-white px-4 py-3 dark:border-stone-800 dark:bg-stone-900"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">
                      {s.day_name ?? "Fritt pass"}
                      {!s.finished_at && (
                        <span className="ml-2 text-xs font-medium text-sand-ink dark:text-amber-400">
                          pågår
                        </span>
                      )}
                    </p>
                    <span className="text-sm text-muted dark:text-faint">
                      {formatDate(s.started_at)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-sm text-muted dark:text-faint">
                    {s.program_name ? `${s.program_name} · ` : ""}
                    {s.set_count} set · {Math.round(s.total_volume_kg)} kg volym
                  </p>
                  {s.notes && (
                    <p className="mt-1 text-sm italic text-faint">
                      {s.notes}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {tab === "cardio" && (
        <>
          {cardio.length === 0 && (
            <p className="py-8 text-center text-sm text-faint">
              Inga konditionspass ännu. Koppla Strava eller Apple Health under
              ⚙️ Kopplingar så dyker de upp här automatiskt.
            </p>
          )}
          <ul className="space-y-2">
            {cardio.map((a) => (
              <li
                key={a.id}
                className="rounded-xl border border-line bg-white px-4 py-3 dark:border-stone-800 dark:bg-stone-900"
              >
                <div className="flex items-center justify-between">
                  <p className="font-semibold">
                    {TYPE_ICONS[a.type] ?? "🏅"} {a.name ?? a.type}
                  </p>
                  <span className="text-sm text-muted dark:text-faint">
                    {formatDate(a.started_at)}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-muted dark:text-faint">
                  {a.distance_m
                    ? `${(a.distance_m / 1000).toFixed(2)} km · `
                    : ""}
                  {formatDuration(a.duration_s)}
                  {a.avg_pace_s_per_km
                    ? ` · ${formatPace(a.avg_pace_s_per_km)}`
                    : ""}
                  {a.avg_hr ? ` · ${Math.round(a.avg_hr)} bpm` : ""}
                </p>
                <p className="mt-0.5 text-xs text-faint">
                  via{" "}
                  {a.source === "strava"
                    ? "Strava"
                    : a.source === "apple_health"
                      ? "Apple Health"
                      : "manuell"}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
