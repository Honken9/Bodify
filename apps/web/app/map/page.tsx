"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { sourceLabel } from "../lib/sources";
import ActivityDetail from "../components/ActivityDetail";
import type { GeoActivity } from "../components/ActivityMap";
import type { CardioActivity } from "../lib/types";

const LocationPicker = dynamic(() => import("../components/LocationPicker"), {
  ssr: false,
});

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
  ["nogps", "📋 Ej på karta"],
];

const TYPE_ICONS: Record<string, string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  other: "💪",
};

const PERIODS: [string, string][] = [
  ["all", "Allt"],
  ["week", "Vecka"],
  ["month", "Månad"],
  ["year", "År"],
];

function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export default function MapPage() {
  const [all, setAll] = useState<CardioActivity[] | null>(null);
  const [geo, setGeo] = useState<GeoActivity[]>([]);
  const [filter, setFilter] = useState("all");
  const [period, setPeriod] = useState("all");
  const [periodOffset, setPeriodOffset] = useState(0); // 0 = nu, -1 = förra…
  const [focusId, setFocusId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkPicker, setBulkPicker] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const [allActs, geoActs] = await Promise.all([
      api<CardioActivity[]>("/api/cardio?limit=5000"),
      api<GeoActivity[]>("/api/cardio/geo?limit=5000"),
    ]);
    setAll(allActs);
    setGeo(geoActs);
  }

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, []);

  async function syncHistory() {
    setSyncing(true);
    setSyncResult(null);
    setError(null);
    try {
      const res = await api<{ imported: number; paused?: boolean }>(
        "/api/integrations/strava/sync",
        { method: "POST" }
      );
      setSyncResult(
        res.paused
          ? `⏸ ${res.imported} aktiviteter hämtade — Stravas kvot är nådd. ` +
              "Tryck på Hämta historik igen om ca 15 min så fortsätter " +
              "hämtningen bakåt i tiden."
          : res.imported > 0
            ? `✅ ${res.imported} aktiviteter hämtade från Strava!`
            : "✅ Historiken är redan komplett — inget nytt att hämta."
      );
      await load();
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

  const geoById = new Map(geo.map((g) => [g.id, g]));

  // Vald tidsperiod → [start, slut) att filtrera på; null = allt
  function periodRange(): [Date, Date] | null {
    if (period === "all") return null;
    const now = new Date();
    if (period === "year") {
      const y = now.getFullYear() + periodOffset;
      return [new Date(y, 0, 1), new Date(y + 1, 0, 1)];
    }
    if (period === "month") {
      const s = new Date(now.getFullYear(), now.getMonth() + periodOffset, 1);
      return [s, new Date(s.getFullYear(), s.getMonth() + 1, 1)];
    }
    // Vecka — måndag som första dag
    const monday = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate() - ((now.getDay() + 6) % 7) + periodOffset * 7
    );
    const end = new Date(monday);
    end.setDate(end.getDate() + 7);
    return [monday, end];
  }
  const range = periodRange();

  function periodLabel(): string {
    if (!range) return "";
    const [s, e] = range;
    if (period === "year") return String(s.getFullYear());
    if (period === "month")
      return new Intl.DateTimeFormat("sv-SE", {
        month: "long",
        year: "numeric",
      }).format(s);
    const last = new Date(e);
    last.setDate(last.getDate() - 1);
    return `v.${isoWeek(s)} · ${s.getDate()}/${s.getMonth() + 1}–${last.getDate()}/${
      last.getMonth() + 1
    }`;
  }

  // Listan: alla pass (typ- + tidsfilter), "nogps" = bara de utan GPS
  const listItems = (all ?? []).filter((a) => {
    if (range) {
      const t = new Date(a.started_at);
      if (t < range[0] || t >= range[1]) return false;
    }
    if (filter === "nogps") return !geoById.has(a.id);
    return filter === "all" || a.type === filter;
  });
  // Kartan: de av listans pass som har GPS + styrkepass med position
  const inRange = (iso: string) => {
    if (!range) return true;
    const t = new Date(iso);
    return t >= range[0] && t < range[1];
  };
  const mapActivities = [
    ...listItems
      .map((a) => geoById.get(a.id))
      .filter((g): g is GeoActivity => !!g),
    ...(filter === "all"
      ? geo.filter((g) => g.type === "strength" && inRange(g.started_at))
      : []),
  ];
  const routes = mapActivities.filter((a) => a.polyline).length;

  const fmtDate = new Intl.DateTimeFormat("sv-SE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const focusIdx = mapActivities.findIndex((a) => a.id === focusId);

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function bulkAssign([lat, lng]: [number, number]) {
    try {
      const res = await api<{ updated: number }>(
        "/api/cardio/location-bulk",
        {
          method: "PATCH",
          body: JSON.stringify({ lat, lng, ids: Array.from(selected) }),
        }
      );
      setBulkPicker(false);
      setSelected(new Set());
      setSyncResult(`✅ ${res.updated} pass platssatta — nu syns de på kartan!`);
      await load();
    } catch (e) {
      setBulkPicker(false);
      setError((e as Error).message);
    }
  }

  function step(delta: number) {
    if (mapActivities.length === 0) return;
    const next =
      focusIdx < 0
        ? delta > 0
          ? mapActivities[0]
          : mapActivities[mapActivities.length - 1]
        : mapActivities[
            (focusIdx + delta + mapActivities.length) % mapActivities.length
          ];
    setFocusId(next.id);
  }

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
            onClick={() => {
              setFilter(key);
              setFocusId(null);
            }}
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

      {/* Tidsfilter: allt, eller bläddra vecka/månad/år */}
      <div className="flex flex-wrap items-center gap-1.5">
        {PERIODS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => {
              setPeriod(key);
              setPeriodOffset(0);
              setFocusId(null);
              setSelected(new Set());
            }}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold ${
              period === key
                ? "bg-lime text-lime-ink"
                : "bg-shell text-muted dark:bg-night-shell dark:text-night-muted"
            }`}
          >
            {label}
          </button>
        ))}
        {range && (
          <div className="ml-auto flex items-center gap-1 rounded-full bg-cream-deep px-1 py-0.5 dark:bg-night-shell/60">
            <button
              onClick={() => {
                setPeriodOffset((o) => o - 1);
                setFocusId(null);
                setSelected(new Set());
              }}
              className="px-2 py-1 text-sm leading-none"
              aria-label="Föregående period"
            >
              ‹
            </button>
            <span className="min-w-20 text-center text-xs font-semibold capitalize">
              {periodLabel()}
            </span>
            <button
              onClick={() => {
                setPeriodOffset((o) => Math.min(0, o + 1));
                setFocusId(null);
                setSelected(new Set());
              }}
              disabled={periodOffset === 0}
              className="px-2 py-1 text-sm leading-none disabled:opacity-30"
              aria-label="Nästa period"
            >
              ›
            </button>
          </div>
        )}
      </div>

      {all !== null && all.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-line-strong p-6 text-center dark:border-night-strong">
          <p className="text-3xl">🗺️</p>
          <p className="mt-2 font-semibold">Ingen träningshistorik ännu</p>
          <p className="mt-1 text-sm text-muted dark:text-faint">
            Koppla{" "}
            <a href="/settings" className="font-semibold text-navy dark:text-lime">
              Strava
            </a>{" "}
            och hämta historiken — rundor med GPS ritas på kartan, övriga
            pass hamnar i listan.
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
          <div className={filter === "nogps" ? "hidden desktop:block" : ""}>
            {/* Bläddra pass för pass, eller zooma ut till allt */}
            <div className="mb-2 flex items-center justify-between rounded-xl bg-cream-deep px-1 py-0.5 dark:bg-night-shell/60">
              <button
                onClick={() => step(-1)}
                disabled={mapActivities.length === 0}
                className="px-3 py-1.5 text-lg leading-none disabled:opacity-30"
                aria-label="Föregående pass"
              >
                ‹
              </button>
              <div className="flex min-w-0 items-center gap-2 text-sm">
                {focusId && focusIdx >= 0 ? (
                  <>
                    <span className="truncate font-semibold">
                      {focusIdx + 1} av {mapActivities.length} ·{" "}
                      {mapActivities[focusIdx].name ?? "Träning"}
                    </span>
                    {mapActivities[focusIdx].type !== "strength" && (
                      <button
                        onClick={() => setDetailId(focusId)}
                        className="shrink-0 rounded-full bg-navy px-2.5 py-1 text-xs font-semibold text-white"
                      >
                        Detaljer
                      </button>
                    )}
                    <button
                      onClick={() => setFocusId(null)}
                      className="shrink-0 rounded-full bg-shell px-2.5 py-1 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
                    >
                      Visa alla
                    </button>
                  </>
                ) : (
                  <span className="font-semibold">
                    Alla {mapActivities.length} på kartan
                  </span>
                )}
              </div>
              <button
                onClick={() => step(1)}
                disabled={mapActivities.length === 0}
                className="px-3 py-1.5 text-lg leading-none disabled:opacity-30"
                aria-label="Nästa pass"
              >
                ›
              </button>
            </div>
            {!fullscreen && (
              <div className="relative">
                <ActivityMap activities={mapActivities} focusId={focusId} />
                <button
                  onClick={() => setFullscreen(true)}
                  aria-label="Helskärm"
                  title="Visa kartan i helskärm"
                  className="absolute right-2 top-2 z-[500] rounded-lg bg-white/90 px-2.5 py-1.5 text-sm font-bold shadow-card dark:bg-night-card/90"
                >
                  ⛶
                </button>
              </div>
            )}
            <p className="mt-2 text-xs text-muted dark:text-faint">
              {mapActivities.length} på kartan · {routes} med rutt · linje =
              GPS-spår, prick = plats.{" "}
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
              {filter === "nogps"
                ? `Pass utan GPS (${listItems.length})`
                : `Alla aktiviteter (${listItems.length})`}
            </h2>

            {filter === "nogps" && listItems.length > 0 && (
              <div className="mb-2 flex items-center gap-2 rounded-xl bg-cream-deep px-3 py-2 dark:bg-night-shell/60">
                <button
                  onClick={() =>
                    setSelected((prev) =>
                      prev.size === listItems.length
                        ? new Set()
                        : new Set(listItems.map((a) => a.id))
                    )
                  }
                  className="text-xs font-semibold text-navy dark:text-lime"
                >
                  {selected.size === listItems.length
                    ? "Rensa urval"
                    : `Välj alla (${listItems.length})`}
                </button>
                <button
                  disabled={selected.size === 0}
                  onClick={() => setBulkPicker(true)}
                  className="ml-auto rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                >
                  📍 Sätt plats för {selected.size} valda
                </button>
              </div>
            )}
            <ul className="max-h-[50dvh] space-y-1.5 overflow-y-auto desktop:max-h-[70dvh]">
              {listItems.length === 0 && (
                <p className="py-4 text-center text-sm text-faint">
                  Inga pass i den här vyn.
                </p>
              )}
              {listItems.map((a) => {
                const g = geoById.get(a.id);
                const active = focusId === a.id;
                return (
                  <li key={a.id}>
                    <div
                      className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 ${
                        active
                          ? "border-navy bg-navy-soft dark:border-lime dark:bg-night-shell"
                          : "border-line bg-white dark:border-night-shell dark:bg-night-card"
                      }`}
                    >
                      <button
                        onClick={() => {
                          // Klick på passet → detaljkortet med all data;
                          // kartan fokuserar samtidigt om GPS finns
                          if (g) setFocusId(a.id);
                          setDetailId(a.id);
                        }}
                        className="flex min-w-0 flex-1 items-center gap-3 text-left"
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
                            {g?.polyline
                              ? " · 📍 rutt"
                              : g
                                ? " · 📍 plats"
                                : ""}
                            {` · ${sourceLabel(a.source)}`}
                          </span>
                        </span>
                      </button>
                      {filter === "nogps" ? (
                        <input
                          type="checkbox"
                          checked={selected.has(a.id)}
                          onChange={() => toggleSelected(a.id)}
                          className="h-5 w-5 shrink-0 accent-[#23588a]"
                          aria-label="Välj pass"
                        />
                      ) : (
                        g && (
                          <button
                            onClick={() => setFocusId(a.id)}
                            aria-label="Visa på kartan"
                            className="shrink-0 rounded-full bg-shell px-2.5 py-1.5 text-xs font-bold text-muted dark:bg-night-shell dark:text-night-muted"
                          >
                            🗺
                          </button>
                        )
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>
      )}

      {fullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-cream dark:bg-night">
          <div className="flex shrink-0 items-center justify-between gap-2 px-3 py-2">
            <button
              onClick={() => step(-1)}
              disabled={mapActivities.length === 0}
              className="px-3 py-1.5 text-xl leading-none disabled:opacity-30"
              aria-label="Föregående pass"
            >
              ‹
            </button>
            <div className="flex min-w-0 items-center gap-2 text-sm">
              {focusId && focusIdx >= 0 ? (
                <>
                  <span className="truncate font-semibold">
                    {focusIdx + 1} av {mapActivities.length} ·{" "}
                    {mapActivities[focusIdx].name ?? "Träning"}
                  </span>
                  {mapActivities[focusIdx].type !== "strength" && (
                    <button
                      onClick={() => setDetailId(focusId)}
                      className="shrink-0 rounded-full bg-navy px-2.5 py-1 text-xs font-semibold text-white"
                    >
                      Detaljer
                    </button>
                  )}
                  <button
                    onClick={() => setFocusId(null)}
                    className="shrink-0 rounded-full bg-shell px-2.5 py-1 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
                  >
                    Visa alla
                  </button>
                </>
              ) : (
                <span className="font-semibold">
                  Alla {mapActivities.length} på kartan
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => step(1)}
                disabled={mapActivities.length === 0}
                className="px-3 py-1.5 text-xl leading-none disabled:opacity-30"
                aria-label="Nästa pass"
              >
                ›
              </button>
              <button
                onClick={() => setFullscreen(false)}
                className="rounded-full bg-shell px-3 py-1.5 text-sm font-semibold dark:bg-night-shell"
                aria-label="Stäng helskärm"
              >
                ✕
              </button>
            </div>
          </div>
          <div className="min-h-0 flex-1 px-2 pb-2">
            <ActivityMap
              activities={mapActivities}
              focusId={focusId}
              height="100%"
            />
          </div>
        </div>
      )}

      {bulkPicker && (
        <LocationPicker
          onSave={bulkAssign}
          onClose={() => setBulkPicker(false)}
        />
      )}

      {detailId && (
        <ActivityDetail
          activityId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => load().catch(() => {})}
        />
      )}
    </main>
  );
}
