"use client";

import { useEffect, useState } from "react";

type Me = {
  email: string;
  display_name: string | null;
  is_admin: boolean;
};

export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/me")
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail ?? `Fel ${res.status}`);
        }
        return res.json();
      })
      .then(setMe)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-4xl font-bold tracking-tight">Bodify</h1>

      {me && (
        <div className="w-full rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <p className="text-2xl font-semibold">
            Hej {me.display_name ?? me.email}! 👋
          </p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Inloggad via Cloudflare Access som {me.email}
            {me.is_admin && " · admin"}
          </p>
        </div>
      )}

      {error && (
        <div className="w-full rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {!me && !error && (
        <p className="text-slate-500 dark:text-slate-400">Laddar…</p>
      )}
    </main>
  );
}
