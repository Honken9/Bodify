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

type TestersData = {
  configured: boolean;
  testers: {
    email: string;
    has_logged_in: boolean;
    display_name: string | null;
  }[];
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
        <p className="rounded-2xl border border-stone-200 bg-white p-6 text-center text-stone-500 dark:border-stone-800 dark:bg-stone-900">
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
        <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
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
              className="rounded-xl border border-stone-200 bg-white p-3 dark:border-stone-800 dark:bg-stone-900"
            >
              <p className="text-[10px] font-semibold uppercase tracking-wide text-stone-400">
                {label}
              </p>
              <p className="text-lg font-bold">{value}</p>
            </div>
          ))}
        </section>
      )}

      <UsersSection
        users={users}
        meId={me?.id ?? null}
        onToggleAdmin={toggleAdmin}
        onChanged={refresh}
        onMessage={setMessage}
      />

      <TestersSection onMessage={setMessage} />

      <section className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
        <h2 className="font-bold">Jobb</h2>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
          Snapshot-jobbet körs automatiskt varje kväll 20:30 av workern.
        </p>
        <button
          onClick={runSnapshots}
          className="mt-2 w-full rounded-xl border border-stone-300 py-2.5 text-sm font-semibold dark:border-stone-700"
        >
          Kör utmanings-snapshots nu
        </button>
      </section>
    </main>
  );
}

function UsersSection({
  users,
  meId,
  onToggleAdmin,
  onChanged,
  onMessage,
}: {
  users: AdminUser[];
  meId: string | null;
  onToggleAdmin: (u: AdminUser) => void;
  onChanged: () => void;
  onMessage: (m: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function createUser() {
    setBusy(true);
    try {
      const result = await api<{ whitelisted: boolean }>("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          display_name: name.trim() || null,
        }),
      });
      onMessage(
        result.whitelisted
          ? `${email.trim()} tillagd och vitlistad — kan logga in direkt.`
          : `${email.trim()} tillagd. Obs: lägg även till adressen i ` +
              `Cloudflare-vitlistan (eller konfigurera CF-API:t) så hen ` +
              `kommer förbi inloggningen.`
      );
      setEmail("");
      setName("");
      onChanged();
    } catch (e) {
      onMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeUser(u: AdminUser) {
    if (
      !window.confirm(
        `Radera ${u.email}?\n\nALL användarens data försvinner: pass, ` +
          `kostloggar, mätningar, foton och utmaningsresultat. ` +
          `Detta går inte att ångra.`
      )
    )
      return;
    try {
      await api(`/api/admin/users/${u.id}`, { method: "DELETE" });
      onMessage(`${u.email} raderad.`);
      onChanged();
    } catch (e) {
      onMessage((e as Error).message);
    }
  }

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <h2 className="font-bold">Användare</h2>

      <div className="mt-2 flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="e-postadress"
          className="min-w-0 flex-[3] rounded-xl border border-stone-300 bg-transparent px-3 py-2 text-sm dark:border-stone-700"
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="namn (valfritt)"
          className="min-w-0 flex-[2] rounded-xl border border-stone-300 bg-transparent px-3 py-2 text-sm dark:border-stone-700"
        />
        <button
          disabled={busy || !email.includes("@")}
          onClick={createUser}
          className="rounded-xl bg-emerald-600 px-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          +
        </button>
      </div>

      <ul className="mt-2 divide-y divide-stone-100 dark:divide-stone-800">
        {users.map((u) => (
          <li key={u.id} className="flex items-center justify-between py-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">
                {u.display_name ?? u.email.split("@")[0]}
                {u.is_admin && (
                  <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                    admin
                  </span>
                )}
              </p>
              <p className="truncate text-xs text-stone-400">{u.email}</p>
            </div>
            {meId && u.id !== meId && (
              <div className="flex shrink-0 gap-1.5">
                <button
                  onClick={() => onToggleAdmin(u)}
                  className="rounded-lg border border-stone-300 px-2 py-1 text-xs font-medium dark:border-stone-700"
                >
                  {u.is_admin ? "Ta bort admin" : "Gör admin"}
                </button>
                <button
                  onClick={() => removeUser(u)}
                  className="rounded-lg border border-red-200 px-2 py-1 text-xs font-medium text-red-600 dark:border-red-900 dark:text-red-400"
                  aria-label={`Radera ${u.email}`}
                >
                  🗑
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function TestersSection({ onMessage }: { onMessage: (m: string) => void }) {
  const [data, setData] = useState<TestersData | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    api<TestersData>("/api/admin/testers").then(setData).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  async function invite() {
    setBusy(true);
    try {
      await api("/api/admin/testers", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      onMessage(
        `${email.trim()} är vitlistad — de kan logga in direkt på appens adress.`
      );
      setEmail("");
      refresh();
    } catch (e) {
      onMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(target: string) {
    if (!window.confirm(`Ta bort ${target} från vitlistan?`)) return;
    try {
      await api(`/api/admin/testers/${encodeURIComponent(target)}`, {
        method: "DELETE",
      });
      refresh();
    } catch (e) {
      onMessage((e as Error).message);
    }
  }

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
      <h2 className="font-bold">Externa testare</h2>

      {data && !data.configured && (
        <div className="mt-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <p className="font-semibold">Cloudflare-API:t är inte konfigurerat.</p>
          <p className="mt-1">
            Skapa en API-token i Cloudflare med behörigheten{" "}
            <em>Access: Apps and Policies – Edit</em> och sätt{" "}
            <code className="rounded bg-black/10 px-1">CF_API_TOKEN</code>,{" "}
            <code className="rounded bg-black/10 px-1">CF_ACCOUNT_ID</code> och{" "}
            <code className="rounded bg-black/10 px-1">CF_ACCESS_APP_ID</code>{" "}
            i .env. Tills dess läggs testare till manuellt i Zero
            Trust-dashboarden (Access → Applications → din policy).
          </p>
        </div>
      )}

      {data?.configured && (
        <>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
            Vitlistade adresser kan logga in direkt — kontot skapas
            automatiskt vid första inloggningen.
          </p>
          <div className="mt-2 flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="testarens e-postadress"
              className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-transparent px-3 py-2 text-sm dark:border-stone-700"
            />
            <button
              disabled={busy || !email.includes("@")}
              onClick={invite}
              className="rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-white disabled:opacity-40"
            >
              Bjud in
            </button>
          </div>

          <ul className="mt-3 divide-y divide-stone-100 dark:divide-stone-800">
            {data.testers.map((t) => (
              <li
                key={t.email}
                className="flex items-center justify-between py-2"
              >
                <div>
                  <p className="text-sm font-medium">
                    {t.display_name ?? t.email}
                  </p>
                  <p className="text-xs text-stone-400">
                    {t.display_name ? `${t.email} · ` : ""}
                    {t.has_logged_in ? "✅ har loggat in" : "⏳ inte inloggad ännu"}
                  </p>
                </div>
                <button
                  onClick={() => remove(t.email)}
                  className="px-2 text-stone-400 hover:text-red-500"
                  aria-label="Ta bort"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
