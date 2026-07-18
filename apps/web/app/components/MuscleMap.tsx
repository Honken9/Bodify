"use client";

/* Muskelkarta: stiliserad kropp fram + bak där tränade muskelgrupper
   lyser (lime). Byggd i SVG så den är skarp, lätt och temavänlig. */

const ACTIVE = "fill-lime-deep";
const IDLE = "fill-line dark:fill-night-shell";
const BODY = "fill-cream-deep stroke-line-strong dark:fill-night-shell/40 dark:stroke-night-strong";

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
  const cls = (...names: string[]) => (on(...names) ? ACTIVE : IDLE);

  return (
    <svg
      viewBox="0 0 230 210"
      style={{ height }}
      className="mx-auto block"
      role="img"
      aria-label={`Muskler: ${groups.join(", ")}`}
    >
      {/* ── Framsida ── */}
      <g strokeWidth="1">
        {/* siluett */}
        <circle cx="55" cy="16" r="9" className={BODY} />
        <path
          d="M40 30 h30 l6 8 v30 l-4 22 h-34 l-4 -22 v-30 z"
          className={BODY}
        />
        <path d="M30 34 l10 -4 v34 l-8 22 -7 -3 5 -22 z" className={BODY} />
        <path d="M80 34 l-10 -4 v34 l8 22 7 -3 -5 -22 z" className={BODY} />
        <path d="M40 92 h13 v70 l-3 30 h-8 l-2 -30 z" className={BODY} />
        <path d="M70 92 h-13 v70 l3 30 h8 l2 -30 z" className={BODY} />

        {/* axlar */}
        <circle cx="38" cy="36" r="6" className={cls("axlar")} />
        <circle cx="72" cy="36" r="6" className={cls("axlar")} />
        {/* bröst */}
        <ellipse cx="47.5" cy="46" rx="7" ry="5.5" className={cls("bröst")} />
        <ellipse cx="62.5" cy="46" rx="7" ry="5.5" className={cls("bröst")} />
        {/* biceps */}
        <ellipse cx="33" cy="55" rx="4.5" ry="8" className={cls("biceps")} />
        <ellipse cx="77" cy="55" rx="4.5" ry="8" className={cls("biceps")} />
        {/* underarmar */}
        <ellipse cx="28" cy="74" rx="3.5" ry="9" className={cls("underarmar")} />
        <ellipse cx="82" cy="74" rx="3.5" ry="9" className={cls("underarmar")} />
        {/* mage */}
        <rect x="47" y="55" width="16" height="26" rx="5" className={cls("mage")} />
        {/* lår (framsida) */}
        <ellipse cx="47" cy="120" rx="6" ry="22" className={cls("ben")} />
        <ellipse cx="63" cy="120" rx="6" ry="22" className={cls("ben")} />
      </g>
      <text x="55" y="205" textAnchor="middle" className="fill-faint text-[9px]">
        Framsida
      </text>

      {/* ── Baksida ── */}
      <g strokeWidth="1" transform="translate(120 0)">
        <circle cx="55" cy="16" r="9" className={BODY} />
        <path
          d="M40 30 h30 l6 8 v30 l-4 22 h-34 l-4 -22 v-30 z"
          className={BODY}
        />
        <path d="M30 34 l10 -4 v34 l-8 22 -7 -3 5 -22 z" className={BODY} />
        <path d="M80 34 l-10 -4 v34 l8 22 7 -3 -5 -22 z" className={BODY} />
        <path d="M40 92 h13 v70 l-3 30 h-8 l-2 -30 z" className={BODY} />
        <path d="M70 92 h-13 v70 l3 30 h8 l2 -30 z" className={BODY} />

        {/* traps */}
        <path d="M45 30 h20 l-4 9 h-12 z" className={cls("traps")} />
        {/* axlar bak */}
        <circle cx="38" cy="36" r="6" className={cls("axlar")} />
        <circle cx="72" cy="36" r="6" className={cls("axlar")} />
        {/* rygg (lats) */}
        <path d="M43 42 h24 l-3 20 -9 6 -9 -6 z" className={cls("rygg")} />
        {/* ländrygg */}
        <rect x="48" y="66" width="14" height="11" rx="4" className={cls("ländrygg", "rygg")} />
        {/* triceps */}
        <ellipse cx="33" cy="55" rx="4.5" ry="8" className={cls("triceps")} />
        <ellipse cx="77" cy="55" rx="4.5" ry="8" className={cls("triceps")} />
        {/* säte */}
        <ellipse cx="48" cy="89" rx="7.5" ry="6.5" className={cls("säte")} />
        <ellipse cx="62" cy="89" rx="7.5" ry="6.5" className={cls("säte")} />
        {/* baksida lår */}
        <ellipse cx="47" cy="118" rx="6" ry="19" className={cls("ben", "baksida lår")} />
        <ellipse cx="63" cy="118" rx="6" ry="19" className={cls("ben", "baksida lår")} />
        {/* vader */}
        <ellipse cx="47" cy="155" rx="4.5" ry="12" className={cls("vader")} />
        <ellipse cx="63" cy="155" rx="4.5" ry="12" className={cls("vader")} />
      </g>
      <text x="175" y="205" textAnchor="middle" className="fill-faint text-[9px]">
        Baksida
      </text>
    </svg>
  );
}
