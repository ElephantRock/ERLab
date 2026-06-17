interface ClusterData {
  cluster_id: number;
  label: string;
  paper_count: number;
  top_terms: string[];
  avg_citations: number | null;
}

interface ClusterScatterPlotProps {
  clusters: ClusterData[];
  onClusterClick?: (clusterId: number) => void;
  selectedClusterId?: number | null;
}

export function ClusterScatterPlot({ clusters, onClusterClick, selectedClusterId }: ClusterScatterPlotProps) {
  if (!clusters.length) {
    return <p className="text-sm text-muted-foreground py-4">No cluster data available.</p>;
  }

  const maxPapers = Math.max(...clusters.map((c) => c.paper_count), 1);
  const width = 600;
  const height = 400;
  const padding = 40;

  // Arrange clusters in a grid layout
  const cols = Math.ceil(Math.sqrt(clusters.length));
  const rows = Math.ceil(clusters.length / cols);

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-2xl">
        {clusters.map((cluster, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols);
          const cx = padding + (col + 0.5) * ((width - 2 * padding) / cols);
          const cy = padding + (row + 0.5) * ((height - 2 * padding) / rows);
          const r = 10 + (cluster.paper_count / maxPapers) * 30;
          const hue = (i * 137.5) % 360; // Golden angle for color spread

          return (
            <g
              key={cluster.cluster_id}
              onClick={() => onClusterClick?.(cluster.cluster_id)}
              className={onClusterClick ? "cursor-pointer" : undefined}
              role={onClusterClick ? "button" : undefined}
              tabIndex={onClusterClick ? 0 : undefined}
              onKeyDown={(e) => {
                if (onClusterClick && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  onClusterClick(cluster.cluster_id);
                }
              }}
              aria-label={`Cluster ${cluster.cluster_id}: ${cluster.label || ""}, ${cluster.paper_count} papers`}
            >
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={`hsl(${hue}, 60%, 70%)`}
                stroke={selectedClusterId === cluster.cluster_id ? "#000" : `hsl(${hue}, 60%, 40%)`}
                strokeWidth={selectedClusterId === cluster.cluster_id ? 4 : 2}
                opacity={selectedClusterId == null || selectedClusterId === cluster.cluster_id ? 0.85 : 0.3}
              />
              <text
                x={cx}
                y={cy}
                textAnchor="middle"
                dominantBaseline="central"
                className="text-xs font-medium"
                fill="#333"
              >
                {cluster.paper_count}
              </text>
              <text
                x={cx}
                y={cy + r + 14}
                textAnchor="middle"
                className="text-xs"
                fill="#666"
              >
                {cluster.label || `Cluster ${cluster.cluster_id}`}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-2 mt-2">
        {clusters.map((cluster) => (
          <span key={cluster.cluster_id} className="text-xs text-muted-foreground">
            {cluster.label || `Cluster ${cluster.cluster_id}`}: {cluster.paper_count} papers
            {cluster.top_terms.length > 0 && ` (${cluster.top_terms.slice(0, 3).join(", ")})`}
          </span>
        ))}
      </div>
    </div>
  );
}
