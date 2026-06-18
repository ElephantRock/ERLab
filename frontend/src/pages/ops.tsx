/**
 * OpsPage — Operational dashboard (read-only).
 *
 * Shows 4 metric cards: Run Health, Model Usage, Source Health, Quality Trends.
 * Uses bounded time window with day selector.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getOpsDashboard, type OpsDashboard } from "@/api/ops";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ErrorCard } from "@/components/ui/error-card";
import {
  Activity,
  Cpu,
  Database,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
} from "lucide-react";

export default function OpsPage() {
  const [days, setDays] = useState(7);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["ops-dashboard", days],
    queryFn: () => getOpsDashboard(days),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Operational Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Platform health, model usage, source coverage, and quality trends
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((d) => (
            <Button
              key={d}
              variant={days === d ? "default" : "outline"}
              size="sm"
              onClick={() => setDays(d)}
            >
              {d}d
            </Button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <ErrorCard
          message="Failed to load dashboard"
          error={error instanceof Error ? error.message : "Unknown error"}
        />
      )}

      {/* Dashboard cards */}
      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <RunHealthCard data={data} />
          <ModelUsageCard data={data} />
          <SourceHealthCard data={data} />
          <QualityTrendsCard data={data} />
        </div>
      )}
    </div>
  );
}

// ── Cards ──────────────────────────────────────────────────

function RunHealthCard({ data }: { data: OpsDashboard }) {
  const rh = data.run_health;
  if (rh.error) {
    return (
      <MetricCard title="Run Health" icon={Activity} testId="run-health-card">
        <p className="text-sm text-muted-foreground">Metrics unavailable: {rh.error}</p>
      </MetricCard>
    );
  }

  return (
    <MetricCard title="Run Health" icon={Activity} testId="run-health-card">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Total" value={rh.total_runs} />
        <Stat label="Completed" value={rh.completed} icon={<CheckCircle2 className="h-3 w-3 text-success" />} />
        <Stat label="Failed" value={rh.failed} icon={<XCircle className="h-3 w-3 text-destructive" />} />
        <Stat label="Running" value={rh.running} icon={<Activity className="h-3 w-3 text-info" />} />
        <Stat label="Pending" value={rh.pending} />
        <Stat label="Cancelled" value={rh.cancelled} />
      </div>

      <div className="mt-3 flex items-center gap-2 text-sm">
        <Clock className="h-3 w-3 text-muted-foreground" />
        <span className="text-muted-foreground">Avg duration:</span>
        <span className="font-mono font-medium">
          {formatDuration(rh.average_duration_s)}
        </span>
      </div>

      {rh.slowest_stages.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="slowest-stages">
          <span className="text-xs text-muted-foreground uppercase tracking-wide">
            Slowest Stages
          </span>
          {rh.slowest_stages.map((s) => (
            <div key={s.stage} className="flex items-center justify-between text-xs">
              <span className="font-mono">{s.stage}</span>
              <span className="text-muted-foreground">
                {formatDuration(s.avg_seconds)} avg ({s.samples}x)
              </span>
            </div>
          ))}
        </div>
      )}
    </MetricCard>
  );
}

function ModelUsageCard({ data }: { data: OpsDashboard }) {
  const mu = data.model_usage;
  if (mu.error) {
    return (
      <MetricCard title="Model Usage" icon={Cpu} testId="model-usage-card">
        <p className="text-sm text-muted-foreground">Metrics unavailable: {mu.error}</p>
      </MetricCard>
    );
  }

  return (
    <MetricCard title="Model Usage" icon={Cpu} testId="model-usage-card">
      <div className="flex items-center gap-4">
        <Stat label="Total Receipts" value={mu.total_receipts} />
      </div>

      {mu.warnings.length > 0 && (
        <div className="mt-3 space-y-1">
          {mu.warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded bg-warning/5 border border-warning/10 px-2 py-1"
            >
              <AlertTriangle className="h-3 w-3 text-warning" />
              <span className="text-xs text-muted-foreground">{w}</span>
            </div>
          ))}
        </div>
      )}

      {mu.models.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="model-list">
          {mu.models.map((m) => (
            <div key={`${m.provider}/${m.served_model}`} className="flex items-center justify-between text-xs">
              <span className="font-mono">
                {m.provider}/{m.served_model}
              </span>
              <Badge variant="outline" className="text-xs">
                {m.calls} calls
              </Badge>
            </div>
          ))}
        </div>
      )}

      {mu.models.length === 0 && mu.warnings.length === 0 && (
        <p className="text-sm text-muted-foreground mt-2">No model usage data in window.</p>
      )}
    </MetricCard>
  );
}

function SourceHealthCard({ data }: { data: OpsDashboard }) {
  const sh = data.source_health;
  if (sh.error) {
    return (
      <MetricCard title="Source Health" icon={Database} testId="source-health-card">
        <p className="text-sm text-muted-foreground">Metrics unavailable: {sh.error}</p>
      </MetricCard>
    );
  }

  return (
    <MetricCard title="Source Health" icon={Database} testId="source-health-card">
      <div className="flex items-center gap-4">
        <Stat label="Total Papers" value={sh.papers_found_total} />
        <Stat
          label="Zero-result Runs"
          value={sh.zero_result_runs}
          icon={sh.zero_result_runs > 0 ? <AlertTriangle className="h-3 w-3 text-warning" /> : undefined}
        />
      </div>

      <div className="mt-3 space-y-1" data-testid="source-list">
        {sh.sources.map((s) => (
          <div key={s.source} className="flex items-center justify-between text-xs">
            <span className="font-mono">{s.source}</span>
            <span className="text-muted-foreground">{s.papers} papers</span>
          </div>
        ))}
      </div>
    </MetricCard>
  );
}

function QualityTrendsCard({ data }: { data: OpsDashboard }) {
  const qt = data.quality_trends;
  if (qt.error) {
    return (
      <MetricCard title="Quality Trends" icon={TrendingUp} testId="quality-trends-card">
        <p className="text-sm text-muted-foreground">Metrics unavailable: {qt.error}</p>
      </MetricCard>
    );
  }

  return (
    <MetricCard title="Quality Trends" icon={TrendingUp} testId="quality-trends-card">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Proposals" value={qt.proposal_count} />
        <Stat
          label="Pass Rate"
          value={`${qt.quality_pass_rate.toFixed(0)}%`}
        />
        <Stat
          label="Cit. Resolution"
          value={
            qt.citation_resolution_rate !== null
              ? `${qt.citation_resolution_rate.toFixed(0)}%`
              : "N/A"
          }
        />
        <Stat label="Remediations" value={qt.remediation_count} />
      </div>

      {qt.common_failures.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="common-failures">
          <span className="text-xs text-muted-foreground uppercase tracking-wide">
            Common Failures
          </span>
          {qt.common_failures.map((f) => (
            <div key={f.failure} className="flex items-center justify-between text-xs">
              <span className="truncate mr-2">{f.failure}</span>
              <Badge variant="outline" className="text-xs">{f.count}x</Badge>
            </div>
          ))}
        </div>
      )}
    </MetricCard>
  );
}

// ── Helpers ────────────────────────────────────────────────

function MetricCard({
  title,
  icon: Icon,
  testId,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Icon className="h-4 w-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border p-2">
      <div className="flex items-center gap-1">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <span className="text-lg font-bold font-mono">{value}</span>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}
