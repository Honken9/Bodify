"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Me } from "../lib/types";

type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  created_at: string;
};

type Overview = {
  users: number;
  workout_sessions: number;
  cardio_activities: number;
  meal_entries: number;
  challenges: number;
  connections: Record<string, number>;
};

export default function AdminPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<AdminUser[]>("/api/admin/users").then(setUsers).catch(() => {});
    api<Overview>("/api/admin/overview").then(setOverview).catch(() => {});
  }, []);

  useEffect(() => {
    api<Me>("/api/me").then((m) => {
      setMe(m);
      if (m.is_admin) refresh();
    });
  }, [refresh]);

  if (me && !me.is_admin) {
    return (
      <main className="mx-auto max-w-md p-5">
        <p className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          Den här sidan kräver adminbehörighet.
        </p>
      </main>
    );
  }

  async function toggleAdmin(user: AdminUser) {
    try {
      await api(`/api/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_admin: !user.is_admin }),
      });
      refresh();
    } catch (e) {
      setMessage((e as Error).message);
    }
  }

  async function runSnapshots() {
    const result = await api<{ snapshots: number; notifications: number }>(
      "/api/admin/jobs/challenge-snapshots",
      { method: "POST" }
    );
    setMessage(
      `Snapshot-jobbet kört: ${result.snapshots} snapshots, ${result.notifications} notiser.`
    );
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Admin</h1>
      {message && (
        <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-700 dark:bg-sky-950 dark:text-sky-300">
          {message}
        </p>
      )}

      {overview && (
        <section className="grid grid-cols-2 gap-2">
          {(
            [
              ["Användare", overview.users],
              ["Styrkepass", overview.workout_sessions],
              ["Konditionspass", overview.cardio_activities],
              ["Måltidsposter", overview.meal_entries],
              ["Utmaningar", overview.challenges],
              [
                "Kopplingar",
                Object.entries(overview.connections)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ") || "0",
              ],
            ] as [string, number | string][]
          ).map(([label, value]) => (
            <div
              key={label}
              className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
            >
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {label}
              </p>
              <p className="text-lg font-bold">{value}</p>
            </div>
          ))}
        </section>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-bold">Användare</h2>
        <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
          {users.map((u) => (
            <li key={u.id} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">
                  {u.display_name ?? u.email.split("@")[0]}
                  {u.is_admin && (
                    <span className="ml-2 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700 dark:bg-sky-950 dark:text-sky-300">
                      admin
                    </span>
                  )}
                </p>
                <p className="text-xs text-slate-400">{u.email}</p>
              </div>
              {me && u.id !== me.id && (
                <button
                  onClick={() => toggleAdmin(u)}
                  className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium dark:border-slate-700"
                >
                  {u.is_admin ? "Ta bort admin" : "Gör till admin"}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-bold">Jobb</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Snapshot-jobbet körs automatiskt varje kväll 20:30 av workern.
        </p>
        <button
          onClick={runSnapshots}
          className="mt-2 w-full rounded-xl border border-slate-300 py-2.5 text-sm font-semibold dark:border-slate-700"
        >
          Kör utmanings-snapshots nu
        </button>
      </section>
    </main>
  );
}
