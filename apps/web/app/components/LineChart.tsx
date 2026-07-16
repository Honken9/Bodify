"use client";

type Point = { x: number; y: number };

export default function LineChart({
  data,
  height = 160,
  unit,
  goalValue,
}: {
  data: { measured_at: string; value: number }[];
  height?: number;
  unit?: string;
  goalValue?: number | null;
}) {
  if (data.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-faint">
        Ingen data ännu.
      </p>
    );
  }

  const width = 340;
  const pad = { top: 10, right: 8, bottom: 20, left: 38 };

  const xs = data.map((d) => new Date(d.measured_at).getTime());
  const ys = data.map((d) => d.value);
  const allYs = goalValue != null ? [...ys, goalValue] : ys;
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...allYs);
  const yMax = Math.max(...allYs);
  const ySpan = yMax - yMin || 1;
  const xSpan = xMax - xMin || 1;

  const toXY = (t: number, v: number): Point => ({
    x: pad.left + ((t - xMin) / xSpan) * (width - pad.left - pad.right),
    y:
      pad.top +
      (1 - (v - yMin) / ySpan) * (height - pad.top - pad.bottom),
  });

  const points = data.map((d) =>
    toXY(new Date(d.measured_at).getTime(), d.value)
  );
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");

  const yTicks = [yMin, (yMin + yMax) / 2, yMax];
  const first = new Date(xMin);
  const last = new Date(xMax);
  const fmt = new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "short" });

  const goalY = goalValue != null ? toXY(xMin, goalValue).y : null;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full text-sage"
      role="img"
    >
      {yTicks.map((v) => {
        const y = toXY(xMin, v).y;
        return (
          <g key={v}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y}
              y2={y}
              className="stroke-stone-200 dark:stroke-stone-800"
              strokeWidth="1"
            />
            <text
              x={pad.left - 4}
              y={y + 3}
              textAnchor="end"
              className="fill-stone-400 text-[9px]"
            >
              {v.toFixed(ySpan < 5 ? 1 : 0)}
            </text>
          </g>
        );
      })}

      {goalY != null && (
        <line
          x1={pad.left}
          x2={width - pad.right}
          y1={goalY}
          y2={goalY}
          className="stroke-emerald-500"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
      )}

      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
      {points.length <= 40 &&
        points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="currentColor" />
        ))}

      <text
        x={pad.left}
        y={height - 4}
        className="fill-stone-400 text-[9px]"
      >
        {fmt.format(first)}
      </text>
      <text
        x={width - pad.right}
        y={height - 4}
        textAnchor="end"
        className="fill-stone-400 text-[9px]"
      >
        {fmt.format(last)}
      </text>
      {unit && (
        <text x={width - pad.right} y={pad.top + 2} textAnchor="end" className="fill-stone-400 text-[9px]">
          {unit}
        </text>
      )}
    </svg>
  );
}
