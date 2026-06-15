import { useEffect, useState } from "react";
import { getEstimate, type EstimateResponse } from "@/api/pipeline";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Timer, DollarSign, Server, Cloud, ChevronDown, ChevronRight } from "lucide-react";

interface EstimateCardProps {
  strategy: string;
}

export function EstimateCard({ strategy }: EstimateCardProps) {
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!strategy) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    getEstimate(strategy)
      .then((data) => {
        if (!cancelled) setEstimate(data);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load estimate");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [strategy]);

  if (loading && !estimate) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
            <Timer className="h-4 w-4" />
            <span>Loading estimate...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !estimate) return null;

  return (
    <Card className="border-dashed">
      <CardContent className="p-4 space-y-3">
        {/* Summary row */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-1.5 text-sm">
            <Timer className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{estimate.estimated_time_display}</span>
            <Badge variant="outline" className="text-xs">
              {estimate.stages} stages
            </Badge>
          </div>
          <div className="flex items-center gap-1.5 text-sm">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{estimate.cost_display}</span>
          </div>
          {estimate.cloud_cost_usd > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Cloud className="h-3.5 w-3.5" />
              <span>Cloud: ${estimate.cloud_cost_usd.toFixed(4)}</span>
            </div>
          )}
          {estimate.local_cost_usd === 0 && (
            <div className="flex items-center gap-1.5 text-xs text-success">
              <Server className="h-3.5 w-3.5" />
              <span>Local compute: Free</span>
            </div>
          )}
        </div>

        {/* Expandable breakdown */}
        <div>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            {expanded ? "Hide stage breakdown" : "Show stage breakdown"}
          </button>
          {expanded && (
            <div className="mt-2 space-y-1">
              {estimate.breakdown.map((b) => (
                <div
                  key={b.stage}
                  className="flex items-center gap-3 text-xs py-1 px-2 rounded hover:bg-muted/50"
                >
                  <span className="w-36 font-medium truncate" title={b.stage}>
                    {b.stage.replace(/_/g, " ")}
                  </span>
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {b.label}
                  </Badge>
                  <span className="w-14 text-right text-muted-foreground">
                    {b.time_seconds >= 60
                      ? `${(b.time_seconds / 60).toFixed(0)}m`
                      : `${b.time_seconds.toFixed(0)}s`}
                  </span>
                  <span className="w-16 text-right">
                    {b.cost_usd > 0 ? `$${b.cost_usd.toFixed(4)}` : "Free"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
