"use client";

import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";

export default function BarcodeScanner({
  onDetected,
  onError,
}: {
  onDetected: (code: string) => void;
  onError: (message: string) => void;
}) {
  const containerId = "bodify-scanner";
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const detectedRef = useRef(false);
  const [starting, setStarting] = useState(true);

  useEffect(() => {
    const scanner = new Html5Qrcode(containerId);
    scannerRef.current = scanner;

    scanner
      .start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 150 } },
        (text) => {
          if (detectedRef.current) return;
          detectedRef.current = true;
          onDetected(text);
        },
        () => {} // per-frame-missar är normala, ignorera
      )
      .then(() => setStarting(false))
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

  return (
    <div>
      <div id={containerId} className="overflow-hidden rounded-xl" />
      {starting && (
        <p className="py-6 text-center text-sm text-stone-400">
          Startar kameran…
        </p>
      )}
      <p className="mt-2 text-center text-xs text-stone-400">
        Rikta kameran mot streckkoden
      </p>
    </div>
  );
}
