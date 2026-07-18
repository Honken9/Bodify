"use client";

type Point = { x: number; y: number };

/** Catmull-Rom → kubisk bezier: mjukar ut linjen utan att missa punkterna. */
function smoothPath(pts: Point[]): string {
  if (pts.length < 2) return "";
  if (pts.length === 2)
    return `M${pts[0].x},${pts[0].y} L${pts[1].x},${pts[1].y}`;
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

export default function LineChart({
  data,
  height = 180,
  unit,
  goalValue,
  bars = false,
  decimals = 1,
}: {
  data: { measured_at: string; value: number }[];
  height?: number;
  unit?: string;
  goalValue?: number | null;
  bars?: boolean; // staplar (t.ex. steg) i stället för linje
  decimals?: number;
}) {
  if (data.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-faint">Ingen data ännu.</p>
    );
  }

  const width = 340;
  const pad = { top: 18, right: 10, bottom: 20, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const xs = data.map((d) => new Date(d.measured_at).getTime());
  const ys = data.map((d) => d.value);
  const allYs = goalValue != null ? [...ys, goalValue] : ys;

  const dataMin = Math.min(...ys);
  const dataMax = Math.max(...ys);
  // Staplar utgår från 0; linjer zoomar in på spannet med lite luft
  const rawMin = bars ? 0 : Math.min(...allYs);
  const rawMax = Math.max(...allYs);
  const padY = bars ? rawMax * 0.06 : (rawMax - rawMin || 1) * 0.08;
  const yMin = bars ? 0 : rawMin - padY;
  const yMax = rawMax + padY || 1;
  const ySpan = yMax - yMin || 1;

  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const xSpan = xMax - xMin || 1;

  const toY = (v: number) => pad.top + (1 - (v - yMin) / ySpan) * plotH;
  const toXY = (t: number, v: number): Point => ({
    x: pad.left + ((t - xMin) / xSpan) * plotW,
    y: toY(v),
  });

  const points = data.map((d) =>
    toXY(new Date(d.measured_at).getTime(), d.value)
  );

  const maxIdx = ys.indexOf(dataMax);
  const minIdx = ys.indexOf(dataMin);
  const fmtVal = (v: number) =>
    v >= 1000 ? Math.round(v).toLocaleString("sv-SE") : v.toFixed(decimals);

  const yTicks = [yMin, yMin + ySpan / 3, yMin + (2 * ySpan) / 3, yMax];
  const fmtDate = new Intl.DateTimeFormat("sv-SE", {
    day: "numeric",
    month: "short",
  });
  const goalY = goalValue != null ? toY(goalValue) : null;

  // Håll etiketter innanför kanterna
  const clampX = (x: number) => Math.min(Math.max(x, pad.left + 14), width - pad.right - 14);

  const barW = Math.max(2, Math.min(18, (plotW / data.length) * 0.7));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full text-navy" role="img">
      {yTicks.map((v, i) => {
        const y = toY(v);
        return (
          <g key={i}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y}
              y2={y}
              className="stroke-line dark:stroke-night-shell"
              strokeWidth="1"
            />
            <text
              x={pad.left - 5}
              y={y + 3}
              textAnchor="end"
              className="fill-faint text-[9px]"
            >
              {ySpan >= 1000
                ? `${Math.round(v / 1000)}k`
                : v.toFixed(ySpan < 5 ? 1 : 0)}
            </text>
          </g>
        );
      })}

      {goalY != null && goalY > pad.top && goalY < height - pad.bottom && (
        <g>
          <line
            x1={pad.left}
            x2={width - pad.right}
            y1={goalY}
            y2={goalY}
            className="stroke-lime-deep"
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
          <text
            x={width - pad.right}
            y={goalY - 3}
            textAnchor="end"
            className="fill-lime-deep text-[9px] font-semibold"
          >
            mål
          </text>
        </g>
      )}

      {bars ? (
        points.map((p, i) => (
          <rect
            key={i}
            x={p.x - barW / 2}
            y={p.y}
            width={barW}
            height={Math.max(0, height - pad.bottom - p.y)}
            rx={Math.min(3, barW / 3)}
            className={i === maxIdx ? "fill-lime" : "fill-navy/70"}
          />
        ))
      ) : (
        <>
          {/* Mjuk yta under linjen gör trenden lättare att läsa */}
          <path
            d={`${smoothPath(points)} L${points[points.length - 1].x},${height - pad.bottom} L${points[0].x},${height - pad.bottom} Z`}
            fill="currentColor"
            opacity="0.07"
          />
          <path
            d={smoothPath(points)}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          {points.length <= 60 &&
            points.map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={i === maxIdx || i === minIdx ? 0 : 2}
                fill="currentColor"
                opacity="0.75"
              />
            ))}
        </>
      )}

      {/* Max- och min-markeringar med värde */}
      <g>
        <circle
          cx={points[maxIdx].x}
          cy={points[maxIdx].y}
          r="3.5"
          className="fill-lime-deep"
          stroke="white"
          strokeWidth="1.2"
        />
        <text
          x={clampX(points[maxIdx].x)}
          y={Math.max(pad.top - 6, points[maxIdx].y - 7) + 0}
          textAnchor="middle"
          className="fill-lime-deep text-[9px] font-bold"
        >
          ▲ {fmtVal(dataMax)}
        </text>
      </g>
      {minIdx !== maxIdx && !bars && (
        <g>
          <circle
            cx={points[minIdx].x}
            cy={points[minIdx].y}
            r="3.5"
            className="fill-fat"
            stroke="white"
            strokeWidth="1.2"
          />
          <text
            x={clampX(points[minIdx].x)}
            y={Math.min(height - pad.bottom + 12, points[minIdx].y + 14)}
            textAnchor="middle"
            className="fill-fat text-[9px] font-bold"
          >
            ▼ {fmtVal(dataMin)}
          </text>
        </g>
      )}

      <text x={pad.left} y={height - 4} className="fill-faint text-[9px]">
        {fmtDate.format(new Date(xMin))}
      </text>
      <text
        x={width - pad.right}
        y={height - 4}
        textAnchor="end"
        className="fill-faint text-[9px]"
      >
        {fmtDate.format(new Date(xMax))}
      </text>
      {unit && (
        <text
          x={width - pad.right}
          y={pad.top - 8}
          textAnchor="end"
          className="fill-faint text-[9px]"
        >
          {unit}
        </text>
      )}
    </svg>
  );
}
