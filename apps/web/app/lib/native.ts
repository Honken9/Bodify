/** Brygga till Shapiqo-appen (Capacitor). När sidan visas i appens
 * webbvy injicerar Capacitor `window.Capacitor` — då kan webben prata
 * med native-moduler som HealthKit-synken. I vanlig webbläsare är allt
 * här null/false och UI:t för appen renderas inte. */

export type HealthKitCounts = {
  metrics: number;
  sleep: number;
  workouts: number;
  skipped: number;
};

export type HealthKitPlugin = {
  isAvailable(): Promise<{ available: boolean }>;
  configure(opts: { endpoint: string; token: string }): Promise<void>;
  requestAuthorization(): Promise<{ granted: boolean }>;
  sync(opts: { days: number }): Promise<HealthKitCounts>;
  status(): Promise<{ configured: boolean; lastSync?: string }>;
  disable(): Promise<void>;
};

type CapacitorGlobal = {
  isNativePlatform?: () => boolean;
  Plugins?: { HealthKitSync?: HealthKitPlugin };
};

function capacitor(): CapacitorGlobal | null {
  if (typeof window === "undefined") return null;
  return (window as { Capacitor?: CapacitorGlobal }).Capacitor ?? null;
}

export function isNativeApp(): boolean {
  return capacitor()?.isNativePlatform?.() === true;
}

export function healthKit(): HealthKitPlugin | null {
  return capacitor()?.Plugins?.HealthKitSync ?? null;
}
