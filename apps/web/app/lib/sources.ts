/** Enhetliga svenska etiketter för datakällor — visas överallt där
 * siffror kan komma från mer än ett håll. */
const LABELS: Record<string, string> = {
  withings: "Withings",
  strava: "Strava",
  apple_health: "Apple Health",
  manual: "Manuellt",
  shapiqo: "Shapiqo",
  off: "Livsmedelsdatabasen",
  base: "Förslag",
  custom: "Eget livsmedel",
};

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "";
  return LABELS[source] ?? source;
}
