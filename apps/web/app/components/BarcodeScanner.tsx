"use client";

import { useEffect, useRef, useState } from "react";
import { Html5Qrcode, Html5QrcodeSupportedFormats } from "html5-qrcode";

/* Optimerad för matvarustreckkoder:
   - Bara EAN/UPC avkodas (i stället för ~15 format) → mycket färre
     beräkningar per bildruta
   - Webbläsarens inbyggda BarcodeDetector används där den finns
     (Chrome/Android m.fl.) → nära omedelbar träff
   - Högre kameraupplösning och tätare avsökning → små/böjda koder hittas
   - Bred sökruta som matchar streckkodens form
   - Ficklampsknapp där kameran stödjer det + manuell inmatning som
     reservväg när koden är repig eller ljuset dåligt */

export default function BarcodeScanner({
  onDetected,
  onError,
}: {
  onDetected: (code: string) => void;
  onError: (message: string) => void;
}) {
  const containerId = "shapiqo-scanner";
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const detectedRef = useRef(false);
  const [starting, setStarting] = useState(true);
  const [torchAvailable, setTorchAvailable] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [manual, setManual] = useState("");

  useEffect(() => {
    const scanner = new Html5Qrcode(containerId, {
      formatsToSupport: [
        Html5QrcodeSupportedFormats.EAN_13,
        Html5QrcodeSupportedFormats.EAN_8,
        Html5QrcodeSupportedFormats.UPC_A,
        Html5QrcodeSupportedFormats.UPC_E,
      ],
      // Native BarcodeDetector när webbläsaren har en — stor skillnad
      experimentalFeatures: { useBarCodeDetectorIfSupported: true },
      verbose: false,
    });
    scannerRef.current = scanner;

    scanner
      .start(
        { facingMode: "environment" },
        {
          fps: 15,
          // Bred och låg ruta — streckkodens form
          qrbox: (w, h) => ({
            width: Math.min(Math.round(w * 0.85), 500),
            height: Math.min(Math.round(h * 0.45), 200),
          }),
          videoConstraints: {
            facingMode: "environment",
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        },
        (text) => {
          if (detectedRef.current) return;
          if (!/^\d{6,14}$/.test(text)) return; // brus/QR ignoreras
          detectedRef.current = true;
          if (navigator.vibrate) navigator.vibrate(60);
          onDetected(text);
        },
        () => {} // per-frame-missar är normala, ignorera
      )
      .then(() => {
        setStarting(false);
        try {
          const caps = scanner.getRunningTrackCapabilities() as
            | (MediaTrackCapabilities & { torch?: boolean })
            | undefined;
          if (caps?.torch) setTorchAvailable(true);
        } catch {
          /* ficklampa är trevligt men inte nödvändigt */
        }
      })
      .catch(() =>
        onError(
          "Kunde inte starta kameran. Kontrollera att webbläsaren har kamerabehörighet."
        )
      );

    return () => {
      const s = scannerRef.current;
      if (s && s.isScanning) {
        s.stop().then(() => s.clear()).catch(() => {});
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function toggleTorch() {
    const s = scannerRef.current;
    if (!s) return;
    const next = !torchOn;
    try {
      await s.applyVideoConstraints({
        advanced: [{ torch: next }],
      } as unknown as MediaTrackConstraints);
      setTorchOn(next);
    } catch {
      setTorchAvailable(false);
    }
  }

  function submitManual() {
    const code = manual.replace(/\D/g, "");
    if (code.length >= 6 && !detectedRef.current) {
      detectedRef.current = true;
      onDetected(code);
    }
  }

  return (
    <div>
      <div className="relative">
        <div id={containerId} className="overflow-hidden rounded-xl" />
        {torchAvailable && !starting && (
          <button
            onClick={toggleTorch}
            className={`absolute bottom-2 right-2 rounded-full px-3 py-2 text-lg ${
              torchOn ? "bg-lime text-lime-ink" : "bg-black/50 text-white"
            }`}
            aria-label="Ficklampa"
          >
            🔦
          </button>
        )}
      </div>
      {starting && (
        <p className="py-6 text-center text-sm text-faint">Startar kameran…</p>
      )}
      <p className="mt-2 text-center text-xs text-faint">
        Håll streckkoden i rutan, 10–15 cm från kameran
      </p>

      <div className="mt-3 flex gap-2">
        <input
          inputMode="numeric"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitManual()}
          placeholder="…eller skriv sifferkoden"
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-transparent px-3 py-2 text-sm dark:border-night-strong"
        />
        <button
          onClick={submitManual}
          disabled={manual.replace(/\D/g, "").length < 6}
          className="rounded-xl bg-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Sök
        </button>
      </div>
    </div>
  );
}
