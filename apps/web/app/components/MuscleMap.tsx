"use client";

/* Muskelkarta: anatomisk kropp fram + bak där tränade muskelgrupper
   lyser (lime). Ritad i SVG — halva figuren definieras och speglas,
   så båda sidor alltid är symmetriska. */

const ACTIVE = "fill-lime-deep stroke-lime-deep";
const IDLE = "fill-line stroke-line-strong/70 dark:fill-night-shell dark:stroke-night-strong";
const BODY =
  "fill-cream-deep stroke-line-strong dark:fill-night-shell/40 dark:stroke-night-strong";
const DETAIL = "stroke-line-strong dark:stroke-night-strong";

/** Spegla alla x-koordinater i en absolut M/L/C/Q-path. */
function mirrorX(d: string, width = 110): string {
  return d.replace(/([MLCQ])([^MLCQZ]*)/gi, (_m, cmd: string, coords: string) => {
    const nums = coords.trim().split(/[\s,]+/).filter(Boolean).map(Number);
    const out: string[] = [];
    for (let i = 0; i < nums.length; i += 2) {
      out.push((width - nums[i]).toFixed(1), String(nums[i + 1]));
    }
    return cmd + " " + out.join(" ") + " ";
  });
}

const HALF_BODY = `M55 21.5 L50 22 C50 25.5 48.8 28 45 29.5 C37 32 31.8 33.4 29.6 38.5 C27.9 42.6 27 47.5 26.3 52.5 C25.6 58 24.8 63.5 23.8 68.8 C22.8 74.8 21.6 80.8 20.8 86.4 C20.4 89.4 20 92 20 94.6 L25.6 95.6 C26.5 90.4 27.4 84.8 28.4 79.4 C29.4 74 30.6 69 31.6 65 C32.6 60.6 33.2 55.2 33.7 50.2 L34.6 46.4 C33.6 52.4 33.4 58.4 34.3 64.2 C35.1 69.6 36.7 73.6 38.6 76.6 C40.2 79.2 40.6 82.6 40.6 86 C40.6 90 40 93.2 39.4 96.2 C38.2 102.4 37.6 110.2 38 118 C38.3 125.8 38.9 133 39.7 139 C40.3 144 40.6 148.2 40.4 152.2 C40.2 158.2 40.1 164.2 41 170 C41.9 175.8 42.7 181 43.3 186 L43.6 191.5 L49.5 191.5 C49.9 185.5 50 179.7 49.7 174 C49.4 168.8 48.9 163.8 48.9 158.8 C48.9 152.2 49.2 146.2 49.7 141 C50.3 133 50.7 124.2 50.5 116.2 C50.4 109.2 50.1 102.2 49.5 97 L55 95.6 Z`;

const SHOULDER = `M29.8 38.6 C31.4 34.4 36 32.6 39.8 33.3 C42.9 34 44.4 36.4 43.9 39.4 C43.4 42.3 41 44.3 38 44.8 C33.6 45.4 30.6 43.1 29.8 38.6 Z`;
const UPPER_ARM = `M27.6 49.8 C29.6 47.6 32 48.6 32.8 52.2 C33.6 56.4 33 61.8 31.6 65.8 C30.2 69.6 27.6 69.6 26.6 65.8 C25.6 61.4 26.2 53.8 27.6 49.8 Z`;
const FOREARM = `M23.6 71 C25.6 68.8 28 69.8 28.6 72.8 C29.1 76.8 28 82.8 26.6 87.8 C25.7 91 23.7 91 22.9 87.8 C22 83.4 22.4 75.8 23.6 71 Z`;

const FRONT: [string, string[]][] = [
  [SHOULDER, ["axlar"]],
  [`M54.8 39.8 L44.8 39.2 C41.8 40.8 40.7 44.2 41.2 47.8 C41.9 52.4 45.6 55.4 50 55.9 C52 56.1 53.9 55.7 54.8 54.4 Z`, ["bröst"]],
  [UPPER_ARM, ["biceps"]],
  [FOREARM, ["underarmar"]],
  [`M54.8 58.2 L48.6 58.6 C46.6 62.2 46.1 68 46.6 74 C47.1 80 49 85 51.6 88 C53 89.6 54.8 90.2 54.8 90.2 Z`, ["mage"]],
  [`M45.2 59.4 C43.4 62.8 42.9 68 43.8 73 C44.5 76.6 45.9 79.4 47.2 80.6 C46 76 45.7 70 46 65 C46.2 62.6 46.6 60.6 47.2 59 Z`, ["mage"]],
  [`M38.6 99.8 C36.9 107.8 36.7 117.8 37.7 126.8 C38.5 133.8 40.1 138.8 41.7 140.8 C43.1 142.4 44.7 141.8 45.1 139.4 C45.3 137.4 44.9 133.8 44.7 129.8 L44.3 103.8 C43.1 100.4 40.6 98.4 38.6 99.8 Z`, ["ben"]],
  [`M45.7 103.8 L45.9 129.8 C45.9 133.8 46.1 137.8 47.3 139.8 C48.7 141.8 50.1 140.8 50.5 137.8 C51.1 131.8 51.1 121.8 50.5 113.8 C50.1 107.8 48.7 103.4 47.1 101.8 C46.3 101 45.7 102 45.7 103.8 Z`, ["ben"]],
];

const BACK: [string, string[]][] = [
  [`M54.8 25.5 L48.6 26.5 C45.6 27.6 44.1 30 44.6 32.6 L47.2 35.4 C50.2 37.8 52.6 40.6 54.8 43.5 Z`, ["traps"]],
  [SHOULDER, ["axlar"]],
  [`M54.8 44 L44.4 41.6 C41.9 43.6 40.9 47.6 41.4 51.6 C42.2 57.6 44.9 63.6 48.9 67.6 C51.3 70 53.5 71.6 54.8 72 Z`, ["rygg"]],
  [`M54.8 70 L49.7 71 C48.7 74 48.7 78 49.7 81.4 L54.8 82.8 Z`, ["ländrygg", "rygg"]],
  [UPPER_ARM, ["triceps"]],
  [FOREARM, ["underarmar"]],
  [`M54.8 84.8 L47.4 85.4 C44.4 86.8 43.4 90.4 43.9 93.8 C44.5 97.8 47.4 100.4 50.9 100.7 C52.9 100.9 54.4 99.9 54.8 97.9 Z`, ["säte"]],
  [`M38.6 103.8 C37.1 110.8 36.9 119.8 37.9 127.8 C38.7 134 40.1 138.4 41.7 140.2 C43.1 141.8 44.7 141.2 45.1 138.8 C45.3 136.8 44.9 133.4 44.7 129.8 L44.3 107 C43.1 103.8 40.4 102.2 38.6 103.8 Z`, ["ben", "baksida lår"]],
  [`M45.7 107 L45.9 129.8 C45.9 133.4 46.1 137.2 47.3 139.2 C48.7 141.2 50.1 140.2 50.5 137.2 C51.1 131.4 51.1 122.4 50.5 115 C50.1 109.4 48.7 105.6 47.1 104.2 C46.3 103.4 45.7 105.2 45.7 107 Z`, ["ben", "baksida lår"]],
  [`M41.4 146.8 C39.8 150.8 39.6 156.8 40.4 162.8 C41 167.2 42.4 170.6 43.8 171 C45 171.4 45.8 169.6 46 166.8 L45.8 150 C44.9 146.6 42.9 145.2 41.4 146.8 Z`, ["vader"]],
  [`M46.9 150 L47.1 166.8 C47.3 169.6 48.3 171.2 49.5 170.6 C50.7 170 51.5 166.8 51.7 162.4 C51.9 157.2 51.3 151.6 50.1 148.4 C49.3 146.2 47.7 146.4 46.9 150 Z`, ["vader"]],
];

const FRONT_LINES = [
  "M47 64 L54.8 64",
  "M47 70.5 L54.8 70.5",
  "M47 77 L54.8 77",
  "M44.8 39.4 L54.8 39.8",
  "M42.5 143.5 C43.5 145.5 46 145.7 47.3 143.9",
];
const BACK_LINES = [
  "M54.8 47 L54.8 70",
  "M42.5 143.5 C43.5 145.5 46 145.7 47.3 143.9",
];

function Figure({
  muscles,
  lines,
  on,
}: {
  muscles: [string, string[]][];
  lines: string[];
  on: (...names: string[]) => boolean;
}) {
  return (
    <g strokeWidth="0.6">
      <ellipse cx="55" cy="12.5" rx="7.6" ry="9.2" strokeWidth="0.8" className={BODY} />
      <path d={HALF_BODY} strokeWidth="0.8" className={BODY} />
      <path d={mirrorX(HALF_BODY)} strokeWidth="0.8" className={BODY} />
      {muscles.map(([d, names], i) => {
        const cls = on(...names) ? ACTIVE : IDLE;
        return (
          <g key={i}>
            <path d={d} className={cls} />
            <path d={mirrorX(d)} className={cls} />
          </g>
        );
      })}
      {lines.map((d, i) => (
        <g key={`l${i}`} opacity="0.7">
          <path d={d} fill="none" className={DETAIL} />
          <path d={mirrorX(d)} fill="none" className={DETAIL} />
        </g>
      ))}
    </g>
  );
}

export default function MuscleMap({
  groups,
  height = 150,
}: {
  groups: string[];
  height?: number;
}) {
  const active = new Set(groups.map((g) => g.toLowerCase()));
  const on = (...names: string[]) =>
    active.has("helkropp") || names.some((n) => active.has(n));

  return (
    <svg
      viewBox="0 0 240 210"
      style={{ height }}
      className="mx-auto block"
      role="img"
      aria-label={`Muskler: ${groups.join(", ")}`}
    >
      <Figure muscles={FRONT} lines={FRONT_LINES} on={on} />
      <g transform="translate(125 0)">
        <Figure muscles={BACK} lines={BACK_LINES} on={on} />
      </g>
      <text x="55" y="205" textAnchor="middle" className="fill-faint text-[9px]">
        Framsida
      </text>
      <text x="180" y="205" textAnchor="middle" className="fill-faint text-[9px]">
        Baksida
      </text>
    </svg>
  );
}
