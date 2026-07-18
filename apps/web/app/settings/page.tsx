"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

type IntegrationsStatus = {
  providers: {
    provider: string;
    connected: boolean;
    status: string | null;
    since: string | null;
  }[];
  apple_health_tokens: {
    id: string;
    label: string;
    created_at: string;
    last_seen_at: string | null;
  }[];
};

const PROVIDER_META: Record<string, { name: string; blurb: string }> = {
  strava: {
    name: "Strava",
    blurb: "Löprundor och cykelturer synkas automatiskt när de laddas upp.",
  },
  withings: {
    name: "Withings",
    blurb: "Vikt, kroppsfett, muskelmassa, vatten och PWV från din våg.",
  },
};

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function PushSection({ onError }: { onError: (m: string) => void }) {
  const [state, setState] = useState<"unknown" | "on" | "off" | "unsupported">(
    "unknown"
  );

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setState("unsupported");
      return;
    }
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setState(sub ? "on" : "off"))
      .catch(() => setState("off"));
  }, []);

  async function enable() {
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        onError("Notistillstånd nekades i webbläsaren.");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const { key } = await api<{ key: string }>("/api/push/vapid-public-key");
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key) as BufferSource,
      });
      await api("/api/push/subscriptions", {
        method: "POST",
        body: JSON.stringify(sub.toJSON()),
      });
      setState("on");
    } catch (e) {
      onError((e as Error).message);
    }
  }

  async function disable() {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await api("/api/push/subscriptions", {
        method: "DELETE",
        body: JSON.stringify(sub.toJSON()),
      }).catch(() => {});
      await sub.unsubscribe();
    }
    setState("off");
  }

  return (
    <section className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
      <h2 className="font-bold">Push-notiser</h2>
      <p className="mt-1 text-sm text-muted dark:text-faint">
        Påminnelser, utmaningsuppdateringar och coach-råd direkt till mobilen.
        På iPhone: lägg först till Shapiqo på hemskärmen (Dela →
        &quot;Lägg till på hemskärmen&quot;).
      </p>
      {state === "unsupported" ? (
        <p className="mt-3 text-sm text-sand-ink dark:text-lime">
          Webbläsaren stöder inte push (öppna appen från hemskärmen på iOS).
        </p>
      ) : (
        <button
          onClick={state === "on" ? disable : enable}
          disabled={state === "unknown"}
          className={`mt-3 w-full rounded-xl py-2.5 font-semibold ${
            state === "on"
              ? "border border-line-strong text-muted dark:border-night-strong dark:text-night-muted"
              : "bg-navy text-white"
          }`}
        >
          {state === "on" ? "Stäng av push-notiser" : "Aktivera push-notiser"}
        </button>
      )}
    </section>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [newToken, setNewToken] = useState<{
    token: string;
    endpoint: string;
  } | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [syncMsg, setSyncMsg] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<IntegrationsStatus>("/api/integrations")
      .then(setStatus)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function connect(provider: string) {
    try {
      const { url } = await api<{ url: string }>(
        `/api/integrations/${provider}/connect`
      );
      window.location.href = url;
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function disconnect(provider: string) {
    if (!window.confirm(`Koppla från ${PROVIDER_META[provider]?.name}?`)) return;
    await api(`/api/integrations/${provider}`, { method: "DELETE" });
    refresh();
  }

  async function syncNow(provider: string) {
    setSyncing(provider);
    setSyncMsg((m) => ({ ...m, [provider]: "" }));
    try {
      const res = await api<{
        measures?: number;
        workouts?: number;
        step_days?: number;
        imported?: number;
      }>(`/api/integrations/${provider}/sync`, { method: "POST" });
      const parts: string[] = [];
      if (res.measures) parts.push(`${res.measures} mätvärden`);
      if (res.workouts) parts.push(`${res.workouts} pass`);
      if (res.step_days) parts.push(`steg för ${res.step_days} dagar`);
      if (res.imported) parts.push(`${res.imported} aktiviteter`);
      setSyncMsg((m) => ({
        ...m,
        [provider]:
          parts.length > 0
            ? `✅ Hämtat: ${parts.join(", ")}`
            : "✅ Redan i kapp — inget nytt hos källan ännu.",
      }));
    } catch (e) {
      setSyncMsg((m) => ({ ...m, [provider]: `⚠️ ${(e as Error).message}` }));
    } finally {
      setSyncing(null);
    }
  }

  async function createToken() {
    const created = await api<{ token: string; endpoint: string }>(
      "/api/integrations/apple-health/tokens",
      { method: "POST", body: JSON.stringify({ label: "Apple Health" }) }
    );
    setNewToken(created);
    refresh();
  }

  async function revokeToken(id: string) {
    await api(`/api/integrations/apple-health/tokens/${id}`, {
      method: "DELETE",
    });
    refresh();
  }

  return (
    <main className="mx-auto flex max-w-md flex-col desktop:max-w-4xl gap-4 p-5">
      <h1 className="pt-2 text-2xl font-bold">Kopplingar</h1>
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {status?.providers.map((p) => {
        const meta = PROVIDER_META[p.provider];
        return (
          <section
            key={p.provider}
            className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-bold">{meta?.name ?? p.provider}</h2>
              {p.connected ? (
                <span className="rounded-full bg-navy-soft px-2.5 py-0.5 text-xs font-semibold text-navy-deep dark:bg-night-shell dark:text-lime">
                  Kopplad
                </span>
              ) : (
                <span className="rounded-full bg-shell px-2.5 py-0.5 text-xs text-muted dark:bg-night-shell">
                  Ej kopplad
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-muted dark:text-faint">
              {meta?.blurb}
            </p>
            {p.connected ? (
              <>
                <button
                  disabled={syncing === p.provider}
                  onClick={() => syncNow(p.provider)}
                  className="mt-3 w-full rounded-xl bg-navy py-2.5 font-semibold text-white disabled:opacity-50"
                >
                  {syncing === p.provider ? "Synkar…" : "🔄 Synka nu"}
                </button>
                {syncMsg[p.provider] && (
                  <p className="mt-2 text-xs text-muted dark:text-faint">
                    {syncMsg[p.provider]}
                  </p>
                )}
                <button
                  onClick={() => disconnect(p.provider)}
                  className="mt-2 w-full rounded-xl border border-line-strong py-2.5 font-semibold text-muted dark:border-night-strong dark:text-night-muted"
                >
                  Koppla från
                </button>
              </>
            ) : (
              <button
                onClick={() => connect(p.provider)}
                className="mt-3 w-full rounded-xl bg-navy py-2.5 font-semibold text-white"
              >
                Anslut {meta?.name}
              </button>
            )}
          </section>
        );
      })}

      <section className="rounded-2xl border border-line bg-white p-5 dark:border-night-shell dark:bg-night-card">
        <h2 className="font-bold">Apple Health</h2>
        <p className="mt-1 text-sm text-muted dark:text-faint">
          Synka sömn, HRV, steg och träningspass via appen{" "}
          <strong>Health Auto Export</strong> på din iPhone:
        </p>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-muted dark:text-night-muted">
          <li>Skapa en token nedan (visas bara en gång).</li>
          <li>I HAE: skapa en automation av typen &quot;REST API&quot;.</li>
          <li>
            Klistra in endpoint-URL:en och lägg till headern{" "}
            <code className="rounded bg-shell px-1 dark:bg-night-shell">
              Authorization: Bearer &lt;din token&gt;
            </code>
          </li>
          <li>Välj mätvärden (sömn, HRV, vilopuls, steg, pass) och schema.</li>
        </ol>

        {newToken && (
          <div className="mt-3 rounded-xl border-2 border-sand-strong bg-sand p-3 dark:border-night-strong dark:bg-night-shell">
            <p className="text-xs font-semibold text-sand-ink dark:text-lime">
              Spara nu — visas inte igen!
            </p>
            <p className="mt-1 break-all font-mono text-sm">{newToken.token}</p>
            <p className="mt-1 break-all text-xs text-muted">
              Endpoint: {newToken.endpoint}
            </p>
            <button
              onClick={() =>
                navigator.clipboard?.writeText(newToken.token)
              }
              className="mt-2 rounded-lg bg-sand-ink px-3 py-1.5 text-xs font-semibold text-white"
            >
              Kopiera token
            </button>
          </div>
        )}

        <ul className="mt-3 space-y-2">
          {status?.apple_health_tokens.map((t) => (
            <li
              key={t.id}
              className="flex items-center justify-between rounded-xl bg-cream-deep px-3 py-2 text-sm dark:bg-night-shell/60"
            >
              <div>
                <p className="font-medium">{t.label}</p>
                <p className="text-xs text-faint">
                  {t.last_seen_at
                    ? `Senast använd ${new Intl.DateTimeFormat("sv-SE", {
                        dateStyle: "short",
                        timeStyle: "short",
                      }).format(new Date(t.last_seen_at))}`
                    : "Aldrig använd ännu"}
                </p>
              </div>
              <button
                onClick={() => revokeToken(t.id)}
                className="px-2 text-faint hover:text-red-500"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>

        <button
          onClick={createToken}
          className="mt-3 w-full rounded-xl bg-navy py-2.5 font-semibold text-white"
        >
          Skapa ny token
        </button>
      </section>

      <PushSection onError={setError} />
    </main>
  );
}
