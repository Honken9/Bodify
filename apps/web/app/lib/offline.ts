/** Offline-kö för setloggning — gymkällare har uselt nät.
 *
 * Misslyckas POST:en av nätverksskäl läggs setet i localStorage och
 * synkas när anslutningen är tillbaka (online-event eller nästa besök). */

const KEY = "shapiqo-offline-sets";

export type QueuedSet = {
  sessionId: string;
  body: {
    exercise_id: string;
    weight_kg: number | null;
    reps: number;
  };
  queuedAt: string;
};

export function isNetworkError(e: unknown): boolean {
  if (typeof navigator !== "undefined" && !navigator.onLine) return true;
  const msg = e instanceof Error ? e.message : String(e);
  return /fetch|network|load failed/i.test(msg);
}

export function queuedSets(): QueuedSet[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function enqueueSet(sessionId: string, body: QueuedSet["body"]): void {
  const queue = queuedSets();
  queue.push({ sessionId, body, queuedAt: new Date().toISOString() });
  localStorage.setItem(KEY, JSON.stringify(queue));
}

/** Försök skicka allt i kön. Returnerar antal synkade set. */
export async function flushSets(): Promise<number> {
  const queue = queuedSets();
  if (queue.length === 0) return 0;
  let synced = 0;
  const keep: QueuedSet[] = [];
  for (let i = 0; i < queue.length; i++) {
    const item = queue[i];
    try {
      const res = await fetch(`/api/sessions/${item.sessionId}/sets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.body),
      });
      if (res.ok || res.status === 409 || res.status === 404) {
        synced += 1; // 409/404 = passet avslutat/borta — släng ur kön
      } else {
        keep.push(item);
      }
    } catch {
      keep.push(...queue.slice(i)); // fortfarande offline — behåll resten
      break;
    }
  }
  if (keep.length > 0) localStorage.setItem(KEY, JSON.stringify(keep));
  else localStorage.removeItem(KEY);
  return synced;
}
