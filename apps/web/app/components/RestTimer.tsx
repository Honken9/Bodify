"use client";

import { useEffect, useRef, useState } from "react";

function beep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch {
    // ljud är trevligt men inte kritiskt
  }
}

export default function RestTimer({
  seconds,
  onDone,
}: {
  seconds: number;
  onDone: () => void;
}) {
  const [remaining, setRemaining] = useState(seconds);
  const endAtRef = useRef(Date.now() + seconds * 1000);

  useEffect(() => {
    endAtRef.current = Date.now() + seconds * 1000;
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    const interval = setInterval(() => {
      const left = Math.max(
        0,
        Math.round((endAtRef.current - Date.now()) / 1000)
      );
      setRemaining(left);
      if (left === 0) {
        clearInterval(interval);
        beep();
        navigator.vibrate?.([200, 100, 200]);
        onDone();
      }
    }, 250);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mm = Math.floor(remaining / 60);
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <div className="fixed inset-x-0 bottom-14 z-50 mx-auto max-w-md px-4 pb-2">
      <div className="flex items-center justify-between rounded-2xl bg-stone-900 px-5 py-3 text-white shadow-lg dark:bg-stone-100 dark:text-stone-900">
        <span className="text-sm font-medium">Vila</span>
        <span className="font-mono text-2xl font-bold tabular-nums">
          {mm}:{ss}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => {
              endAtRef.current += 30_000;
              setRemaining((r) => r + 30);
            }}
            className="rounded-lg bg-white/20 px-3 py-1 text-sm font-semibold dark:bg-stone-900/20"
          >
            +30 s
          </button>
          <button
            onClick={onDone}
            className="rounded-lg bg-white/20 px-3 py-1 text-sm font-semibold dark:bg-stone-900/20"
          >
            Hoppa över
          </button>
        </div>
      </div>
    </div>
  );
}
