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

function fmt(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = String(totalSeconds % 60).padStart(2, "0");
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${s}`;
  return `${m}:${s}`;
}

export default function WorkoutHUD({
  startedAt,
  exerciseName,
  exerciseIndex,
  exerciseTotal,
  setsDone,
  targetSets,
  targetReps,
  restSeconds,
  restKey,
  onRestDone,
}: {
  startedAt: string;
  exerciseName: string | null;
  exerciseIndex: number; // 1-baserad; 0 = allt klart
  exerciseTotal: number;
  setsDone: number;
  targetSets: number | null;
  targetReps: string | null;
  restSeconds: number | null;
  restKey: number;
  onRestDone: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);
  const [restLeft, setRestLeft] = useState<number | null>(null);
  const restEndRef = useRef<number>(0);

  // Total passtid
  useEffect(() => {
    const started = new Date(startedAt).getTime();
    const tick = () =>
      setElapsed(Math.max(0, Math.floor((Date.now() - started) / 1000)));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  // Vilonedräkning
  useEffect(() => {
    if (restSeconds === null) {
      setRestLeft(null);
      return;
    }
    restEndRef.current = Date.now() + restSeconds * 1000;
    setRestLeft(restSeconds);
    const interval = setInterval(() => {
      const left = Math.max(
        0,
        Math.round((restEndRef.current - Date.now()) / 1000)
      );
      setRestLeft(left);
      if (left === 0) {
        clearInterval(interval);
        beep();
        navigator.vibrate?.([200, 100, 200]);
        onRestDone();
      }
    }, 250);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restKey, restSeconds]);

  const resting = restLeft !== null && restSeconds !== null;
  const allDone = exerciseIndex === 0;

  return (
    <div className="sticky top-0 z-30 -mx-5 bg-cream/95 px-5 pb-2 pt-2 backdrop-blur dark:bg-night/95">
      <div
        className={`rounded-2xl p-4 shadow-card transition-colors ${
          resting
            ? "bg-navy text-white"
            : "bg-ink text-white dark:bg-shell dark:text-night-card"
        }`}
      >
        <div className="flex items-baseline justify-between text-[11px] font-semibold uppercase tracking-wide opacity-70">
          <span>
            {allDone
              ? "Pass"
              : `Övning ${exerciseIndex} av ${exerciseTotal}`}
          </span>
          <span className="font-mono tabular-nums">⏱ {fmt(elapsed)}</span>
        </div>

        {resting ? (
          <div className="mt-1 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-medium opacity-80">
                Vila{exerciseName ? ` · nästa: ${exerciseName}` : ""}
              </p>
              <p className="font-mono text-4xl font-bold tabular-nums leading-tight text-lime">
                {fmt(restLeft)}
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-1.5">
              <button
                onClick={() => {
                  restEndRef.current += 30_000;
                  setRestLeft((r) => (r === null ? r : r + 30));
                }}
                className="rounded-lg bg-white/20 px-3 py-1.5 text-sm font-semibold"
              >
                +30 s
              </button>
              <button
                onClick={onRestDone}
                className="rounded-lg bg-white/20 px-3 py-1.5 text-sm font-semibold"
              >
                Hoppa över
              </button>
            </div>
          </div>
        ) : allDone ? (
          <p className="mt-1 text-xl font-bold">
            Alla planerade set klara! 🎉
          </p>
        ) : (
          <div className="mt-1">
            <p className="truncate text-xl font-bold">{exerciseName}</p>
            <p className="text-sm opacity-80">
              Set {setsDone + 1}
              {targetSets ? ` av ${targetSets}` : ""}
              {targetReps ? ` · mål ${targetReps} reps` : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
