"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, formatDate } from "../lib/api";
import type { SessionSummary } from "../lib/types";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<SessionSummary[]>("/api/sessions?limit=50")
      .then(setSessions)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Historik</h1>
      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      {sessions.length === 0 && !error && (
        <p className="py-8 text-center text-sm text-slate-400">
          Inga pass loggade ännu — dags att köra! 💪
        </p>
      )}

      <ul className="space-y-2">
        {sessions.map((s) => (
          <li key={s.id}>
            <Link
              href={`/workout/${s.id}`}
              className="block rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between">
                <p className="font-semibold">
                  {s.day_name ?? "Fritt pass"}
                  {!s.finished_at && (
                    <span className="ml-2 text-xs font-medium text-amber-600 dark:text-amber-400">
                      pågår
                    </span>
                  )}
                </p>
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  {formatDate(s.started_at)}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                {s.program_name ? `${s.program_name} · ` : ""}
                {s.set_count} set · {Math.round(s.total_volume_kg)} kg volym
              </p>
              {s.notes && (
                <p className="mt-1 text-sm italic text-slate-400">{s.notes}</p>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
