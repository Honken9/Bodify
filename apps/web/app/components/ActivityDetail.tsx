"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const ActivityMap = dynamic(() => import("./ActivityMap"), { ssr: false });

export type CardioDetail = {
  id: string;
  type: string;
  source: string;
  name: string | null;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_pace_s_per_km: number | null;
  calories: number | null;
  polyline: string | null;
  start: [number, number] | null;
  extras: Record<string, number | string>;
};

const TYPE_META: Record<string, [string, string]> = {
  run: ["🏃", "Löpning"],
  ride: ["🚴", "Cykling"],
  walk: ["🚶", "Promenad"],
  swim: ["🏊", "Simning"],
  other: ["💪", "Träning"],
};

const SOURCE_LABELS: Record<string, string> = {
  strava: "Strava",
  withings: "Withings",
  apple_health: "Apple Health",
  manual: "Manuellt loggad",
};

function fmtDuration(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

function fmtPace(sPerKm: number): string {
  const m = Math.floor(sPerKm / 60);
  const s = Math.round(sPerKm % 60);
  return `${m}:${String(s).padStart(2, "0")} /km`;
}

export default function ActivityDetail({
  activityId,
  onClose,
}: {
  activityId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<CardioDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CardioDetail>(`/api/cardio/${activityId}`)
      .then(setDetail)
      .catch((e: Error) => setError(e.message));
  }, [activityId]);

  const d = detail;
  const [icon, typeLabel] = TYPE_META[d?.type ?? "other"] ?? TYPE_META.other;
  const ex = d?.extras ?? {};

  // (etikett, värde) — bara det som faktiskt finns visas
  const stats: [string, string][] = d
    ? ([
        d.distance_m && [
          "Distans",
          `${(d.distance_m / 1000).toLocaleString("sv-SE", { maximumFractionDigits: 2 })} km`,
        ],
        ["Tid (aktiv)", fmtDuration(d.duration_s)],
        typeof ex.elapsed_time === "number" &&
          ex.elapsed_time > d.duration_s + 30 && [
            "Total tid",
            fmtDuration(ex.elapsed_time),
          ],
        d.avg_pace_s_per_km && ["Tempo", fmtPace(d.avg_pace_s_per_km)],
        typeof ex.average_speed === "number" && [
          "Snittfart",
          `${(ex.average_speed * 3.6).toFixed(1)} km/h`,
        ],
        typeof ex.max_speed === "number" && [
          "Maxfart",
          `${(ex.max_speed * 3.6).toFixed(1)} km/h`,
        ],
        d.avg_hr && ["Snittpuls", `${Math.round(d.avg_hr)} bpm`],
        d.max_hr && ["Maxpuls", `${Math.round(d.max_hr)} bpm`],
        d.calories && ["Kalorier", `${Math.round(d.calories)} kcal`],
        typeof ex.total_elevation_gain === "number" && [
          "Höjdmeter",
          `${Math.round(ex.total_elevation_gain)} m`,
        ],
        typeof ex.average_cadence === "number" && [
          "Kadens",
          `${Math.round(ex.average_cadence)}`,
        ],
        typeof ex.average_watts === "number" && [
          "Effekt",
          `${Math.round(ex.average_watts)} W`,
        ],
        typeof ex.suffer_score === "number" && [
          "Ansträngning",
          `${Math.round(ex.suffer_score)}`,
        ],
        typeof ex.kudos_count === "number" && [
          "Kudos",
          `👍 ${ex.kudos_count}`,
        ],
        typeof ex.pr_count === "number" &&
          ex.pr_count > 0 && ["Rekord", `🏅 ${ex.pr_count}`],
      ].filter(Boolean) as [string, string][])
    : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 desktop:items-center"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90dvh] w-full max-w-md flex-col overflow-hidden rounded-t-3xl bg-white desktop:rounded-3xl dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between p-5 pb-3">
          <div className="min-w-0">
            <h3 className="truncate text-lg font-bold">
              {icon} {d?.name ?? typeLabel}
            </h3>
            <p className="text-xs text-muted dark:text-faint">
              {d &&
                new Intl.DateTimeFormat("sv-SE", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                  hour: "2-digit",
                  minute: "2-digit",
                }).format(new Date(d.started_at))}
              {d && ` · ${SOURCE_LABELS[d.source] ?? d.source}`}
            </p>
          </div>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          {!d && !error && (
            <p className="py-8 text-center text-sm text-faint">Laddar…</p>
          )}

          {d && (d.polyline || d.start) && (
            <div className="mb-3">
              <ActivityMap
                activities={[
                  {
                    id: d.id,
                    type: d.type,
                    name: d.name,
                    started_at: d.started_at,
                    duration_s: d.duration_s,
                    distance_m: d.distance_m,
                    polyline: d.polyline,
                    start: d.start,
                  },
                ]}
                height={200}
              />
            </div>
          )}

          {d && (
            <div className="grid grid-cols-2 gap-2">
              {stats.map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-xl bg-cream-deep p-3 dark:bg-night-shell/60"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                    {label}
                  </p>
                  <p className="text-base font-bold">{value}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
