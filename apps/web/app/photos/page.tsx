"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatDate } from "../lib/api";

type Photo = { id: string; taken_at: string; pose: string };

const POSE_LABELS: Record<string, string> = {
  front: "Framifrån",
  side: "Från sidan",
  back: "Bakifrån",
};

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [pose, setPose] = useState("front");
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

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Progressfoton</h1>
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        <select
          value={pose}
          onChange={(e) => setPose(e.target.value)}
          className="rounded-xl border border-stone-300 bg-transparent px-3 py-2.5 text-sm dark:border-stone-700"
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
          className="flex-1 rounded-xl bg-emerald-600 py-2.5 font-semibold text-white disabled:opacity-50"
        >
          {uploading ? "Laddar upp…" : "📸 Ta / välj foto"}
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
        <section className="rounded-2xl border-2 border-emerald-400 bg-white p-3 dark:border-emerald-600 dark:bg-stone-900">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-bold">Före / efter</h2>
            <button
              onClick={() => setCompare([])}
              className="text-sm text-stone-400"
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
              .map((p, i) => (
                <figure key={p.id}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/photos/${p.id}/file`}
                    alt={POSE_LABELS[p.pose]}
                    className="aspect-[3/4] w-full rounded-xl object-cover"
                  />
                  <figcaption className="mt-1 text-center text-xs text-stone-500">
                    {i === 0 ? "Före · " : "Efter · "}
                    {formatDate(p.taken_at)}
                  </figcaption>
                </figure>
              ))}
          </div>
        </section>
      )}

      {photos.length === 0 && (
        <p className="py-8 text-center text-sm text-stone-400">
          Inga foton ännu. Ta ett första referensfoto idag — du kommer tacka
          dig själv om tre månader. 📈
        </p>
      )}

      {photos.length > 0 && (
        <p className="text-xs text-stone-400">
          Tryck på två foton för att jämföra före/efter.
        </p>
      )}

      <div className="grid grid-cols-3 gap-2">
        {photos.map((p) => {
          const selected = compare.some((c) => c.id === p.id);
          return (
            <div key={p.id} className="relative">
              <button
                onClick={() => toggleCompare(p)}
                className={`block w-full overflow-hidden rounded-xl ${
                  selected ? "ring-4 ring-emerald-500" : ""
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/api/photos/${p.id}/file`}
                  alt={POSE_LABELS[p.pose]}
                  className="aspect-[3/4] w-full object-cover"
                />
              </button>
              <p className="mt-0.5 text-center text-[10px] text-stone-400">
                {formatDate(p.taken_at)} · {POSE_LABELS[p.pose]}
              </p>
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
    </main>
  );
}
