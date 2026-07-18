"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/** Välj plats för ett pass utan GPS — tryck på kartan för att sätta
 * nålen, eller använd mobilens position. */
export default function LocationPicker({
  onSave,
  onClose,
}: {
  onSave: (pos: [number, number]) => void;
  onClose: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const [pos, setPos] = useState<[number, number] | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current).setView([59.334, 18.063], 5);
    mapRef.current = map;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    map.on("click", (e: L.LeafletMouseEvent) => {
      place([e.latlng.lat, e.latlng.lng]);
    });

    function place(p: [number, number]) {
      setPos(p);
      if (markerRef.current) {
        markerRef.current.setLatLng(p);
      } else {
        markerRef.current = L.circleMarker(p, {
          radius: 8,
          color: "#19325b",
          fillColor: "#a1e645",
          fillOpacity: 1,
          weight: 2,
        }).addTo(map);
      }
    }

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function useMyPosition() {
    navigator.geolocation?.getCurrentPosition(
      (geo) => {
        const p: [number, number] = [geo.coords.latitude, geo.coords.longitude];
        setPos(p);
        const map = mapRef.current;
        if (map) {
          map.setView(p, 15);
          if (markerRef.current) markerRef.current.setLatLng(p);
          else
            markerRef.current = L.circleMarker(p, {
              radius: 8,
              color: "#19325b",
              fillColor: "#a1e645",
              fillOpacity: 1,
              weight: 2,
            }).addTo(map);
        }
      },
      () => {}
    );
  }

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-3xl bg-white p-4 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center justify-between">
          <h3 className="font-bold">📍 Var var passet?</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>
        <p className="mb-2 text-xs text-muted dark:text-faint">
          Tryck på kartan för att sätta nålen — zooma in för precision.
        </p>
        <div
          ref={containerRef}
          style={{ height: 300 }}
          className="z-0 w-full overflow-hidden rounded-xl border border-line dark:border-night-shell"
        />
        <div className="mt-3 flex gap-2">
          <button
            onClick={useMyPosition}
            className="flex-1 rounded-xl border border-line-strong py-2.5 text-sm font-semibold text-muted dark:border-night-strong dark:text-night-muted"
          >
            🧭 Använd min position
          </button>
          <button
            disabled={!pos || saving}
            onClick={() => {
              if (!pos) return;
              setSaving(true);
              onSave(pos);
            }}
            className="flex-1 rounded-xl bg-navy py-2.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {saving ? "Sparar…" : "Spara platsen"}
          </button>
        </div>
      </div>
    </div>
  );
}
