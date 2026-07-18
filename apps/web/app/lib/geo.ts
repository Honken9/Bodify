/** Hämta position snabbt och tyst — null om användaren nekar, det tar
 * för länge eller webbläsaren saknar stöd. Blockerar aldrig flödet. */
export function quickPosition(
  timeoutMs = 4000
): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve(null);
      return;
    }
    const timer = setTimeout(() => resolve(null), timeoutMs);
    navigator.geolocation.getCurrentPosition(
      (geo) => {
        clearTimeout(timer);
        resolve({ lat: geo.coords.latitude, lng: geo.coords.longitude });
      },
      () => {
        clearTimeout(timer);
        resolve(null);
      },
      { timeout: timeoutMs, maximumAge: 10 * 60 * 1000 }
    );
  });
}
