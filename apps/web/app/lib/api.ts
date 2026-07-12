export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `Fel ${res.status}`
    );
  }
  return body as T;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("sv-SE", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(iso));
}

export function formatWeight(kg: number | null): string {
  if (kg === null) return "–";
  return `${Number.isInteger(kg) ? kg : kg.toFixed(1)} kg`;
}
