"use client";

import { useEffect, useRef, useState } from "react";

/** Webbkamera-läge för datorer: mobilens filväljare kan öppna kameran
 * direkt, men på en dator måste vi själva visa videoströmmen och knäppa. */
export default function CameraCapture({
  onCapture,
  onClose,
}: {
  onCapture: (photo: Blob) => void;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 } },
      })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
        setReady(true);
      })
      .catch(() =>
        setError(
          "Kunde inte starta kameran — kontrollera att webbläsaren har kamerabehörighet."
        )
      );
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function snap() {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (blob) onCapture(blob);
      },
      "image/jpeg",
      0.9
    );
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-3xl bg-white p-4 dark:bg-night-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex items-center justify-between">
          <h3 className="font-bold">📷 Ta en bild</h3>
          <button onClick={onClose} className="p-1 text-faint">
            ✕
          </button>
        </div>
        {error ? (
          <p className="py-8 text-center text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : (
          <>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              ref={videoRef}
              playsInline
              muted
              className="w-full rounded-xl bg-black"
            />
            <button
              disabled={!ready}
              onClick={snap}
              className="mt-3 w-full rounded-xl bg-navy py-3 font-semibold text-white disabled:opacity-40"
            >
              Ta bilden
            </button>
          </>
        )}
      </div>
    </div>
  );
}
