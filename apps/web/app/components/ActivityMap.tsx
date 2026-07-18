"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type GeoActivity = {
  id: string;
  type: string;
  name: string | null;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  polyline: string | null;
  start: [number, number] | null;
};

/** Google/Strava-kodad polyline → [lat, lng][] */
function decodePolyline(encoded: string): [number, number][] {
  const points: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  while (index < encoded.length) {
    for (const which of [0, 1]) {
      let result = 0;
      let shift = 0;
      let byte: number;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (which === 0) lat += delta;
      else lng += delta;
    }
    points.push([lat / 1e5, lng / 1e5]);
  }
  return points;
}

const TYPE_ICONS: Record<string, string> = {
  run: "🏃",
  ride: "🚴",
  walk: "🚶",
  swim: "🏊",
  strength: "🏋️",
  other: "💪",
};

export default function ActivityMap({
  activities,
  height = 420,
  focusId = null,
}: {
  activities: GeoActivity[];
  height?: number | string;
  focusId?: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const allBoundsRef = useRef<L.LatLngBounds | null>(null);
  const layersRef = useRef<
    Map<string, { layer: L.Polyline | L.CircleMarker; isRoute: boolean }>
  >(new Map());
  const focusRef = useRef<string | null>(focusId);
  const myPosRef = useRef<{ dot: L.CircleMarker; ring: L.Circle } | null>(null);
  const [locating, setLocating] = useState(false);

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
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    const bounds = L.latLngBounds([]);
    const fmtDate = new Intl.DateTimeFormat("sv-SE", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });

    for (const a of activities) {
      const label = `${TYPE_ICONS[a.type] ?? "💪"} <b>${a.name ?? "Träning"}</b><br>${fmtDate.format(
        new Date(a.started_at)
      )}${a.distance_m ? ` · ${(a.distance_m / 1000).toFixed(1)} km` : ""} · ${Math.round(
        a.duration_s / 60
      )} min`;

      if (a.polyline) {
        // Rundan ritas som linje — navy med lime-startpunkt
        const coords = decodePolyline(a.polyline);
        if (coords.length > 1) {
          const line = L.polyline(coords, {
            color: "#23588a",
            weight: 3,
            opacity: 0.85,
          })
            .bindPopup(label)
            .addTo(map);
          layersRef.current.set(a.id, { layer: line, isRoute: true });
          bounds.extend(line.getBounds());
          L.circleMarker(coords[0], {
            radius: 5,
            color: "#7fc22b",
            fillColor: "#a1e645",
            fillOpacity: 1,
            weight: 2,
          })
            .bindPopup(label)
            .addTo(map);
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

    if (bounds.isValid()) {
      allBoundsRef.current = bounds;
      map.fitBounds(bounds, { padding: [30, 30] });
    } else {
      allBoundsRef.current = null;
      map.setView([59.334, 18.063], 5); // Sverige som utgångsvy
    }

    return () => {
      map.remove();
      mapRef.current = null;
      layersRef.current.clear();
      myPosRef.current = null; // lagren dog med kartan
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activities]);

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
