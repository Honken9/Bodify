"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatDate } from "../lib/api";

type Photo = { id: string; taken_at: string; pose: string; phase: string };

const POSE_LABELS: Record<string, string> = {
  front: "Framifrån",
  side: "Från sidan",
  back: "Bakifrån",
};

const PHASES: { key: string; label: string; icon: string; blurb: string }[] = [
  { key: "before", label: "Före", icon: "🟢", blurb: "Startpunkten — referensen allt jämförs mot." },
  { key: "during", label: "Mittemellan", icon: "🟡", blurb: "Checkpoints längs vägen." },
  { key: "after", label: "Efter", icon: "🏁", blurb: "Resultatet." },
];

const PHASE_LABELS: Record<string, string> = Object.fromEntries(
  PHASES.map((p) => [p.key, p.label])
);

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [pose, setPose] = useState("front");
  const [phase, setPhase] = useState("before");
  const [compare, setCompare] = useState<Photo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    api<Photo[]>("/api/photos")
      .then(setPhotos)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("pose", pose);
      form.append("phase", phase);
      const res = await fetch("/api/photos", { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Fel ${res.status}`);
      }
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function retag(photo: Photo, newPhase: string) {
    if (newPhase === photo.phase) return;
    try {
      await api(`/api/photos/${photo.id}`, {
        method: "PATCH",
        body: JSON.stringify({ phase: newPhase }),
      });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function toggleCompare(photo: Photo) {
    setCompare((prev) => {
      if (prev.some((p) => p.id === photo.id)) {
        return prev.filter((p) => p.id !== photo.id);
      }
      return prev.length >= 2 ? [prev[1], photo] : [...prev, photo];
    });
  }

  async function remove(id: string) {
    if (!window.confirm("Ta bort fotot?")) return;
    await api(`/api/photos/${id}`, { method: "DELETE" });
    setCompare((prev) => prev.filter((p) => p.id !== id));
    refresh();
  }

  const selectCls =
    "rounded-xl border border-line-strong bg-transparent px-3 py-2.5 text-sm dark:border-night-strong";

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Progressfoton</h1>
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        <select
          value={phase}
          onChange={(e) => setPhase(e.target.value)}
          className={selectCls}
          aria-label="När i resan"
        >
          {PHASES.map((p) => (
            <option key={p.key} value={p.key}>
              {p.icon} {p.label}
            </option>
          ))}
        </select>
        <select
          value={pose}
          onChange={(e) => setPose(e.target.value)}
          className={selectCls}
          aria-label="Vinkel"
        >
          {Object.entries(POSE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <button
          disabled={uploading}
          onClick={() => fileRef.current?.click()}
          className="flex-1 rounded-xl bg-navy py-2.5 font-semibold text-white disabled:opacity-50"
        >
          {uploading ? "Laddar upp…" : "📸 Foto"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />
      </div>

      {compare.length === 2 && (
        <section className="rounded-2xl border-2 border-navy bg-white p-3 dark:border-lime dark:bg-night-card">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-bold">Jämförelse</h2>
            <button
              onClick={() => setCompare([])}
              className="text-sm text-faint"
            >
              Stäng ✕
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[...compare]
              .sort(
                (a, b) =>
                  new Date(a.taken_at).getTime() -
                  new Date(b.taken_at).getTime()
              )
              .map((p) => (
                <figure key={p.id}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/photos/${p.id}/file`}
                    alt={POSE_LABELS[p.pose]}
                    className="aspect-[3/4] w-full rounded-xl object-cover"
                  />
                  <figcaption className="mt-1 text-center text-xs text-muted">
                    {PHASE_LABELS[p.phase] ?? p.phase} · {formatDate(p.taken_at)}
                  </figcaption>
                </figure>
              ))}
          </div>
        </section>
      )}

      {photos.length === 0 && (
        <p className="py-8 text-center text-sm text-faint">
          Inga foton ännu. Ta ett första Före-foto idag — du kommer tacka
          dig själv om tre månader. 📈
        </p>
      )}

      {photos.length > 0 && (
        <p className="text-xs text-faint">
          Tryck på två foton för att jämföra sida vid sida. Taggen under
          varje foto flyttar det mellan grupperna.
        </p>
      )}

      {PHASES.map(({ key, label, icon, blurb }) => {
        const group = photos.filter((p) => p.phase === key);
        if (group.length === 0) return null;
        return (
          <section key={key}>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="font-bold">
                {icon} {label}
                <span className="ml-1.5 text-sm font-normal text-faint">
                  ({group.length})
                </span>
              </h2>
              <span className="text-xs text-faint">{blurb}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 desktop:grid-cols-6">
              {group.map((p) => {
                const selected = compare.some((c) => c.id === p.id);
                return (
                  <div key={p.id} className="relative">
                    <button
                      onClick={() => toggleCompare(p)}
                      className={`block w-full overflow-hidden rounded-xl ${
                        selected ? "ring-4 ring-navy" : ""
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`/api/photos/${p.id}/file`}
                        alt={`${label} · ${POSE_LABELS[p.pose]}`}
                        className="aspect-[3/4] w-full object-cover"
                      />
                    </button>
                    <p className="mt-0.5 text-center text-[10px] text-faint">
                      {formatDate(p.taken_at)} · {POSE_LABELS[p.pose]}
                    </p>
                    <select
                      value={p.phase}
                      onChange={(e) => retag(p, e.target.value)}
                      className="mt-0.5 w-full rounded-md border border-line bg-transparent px-1 py-0.5 text-center text-[10px] text-muted dark:border-night-shell dark:text-night-muted"
                      aria-label="Flytta till grupp"
                    >
                      {PHASES.map((ph) => (
                        <option key={ph.key} value={ph.key}>
                          {ph.icon} {ph.label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => remove(p.id)}
                      className="absolute right-1 top-1 rounded-full bg-black/50 px-1.5 text-xs text-white"
                      aria-label="Ta bort"
                    >
                      ✕
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </main>
  );
}
