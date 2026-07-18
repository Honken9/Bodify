"use client";

import { useRef, useState } from "react";

type VisionResult = {
  equipment: string[];
  exercises: { id: string; name: string; muscle_groups: string[] }[];
};

export default function GymVision({ onClose }: { onClose: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<VisionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { downscaleImage } = await import("../lib/image");
      const small = await downscaleImage(file);
      const form = new FormData();
      form.append("file", small, "gym.jpg");
      const res = await fetch("/api/ai/gym-vision", {
        method: "POST",
        body: form,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.detail ?? `Fel ${res.status}`);
      setResult(body);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">📷 Gym-vision</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>

        <p className="mb-3 text-sm text-muted dark:text-faint">
          Fota gymmets utrustning så föreslår Shapiqo övningar du kan köra där.
        </p>

        <button
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Analyserar…" : "Ta / välj foto"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) analyze(f);
            e.target.value = "";
          }}
        />

        {error && (
          <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        {result && (
          <div className="mt-4">
            {result.equipment.length === 0 ? (
              <p className="text-center text-sm text-faint">
                Ingen utrustning kändes igen — prova ett tydligare foto.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap gap-1.5">
                  {result.equipment.map((eq) => (
                    <span
                      key={eq}
                      className="rounded-full bg-navy-soft px-3 py-1 text-xs font-semibold capitalize text-navy-deep dark:bg-night-shell dark:text-lime"
                    >
                      ✓ {eq}
                    </span>
                  ))}
                </div>
                <ul className="mt-3 divide-y divide-line dark:divide-night-shell">
                  {result.exercises.map((e) => (
                    <li key={e.id} className="py-2">
                      <p className="text-sm font-medium">{e.name}</p>
                      <p className="text-xs capitalize text-faint">
                        {e.muscle_groups.join(" · ")}
                      </p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
