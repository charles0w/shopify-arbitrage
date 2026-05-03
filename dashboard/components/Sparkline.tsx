import type { DailyPoint } from "@/lib/stats";

/**
 * Pure-SVG line chart. No chart library — keeps the dashboard bundle small.
 *
 * The path is drawn in a 0..100 viewBox with non-scaling stroke so the line
 * stays crisp at any width. Hover dots show day + value via native title.
 */
export default function Sparkline({
  data,
  height = 56,
  ariaLabel,
}: {
  data: DailyPoint[];
  height?: number;
  ariaLabel?: string;
}) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.total), 1);
  const stepX = data.length > 1 ? 100 / (data.length - 1) : 0;

  const points = data.map((d, i) => {
    const x = i * stepX;
    const y = max === 0 ? 100 : 100 - (d.total / max) * 100;
    return { x, y, ...d };
  });

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ");
  const fillD = `${pathD} L100,100 L0,100 Z`;

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ height, width: "100%", display: "block" }}
      role="img"
      aria-label={ariaLabel}
    >
      <path d={fillD} fill="rgb(99 102 241)" fillOpacity="0.12" />
      <path
        d={pathD}
        fill="none"
        stroke="rgb(129 140 248)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {points.map((p) => (
        <circle
          key={p.date}
          cx={p.x}
          cy={p.y}
          r="0.7"
          fill="rgb(129 140 248)"
          vectorEffect="non-scaling-stroke"
        >
          <title>{`${p.date}: $${p.total.toFixed(2)}`}</title>
        </circle>
      ))}
    </svg>
  );
}
