import { useMemo } from "react";

export interface RadarChartProps {
  data: Array<{ label: string; value: number }>;
  size?: number;
  color?: string;
}

function getFillColor(avg: number): string {
  if (avg >= 0.8) return "rgba(34, 197, 94, 0.25)";
  if (avg >= 0.6) return "rgba(234, 179, 8, 0.25)";
  if (avg >= 0.4) return "rgba(249, 115, 22, 0.25)";
  return "rgba(239, 68, 68, 0.25)";
}

function getStrokeColor(avg: number): string {
  if (avg >= 0.8) return "rgb(34, 197, 94)";
  if (avg >= 0.6) return "rgb(234, 179, 8)";
  if (avg >= 0.4) return "rgb(249, 115, 22)";
  return "rgb(239, 68, 68)";
}

function getColorClass(avg: number): string {
  if (avg >= 0.8) return "radar-color-green";
  if (avg >= 0.6) return "radar-color-yellow";
  if (avg >= 0.4) return "radar-color-orange";
  return "radar-color-red";
}

export function RadarChart({ data, size = 200, color }: RadarChartProps) {
  const n = data.length || 5;
  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.35;

  const avg = useMemo(() => {
    if (data.length === 0) return 0;
    return data.reduce((s, d) => s + d.value, 0) / data.length;
  }, [data]);

  const colorClass = color ? "" : getColorClass(avg);

  const points = useMemo(() => {
    const pts: Array<{ x: number; y: number }> = [];
    for (let i = 0; i < n; i++) {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      const value = data[i]?.value ?? 0;
      const r = radius * Math.max(0, Math.min(1, value));
      pts.push({
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
      });
    }
    return pts;
  }, [data, n, cx, cy, radius]);

  const polygonPoints = points.map((p) => `${p.x},${p.y}`).join(" ");

  const labelPoints = useMemo(() => {
    const labels: Array<{ x: number; y: number; label: string }> = [];
    const labelRadius = radius + 24;
    for (let i = 0; i < n; i++) {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      labels.push({
        x: cx + labelRadius * Math.cos(angle),
        y: cy + labelRadius * Math.sin(angle),
        label: data[i]?.label ?? "",
      });
    }
    return labels;
  }, [data, n, cx, cy, radius]);

  // Grid rings at 0.25, 0.5, 0.75, 1.0
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`radar-chart ${colorClass}`}
      data-testid="radar-chart"
      role="img"
      aria-label={`Radar chart with average score ${avg.toFixed(2)}`}
    >
      {/* Grid rings */}
      {gridLevels.map((level) => {
        const gridPoints: string[] = [];
        for (let i = 0; i < n; i++) {
          const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
          const r = radius * level;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          gridPoints.push(`${x},${y}`);
        }
        return (
          <polygon
            key={level}
            points={gridPoints.join(" ")}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.15}
            strokeWidth={1}
          />
        );
      })}

      {/* Axis lines */}
      {Array.from({ length: n }, (_, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        return (
          <line
            key={`axis-${i}`}
            x1={cx}
            y1={cy}
            x2={cx + radius * Math.cos(angle)}
            y2={cy + radius * Math.sin(angle)}
            stroke="currentColor"
            strokeOpacity={0.15}
            strokeWidth={1}
          />
        );
      })}

      {/* Data polygon */}
      <polygon
        data-testid="radar-polygon"
        points={polygonPoints}
        fill={color || getFillColor(avg)}
        stroke={color || getStrokeColor(avg)}
        strokeWidth={2}
      />

      {/* Data points */}
      {points.map((p, i) => (
        <circle
          key={`point-${i}`}
          cx={p.x}
          cy={p.y}
          r={3}
          fill={color || getStrokeColor(avg)}
        />
      ))}

      {/* Labels */}
      {labelPoints.map((lp, i) => (
        <text
          key={`label-${i}`}
          data-testid={`radar-label-${i}`}
          x={lp.x}
          y={lp.y}
          textAnchor="middle"
          dominantBaseline="central"
          className="text-xs fill-muted-foreground"
          fontSize={11}
        >
          {lp.label}
        </text>
      ))}
    </svg>
  );
}
