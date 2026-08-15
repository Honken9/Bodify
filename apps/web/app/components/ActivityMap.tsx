"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type GeoActivity = {
  id: string;
  type: string;
  source?: string;
  name: string | null;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  polyline: string | null;
  start: [number, number] | null;
};

const SOURCE_LABELS: Record<string, string> = {
  withings: "Withings",
  strava: "Strava",
  apple_health: "Apple Health",
  manual: "Manuellt",
  shapiqo: "Shapiqo",
};

import { decodePolyline, type Viewport } from "../lib/polyline";

const TYPE_ICONS: Record<string, string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  strength: "🏋️",
  other: "💪",
};

/** Popup-innehållet byggs som HTML — passnamn (från Strava/Apple/egna
 * fält) måste escapas så de aldrig kan smuggla in markup. */
function esc(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export default function ActivityMap({
  activities,
  height = 420,
  focusId = null,
  onViewport,
  zoomOutKey = 0,
}: {
  activities: GeoActivity[];
  height?: number | string;
  focusId?: string | null;
  /** Anropas när kartvyn ändras (zoom/panorering) — driver listfiltret */
  onViewport?: (v: Viewport) => void;
  /** Räknas upp → zooma ut till alla aktiviteter */
  zoomOutKey?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const allBoundsRef = useRef<L.LatLngBounds | null>(null);
  const layersRef = useRef<
    Map<string, { layer: L.Polyline | L.CircleMarker; isRoute: boolean }>
  >(new Map());
  const focusRef = useRef<string | null>(focusId);
  // Senaste vyn — överlever ombygge av kartan (nya data ska inte
  // kasta användaren tillbaka till utzoomat läge)
  const viewRef = useRef<{ center: L.LatLng; zoom: number } | null>(null);
  const myPosRef = useRef<{ dot: L.CircleMarker; ring: L.Circle } | null>(null);
  const [locating, setLocating] = useState(false);
  // Callback i ref så kartan inte byggs om när föräldern re-renderar
  const onViewportRef = useRef(onViewport);
  onViewportRef.current = onViewport;

  // 🧭 Visa var jag är just nu — blå prick + osäkerhetsring
  function showMyPosition() {
    const map = mapRef.current;
    if (!map || !navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (geo) => {
        setLocating(false);
        const m = mapRef.current;
        if (!m) return;
        const p: [number, number] = [geo.coords.latitude, geo.coords.longitude];
        const accuracy = Math.min(geo.coords.accuracy || 30, 500);
        if (myPosRef.current) {
          myPosRef.current.dot.setLatLng(p);
          myPosRef.current.ring.setLatLng(p).setRadius(accuracy);
        } else {
          const ring = L.circle(p, {
            radius: accuracy,
            color: "#2563eb",
            weight: 1,
            fillColor: "#2563eb",
            fillOpacity: 0.12,
          }).addTo(m);
          const dot = L.circleMarker(p, {
            radius: 7,
            color: "#ffffff",
            weight: 3,
            fillColor: "#2563eb",
            fillOpacity: 1,
          })
            .bindPopup("🧭 Du är här")
            .addTo(m);
          myPosRef.current = { dot, ring };
        }
        m.setView(p, Math.max(m.getZoom(), 14));
        myPosRef.current.dot.openPopup();
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  // Valt pass lyser rött så det sticker ut bland de navyfärgade
  function styleEntry(
    entry: { layer: L.Polyline | L.CircleMarker; isRoute: boolean },
    focused: boolean
  ) {
    if (entry.isRoute) {
      (entry.layer as L.Polyline).setStyle({
        color: focused ? "#e11d48" : "#23588a",
        weight: focused ? 5 : 3,
        opacity: focused ? 1 : 0.85,
      });
    } else {
      const dot = entry.layer as L.CircleMarker;
      dot.setStyle({
        color: focused ? "#9f1239" : "#19325b",
        fillColor: focused ? "#e11d48" : "#23588a",
        fillOpacity: focused ? 1 : 0.85,
      });
      dot.setRadius(focused ? 9 : 7);
    }
    if (focused) entry.layer.bringToFront();
  }

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    // preferCanvas: ritar hundratals rutter snabbt utan att segna ner
    const map = L.map(containerRef.current, {
      scrollWheelZoom: true,
      preferCanvas: true,
    });
    mapRef.current = map;
    layersRef.current.clear();

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      updateWhenIdle: true, // hämta tiles först när rörelsen stannat
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    // Stor historik: hoppa över dekorativa startprickar och förenkla
    // linjerna hårdare — halverar antalet lager och ritpunkter
    const manyLayers = activities.length > 300;

    const bounds = L.latLngBounds([]);
    const fmtDate = new Intl.DateTimeFormat("sv-SE", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });

    for (const a of activities) {
      const label = `${TYPE_ICONS[a.type] ?? "💪"} <b>${esc(a.name ?? "Träning")}</b><br>${fmtDate.format(
        new Date(a.started_at)
      )}${a.distance_m ? ` · ${(a.distance_m / 1000).toFixed(1)} km` : ""} · ${Math.round(
        a.duration_s / 60
      )} min${
        a.source && SOURCE_LABELS[a.source]
          ? `<br><span style="opacity:.65">via ${SOURCE_LABELS[a.source]}</span>`
          : ""
      }`;

      if (a.polyline) {
        // Rundan ritas som linje — navy med lime-startpunkt
        const coords = decodePolyline(a.polyline);
        if (coords.length > 1) {
          const line = L.polyline(coords, {
            color: "#23588a",
            weight: 3,
            opacity: 0.85,
            smoothFactor: manyLayers ? 2.5 : 1,
          })
            .bindPopup(label)
            .addTo(map);
          layersRef.current.set(a.id, { layer: line, isRoute: true });
          bounds.extend(line.getBounds());
          if (!manyLayers) {
            L.circleMarker(coords[0], {
              radius: 5,
              color: "#7fc22b",
              fillColor: "#a1e645",
              fillOpacity: 1,
              weight: 2,
            })
              .bindPopup(label)
              .addTo(map);
          }
          continue;
        }
      }
      if (a.start) {
        // Platsbundet pass utan rutt — en prick
        const dot = L.circleMarker(a.start, {
          radius: 7,
          color: "#19325b",
          fillColor: "#23588a",
          fillOpacity: 0.85,
          weight: 2,
        })
          .bindPopup(label)
          .addTo(map);
        layersRef.current.set(a.id, { layer: dot, isRoute: false });
        bounds.extend(dot.getLatLng());
      }
    }

    // Behåll markeringen om kartan byggs om (t.ex. efter omladdning av data)
    const focused = focusRef.current && layersRef.current.get(focusRef.current);
    if (focused) styleEntry(focused, true);

    allBoundsRef.current = bounds.isValid() ? bounds : null;
    if (viewRef.current) {
      // Ombygge (nya data) — stanna kvar där användaren var
      map.setView(viewRef.current.center, viewRef.current.zoom);
    } else if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    } else {
      map.setView([59.334, 18.063], 5); // Sverige som utgångsvy
    }

    // Rapportera kartutsnittet vid zoom/panorering (och startläget)
    const reportViewport = () => {
      viewRef.current = { center: map.getCenter(), zoom: map.getZoom() };
      const b = map.getBounds();
      onViewportRef.current?.({
        south: b.getSouth(),
        west: b.getWest(),
        north: b.getNorth(),
        east: b.getEast(),
      });
    };
    map.on("moveend", reportViewport);
    reportViewport();

    return () => {
      map.remove();
      mapRef.current = null;
      layersRef.current.clear();
      myPosRef.current = null; // lagren dog med kartan
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activities]);

  // "Visa alla"-knappen → zooma ut till hela historiken
  useEffect(() => {
    if (zoomOutKey === 0) return;
    const map = mapRef.current;
    if (!map) return;
    map.closePopup();
    if (allBoundsRef.current) {
      map.fitBounds(allBoundsRef.current, { padding: [30, 30] });
    }
  }, [zoomOutKey]);

  // Klick i listan/bläddring → zooma till aktiviteten; null = visa alla
  useEffect(() => {
    focusRef.current = focusId;
    const map = mapRef.current;
    if (!map) return;
    for (const [id, e] of layersRef.current) styleEntry(e, id === focusId);
    if (!focusId) {
      map.closePopup();
      if (allBoundsRef.current) {
        map.fitBounds(allBoundsRef.current, { padding: [30, 30] });
      }
      return;
    }
    const entry = layersRef.current.get(focusId);
    if (!entry) return;
    if (entry.isRoute) {
      map.fitBounds((entry.layer as L.Polyline).getBounds(), {
        padding: [40, 40],
        maxZoom: 16,
      });
    } else {
      map.setView((entry.layer as L.CircleMarker).getLatLng(), 15);
    }
    entry.layer.openPopup();
  }, [focusId]);

  return (
    <div className="relative w-full" style={{ height }}>
      <div
        ref={containerRef}
        className="z-0 h-full w-full overflow-hidden rounded-2xl border border-line dark:border-night-shell"
      />
      <button
        onClick={showMyPosition}
        disabled={locating}
        aria-label="Visa min position"
        title="Visa min position"
        className="absolute right-2 top-12 z-[500] rounded-lg bg-white/90 px-2.5 py-1.5 text-sm font-bold shadow-card disabled:opacity-50 dark:bg-night-card/90"
      >
        {locating ? "…" : "🧭"}
      </button>
    </div>
  );
}
