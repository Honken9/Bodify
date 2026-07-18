"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { GeoActivity } from "../components/ActivityMap";

// Leaflet kräver window — ladda kartan först i webbläsaren
const ActivityMap = dynamic(() => import("../components/ActivityMap"), {
  ssr: false,
  loading: () => (
    <p className="py-16 text-center text-sm text-faint">Laddar kartan…</p>
  ),
});

const FILTERS: [string, string][] = [
  ["all", "Allt"],
  ["run", "🏃 Löpning"],
  ["ride", "🚴 Cykling"],
  ["walk", "🚶 Promenad"],
  ["other", "💪 Övrigt"],
];

const TYPE_ICONS: Record<string, string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  other: "💪",
};

export default function MapPage() {
  const [activities, setActivities] = useState<GeoActivity[] | null>(null);
  const [filter, setFilter] = useState("all");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<GeoActivity[]>("/api/cardio/geo?limit=5000")
      .then(setActivities)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function syncHistory() {
    setSyncing(true);
    setSyncResult(null);
    setError(null);
    try {
      const res = await api<{ imported: number }>(
        "/api/integrations/strava/sync",
        { method: "POST" }
      );
      setSyncResult(
        res.imported > 0
          ? `✅ ${res.imported} aktiviteter hämtade från Strava!`
          : "✅ Historiken är redan komplett — inget nytt att hämta."
      );
      setActivities(await api<GeoActivity[]>("/api/cardio/geo?limit=5000"));
    } catch (e) {
      const msg = (e as Error).message;
      setError(
        msg.includes("inte kopplat")
          ? "Strava är inte kopplat ännu — gör det under Kopplingar först."
          : msg
      );
    } finally {
      setSyncing(false);
    }
  }

  const filtered = (activities ?? []).filter(
    (a) => filter === "all" || a.type === filter
  );
  const routes = filtered.filter((a) => a.polyline).length;
  const fmtDate = new Intl.DateTimeFormat("sv-SE", {
    day: "numeric",
    month: "short",
  });

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <div className="flex items-center justify-between pt-2">
        <h1 className="text-2xl font-bold">Träningskarta</h1>
        <a href="/programs" className="text-sm text-navy dark:text-lime">
          ‹ Träning
        </a>
      </div>

      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}
      {syncResult && (
        <p className="rounded-xl bg-sand p-3 text-sm text-sand-ink dark:bg-night-shell dark:text-lime">
          {syncResult}
        </p>
      )}

      <div className="flex gap-1.5 overflow-x-auto">
        {FILTERS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold ${
              filter === key
                ? "bg-navy text-white"
                : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activities !== null && activities.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-line-strong p-6 text-center dark:border-night-strong">
          <p className="text-3xl">🗺️</p>
          <p className="mt-2 font-semibold">Inga GPS-spår ännu</p>
          <p className="mt-1 text-sm text-muted dark:text-faint">
            Rundor och platser hämtas från pass med GPS — koppla{" "}
            <a href="/settings" className="font-semibold text-navy dark:text-lime">
              Strava
            </a>{" "}
            så ritas dina löprundor här. (Withings skickar tyvärr inte med
            GPS-data via sitt API.)
          </p>
          <button
            disabled={syncing}
            onClick={syncHistory}
            className="mt-4 rounded-xl bg-navy px-5 py-2.5 font-semibold text-white disabled:opacity-50"
          >
            {syncing ? "Hämtar historik…" : "🔄 Hämta historik från Strava"}
          </button>
        </section>
      ) : (
        <div className="flex flex-col gap-4 desktop:grid desktop:grid-cols-[1fr_320px] desktop:items-start">
          <div>
            {/* Bläddra pass för pass, eller zooma ut till allt */}
            <div className="mb-2 flex items-center justify-between rounded-xl bg-cream-deep px-1 py-0.5 dark:bg-night-shell/60">
              <button
                onClick={() => {
                  const idx = filtered.findIndex((a) => a.id === focusId);
                  const next =
                    idx <= 0 ? filtered[filtered.length - 1] : filtered[idx - 1];
                  if (next) setFocusId(next.id);
                }}
                disabled={filtered.length === 0}
                className="px-3 py-1.5 text-lg leading-none disabled:opacity-30"
                aria-label="Föregående pass"
              >
                ‹
              </button>
              <div className="flex items-center gap-2 text-sm">
                {focusId ? (
                  <>
                    <span className="font-semibold">
                      {(() => {
                        const idx = filtered.findIndex((a) => a.id === focusId);
                        const a = filtered[idx];
                        return a
                          ? `${idx + 1} av ${filtered.length} · ${a.name ?? "Träning"}`
                          : "";
                      })()}
                    </span>
                    <button
                      onClick={() => setFocusId(null)}
                      className="rounded-full bg-shell px-2.5 py-1 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
                    >
                      Visa alla
                    </button>
                  </>
                ) : (
                  <span className="font-semibold">
                    Alla {filtered.length} aktiviteter
                  </span>
                )}
              </div>
              <button
                onClick={() => {
                  const idx = filtered.findIndex((a) => a.id === focusId);
                  const next =
                    idx < 0 || idx === filtered.length - 1
                      ? filtered[0]
                      : filtered[idx + 1];
                  if (next) setFocusId(next.id);
                }}
                disabled={filtered.length === 0}
                className="px-3 py-1.5 text-lg leading-none disabled:opacity-30"
                aria-label="Nästa pass"
              >
                ›
              </button>
            </div>
            <ActivityMap activities={filtered} focusId={focusId} />
            <p className="mt-2 text-xs text-muted dark:text-faint">
              {filtered.length} aktiviteter på kartan · {routes} med rutt.
              Linje = runda med GPS-spår, prick = plats för passet.{" "}
              <button
                disabled={syncing}
                onClick={syncHistory}
                className="font-semibold text-navy underline-offset-2 hover:underline disabled:opacity-50 dark:text-lime"
              >
                {syncing ? "Hämtar…" : "🔄 Hämta historik"}
              </button>
            </p>
          </div>

          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-faint">
              Alla aktiviteter
            </h2>
            <ul className="max-h-[50dvh] space-y-1.5 overflow-y-auto desktop:max-h-[70dvh]">
              {filtered.map((a) => {
                const active = focusId === a.id;
                return (
                  <li key={a.id}>
                    <button
                      onClick={() => setFocusId(a.id)}
                      className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left ${
                        active
                          ? "border-navy bg-navy-soft dark:border-lime dark:bg-night-shell"
                          : "border-line bg-white dark:border-night-shell dark:bg-night-card"
                      }`}
                    >
                      <span className="text-lg">
                        {TYPE_ICONS[a.type] ?? "💪"}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold">
                          {a.name ?? "Träning"}
                        </span>
                        <span className="block text-xs text-muted dark:text-faint">
                          {fmtDate.format(new Date(a.started_at))}
                          {a.distance_m
                            ? ` · ${(a.distance_m / 1000).toFixed(1)} km`
                            : ""}
                          {" · "}
                          {Math.round(a.duration_s / 60)} min
                          {a.polyline ? " · 📍 rutt" : ""}
                        </span>
                      </span>
                      <span className="text-faint">›</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>
      )}
    </main>
  );
}
