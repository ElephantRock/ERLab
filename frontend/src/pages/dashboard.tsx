/**
 * Dashboard — Research Command Center
 *
 * Serves three user personas simultaneously:
 * - Researcher: start runs, inspect ideas, export results
 * - Reviewer: see what needs attention, quality issues, governance
 * - Operator: system health, model status, source availability
 *
 * Each panel degrades independently. No single API failure breaks the page.
 */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState, useEffect, lazy, Suspense } from "react";
import {
  Play,
  Activity,
  Lightbulb,
  Server,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Shield,
  TrendingUp,
  ChevronRight,
  Loader2,
  FlaskConical,
  Zap,
  FileText,
  BookOpen,
  Download,
} from "lucide-react";

import { listRuns } from "@/api/pipeline";
import { getSystemStatus } from "@/api/status";
import { listIdeas } from "@/api/ideas";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { OnboardingOverlay } from "@/components/onboarding/onboarding-overlay";
import { cn } from "@/lib/utils";

import type { PipelineRunSummary, IdeaSummary } from "@/api/types";

const ScoreDistributionChart = lazy(() =>
  import("@/components/charts/score-distribution").then((m) => ({ default: m.ScoreDistributionChart })),
);
const RunStatusChart = lazy(() =>
  import("@/components/charts/run-status-chart").then((m) => ({ default: m.RunStatusChart })),
);

export default function Dashboard() {
  const navigate = useNavigate();
  const [showOnboarding, setShowOnboarding] = useState(false);

  const { data: status } = useQuery({ queryKey: ["status"], queryFn: getSystemStatus });
  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ["runs", { limit: 5 }],
    queryFn: () => listRuns({ limit: 5 }),
  });
  const { data: ideasData, isLoading: ideasLoading } = useQuery({
    queryKey: ["ideas", { limit: 5 }],
    queryFn: () => listIdeas({ limit: 5 }),
  });
  const { data: opsData, isError: opsError } = useQuery({
    queryKey: ["ops-dashboard", 30],
    queryFn: () => getOpsDashboard(30),
  });
  const { data: governanceData } = useQuery({
    queryKey: ["governance-pending"],
    queryFn: getPending,
  });
  const { data: chartIdeas } = useQuery({
    queryKey: ["ideas", { limit: 50 }],
    queryFn: () => listIdeas({ limit: 50 }),
  });
  const { data: chartRuns } = useQuery({
    queryKey: ["runs", { limit: 50 }],
    queryFn: () => listRuns({ limit: 50 }),
  });

  useEffect(() => {
    const onboardingDone = localStorage.getItem("erock_onboarding_complete");
    if (!onboardingDone && runsData && (runsData.total ?? 0) === 0) {
      setShowOnboarding(true);
    }
  }, [runsData]);

  function handleOnboardingStart(topic: string) {
    navigate(`/pipeline/new?topic=${encodeURIComponent(topic)}`);
  }

  // Derived values (all safe when data is undefined)
  const latestRun = runsData?.runs[0];
  const failedRuns = runsData?.runs.filter((r) => r.status === "failed") ?? [];
  const governancePending = governanceData?.pending ?? [];
  const qualityFailures = opsData?.quality_trends?.common_failures ?? [];
  const passRate = opsData?.quality_trends?.quality_pass_rate;
  const citationRate = opsData?.quality_trends?.citation_resolution_rate;
  const remediationCount = opsData?.quality_trends?.remediation_count ?? 0;
  const totalIdeas = ideasData?.total ?? 0;
  const proposalsCount = opsData?.quality_trends?.proposal_count ?? 0;

  // ── Attention Queue items ──────────────────────────────────────
  const attentionItems: AttentionItem[] = [
    ...failedRuns.slice(0, 3).map((r) => ({
      type: "run_failure" as const,
      severity: "high" as const,
      title: r.domain,
      detail: r.error_message ?? "Run failed unexpectedly",
      action: () => navigate(`/runs/${r.id}`),
      actionLabel: "Open Run",
    })),
    ...governancePending.slice(0, 3).map((g) => ({
      type: "governance" as const,
      severity: "medium" as const,
      title: g.summary,
      detail: `Pending: ${g.type}`,
      action: () => navigate("/governance"),
      actionLabel: "Review",
    })),
    ...qualityFailures.slice(0, 4).map((f) => ({
      type: "quality" as const,
      severity: "medium" as const,
      title: f.failure,
      detail: `${f.count} section${f.count !== 1 ? "s" : ""} affected`,
      action: () => navigate("/ideas"),
      actionLabel: "Browse Ideas",
    })),
  ];

  if (remediationCount > 0) {
    attentionItems.push({
      type: "remediation" as const,
      severity: "low" as const,
      title: `${remediationCount} section${remediationCount !== 1 ? "s" : ""} remediated`,
      detail: "Review regenerated sections in revision history",
      action: () => navigate("/ideas"),
      actionLabel: "Review",
    });
  }

  const hasChartData =
    (chartIdeas?.ideas.length ?? 0) > 0 || (chartRuns?.runs.length ?? 0) > 0;

  return (
    <div className="space-y-6" data-testid="dashboard">
      {/* ── Hero ───────────────────────────────────────────────── */}
      <div className="space-y-3" data-testid="hero-section">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Research Command Center</h1>
          <p className="text-muted-foreground mt-1">
            Generate, review, improve, and export research proposals.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => navigate("/pipeline/new")} size="lg" data-testid="hero-new-run">
            <Play className="mr-2 h-5 w-5" />
            Start New Research Run
          </Button>
          {latestRun && (
            <Button
              variant="outline"
              size="lg"
              onClick={() => navigate(`/runs/${latestRun.id}`)}
              data-testid="hero-latest-run"
            >
              <Clock className="mr-2 h-4 w-4" />
              Open Latest Run
            </Button>
          )}
          <Button
            variant="outline"
            size="lg"
            onClick={() => navigate("/ops")}
            data-testid="hero-system-health"
          >
            <Server className="mr-2 h-4 w-4" />
            System Health
          </Button>
        </div>
      </div>

      {/* ── Metric Strip ───────────────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Latest Run"
          icon={Activity}
          loading={runsLoading}
          testId="stat-latest-run"
        >
          {latestRun ? (
            <div className="space-y-1">
              <RunStatusBadge status={latestRun.status} />
              <p className="text-xs text-muted-foreground truncate">{latestRun.domain}</p>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">No runs yet</span>
          )}
        </MetricCard>

        <MetricCard
          label="Outputs"
          icon={Lightbulb}
          loading={ideasLoading}
          testId="stat-outputs"
        >
          <div className="flex items-baseline gap-3">
            <Metric label="Ideas" value={totalIdeas} />
            <Metric label="Proposals" value={proposalsCount} />
          </div>
        </MetricCard>

        <MetricCard
          label="Quality"
          icon={CheckCircle2}
          loading={!opsData && !opsError}
          testId="stat-quality"
        >
          {passRate != null ? (
            <div className="space-y-0.5">
              <div className="flex items-baseline gap-1.5">
                <span className={cn("text-2xl font-bold", passRate >= 80 ? "text-success" : "text-warning")}>
                  {passRate.toFixed(0)}%
                </span>
                <span className="text-xs text-muted-foreground">pass rate</span>
              </div>
              {citationRate != null && (
                <p className="text-xs text-muted-foreground">
                  {citationRate.toFixed(0)}% citations resolved
                </p>
              )}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">Not available</span>
          )}
        </MetricCard>

        <MetricCard
          label="Review"
          icon={Shield}
          loading={!governanceData}
          testId="stat-review"
        >
          <div className="flex items-baseline gap-3">
            <Metric
              label="Pending"
              value={governancePending.length}
              tone={governancePending.length > 0 ? "warning" : "success"}
            />
            {remediationCount > 0 && (
              <Metric label="Remediated" value={remediationCount} tone="info" />
            )}
          </div>
        </MetricCard>
      </div>

      {/* ── Latest Run + Attention Queue ──────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="latest-run-panel">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Latest Run</span>
              {latestRun && (
                <Button
                  variant="link"
                  size="sm"
                  className="p-0 h-auto"
                  onClick={() => navigate(`/runs/${latestRun.id}`)}
                >
                  Details
                  <ChevronRight className="h-3 w-3" />
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {runsLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : latestRun ? (
              <LatestRunPanel run={latestRun} navigate={navigate} />
            ) : (
              <div className="text-center py-6 text-muted-foreground">
                <FlaskConical className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No runs yet.</p>
                <Button
                  variant="link"
                  size="sm"
                  className="mt-1"
                  onClick={() => navigate("/pipeline/new")}
                >
                  Start your first pipeline
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card data-testid="attention-queue">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-warning" />
                Attention Queue
              </span>
              {attentionItems.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  {attentionItems.length} item{attentionItems.length !== 1 ? "s" : ""}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {attentionItems.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-success opacity-70" />
                <p className="text-sm">All clear. Nothing needs attention.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {attentionItems.slice(0, 6).map((item, idx) => (
                  <AttentionRow key={idx} item={item} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Recent Outputs + System Health ────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="recent-outputs">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span>Recent Research Outputs</span>
              <Button
                variant="link"
                size="sm"
                className="p-0 h-auto"
                onClick={() => navigate("/ideas")}
              >
                View all
                <ChevronRight className="h-3 w-3" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {ideasLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : ideasData?.ideas.length ? (
              <div className="space-y-2">
                {ideasData.ideas.slice(0, 5).map((idea) => (
                  <RecentOutputRow
                    key={idea.id}
                    idea={idea}
                    onClick={() => navigate(`/ideas/${idea.id}`)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-muted-foreground">
                <Lightbulb className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No ideas generated yet.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card data-testid="system-health">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Server className="h-4 w-4" />
                System Health
              </span>
              <Button
                variant="link"
                size="sm"
                className="p-0 h-auto"
                onClick={() => navigate("/ops")}
              >
                Open Ops
                <ChevronRight className="h-3 w-3" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SystemHealthPanel status={status} opsData={opsData} />
          </CardContent>
        </Card>
      </div>

      {/* ── Analytics ─────────────────────────────────────────── */}
      {hasChartData && (
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Analytics</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Score Distribution
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScoreDistributionChart ideas={chartIdeas?.ideas ?? []} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Run Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <RunStatusChart runs={chartRuns?.runs ?? []} />
                </CardContent>
              </Card>
            </div>
          </div>
        </Suspense>
      )}

      {showOnboarding && (
        <OnboardingOverlay
          onStartPipeline={handleOnboardingStart}
          onDismiss={() => setShowOnboarding(false)}
        />
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────

interface AttentionItem {
  type: "run_failure" | "governance" | "quality" | "remediation";
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
  action: () => void;
  actionLabel: string;
}

const ATTENTION_CONFIG = {
  run_failure: { icon: XCircle, color: "text-destructive", label: "Run Failure" },
  governance: { icon: Shield, color: "text-warning", label: "Governance" },
  quality: { icon: AlertTriangle, color: "text-warning", label: "Quality" },
  remediation: { icon: Zap, color: "text-info", label: "Remediation" },
} as const;

const SEVERITY_DOT = {
  high: "bg-destructive",
  medium: "bg-warning",
  low: "bg-info",
} as const;

function AttentionRow({ item }: { item: AttentionItem }) {
  const config = ATTENTION_CONFIG[item.type];
  const Icon = config.icon;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-muted p-2.5 hover:bg-accent/50 transition-colors cursor-pointer"
      onClick={item.action}
      data-testid={`attention-${item.type}`}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          item.action();
        }
      }}
    >
      <Icon className={cn("h-4 w-4 flex-shrink-0", config.color)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {config.label}
          </span>
          <span className={cn("h-1.5 w-1.5 rounded-full", SEVERITY_DOT[item.severity])} />
        </div>
        <p className="text-sm font-medium line-clamp-1">{item.title}</p>
        <p className="text-xs text-muted-foreground line-clamp-1">{item.detail}</p>
      </div>
      <Button variant="ghost" size="sm" className="flex-shrink-0 text-xs">
        {item.actionLabel}
      </Button>
    </div>
  );
}

function LatestRunPanel({
  run,
  navigate,
}: {
  run: PipelineRunSummary;
  navigate: (path: string) => void;
}) {
  if (run.status === "running") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="text-sm font-medium">{run.domain}</span>
          {run.current_stage && (
            <Badge variant="outline" className="text-xs">{run.current_stage}</Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Started {new Date(run.created_at).toLocaleTimeString()}
        </p>
        <div className="flex gap-2 mt-2">
          <Button size="sm" variant="outline" onClick={() => navigate(`/runs/${run.id}`)}>
            View Progress
          </Button>
        </div>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-destructive" />
          <span className="text-sm font-medium">{run.domain}</span>
        </div>
        <p className="text-xs text-destructive/80 line-clamp-2">
          {run.error_message ?? "Run failed unexpectedly"}
        </p>
        <div className="flex gap-2 mt-2">
          <Button size="sm" variant="outline" onClick={() => navigate(`/runs/${run.id}`)}>
            View Details
          </Button>
          <Button size="sm" onClick={() => navigate("/pipeline/new")}>
            Start New
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-success" />
        <span className="text-sm font-medium">{run.domain}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>{run.ideas_count} ideas</span>
        <span>{new Date(run.created_at).toLocaleDateString()}</span>
      </div>
      <div className="flex gap-2 mt-2">
        <Button size="sm" variant="outline" onClick={() => navigate(`/runs/${run.id}`)}>
          View Run
        </Button>
        <Button size="sm" variant="outline" onClick={() => navigate("/ideas")}>
          Browse Ideas
        </Button>
      </div>
    </div>
  );
}

function RecentOutputRow({
  idea,
  onClick,
}: {
  idea: IdeaSummary;
  onClick: () => void;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-muted p-2.5 hover:bg-accent/50 transition-colors cursor-pointer"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      data-testid={`recent-output-${idea.id}`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium line-clamp-1">{idea.title}</p>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          <span className="text-xs text-muted-foreground">{idea.domain}</span>
          {idea.has_proposal ? (
            <Badge variant="outline" className="text-xs py-0 gap-0.5">
              <FileText className="h-2.5 w-2.5" />
              Proposal
            </Badge>
          ) : (
            <span className="text-xs text-muted-foreground italic">No proposal</span>
          )}
          {idea.overall_score != null && (
            <span className="text-xs font-semibold text-primary">
              {idea.overall_score.toFixed(2)}
            </span>
          )}
          {idea.novelty_score != null && (
            <span className="text-xs text-muted-foreground">
              Novelty {idea.novelty_score.toFixed(2)}
            </span>
          )}
        </div>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
    </div>
  );
}

function SystemHealthPanel({
  status,
  opsData,
}: {
  status: ReturnType<typeof useQuery>["data"] extends infer T ? T : never;
  opsData: ReturnType<typeof useQuery>["data"] extends infer T ? T : never;
}) {
  const backendOnline = !!status;
  const governanceEnabled = status?.config?.governance_enabled ?? false;
  const defaultProvider = status?.config?.default_provider ?? "—";
  const qualityPassRate = opsData?.quality_trends?.quality_pass_rate;
  const totalPapers = opsData?.source_health?.papers_found_total;
  const runHealth = opsData?.run_health;

  return (
    <div className="space-y-2" data-testid="system-health-content">
      <HealthRow
        label="Backend"
        ok={backendOnline}
        value={backendOnline ? "Online" : "Offline"}
      />
      <HealthRow
        label="Model Provider"
        ok={backendOnline}
        value={defaultProvider}
      />
      <HealthRow
        label="Governance"
        ok={governanceEnabled}
        value={governanceEnabled ? "Enabled" : "Disabled"}
      />
      {totalPapers != null && (
        <HealthRow
          label="Papers Indexed"
          ok={totalPapers > 0}
          value={totalPapers.toLocaleString()}
        />
      )}
      {runHealth && (
        <HealthRow
          label="Recent Runs"
          ok={runHealth.failed < runHealth.total_runs}
          value={`${runHealth.completed}/${runHealth.total_runs} completed`}
        />
      )}
      {qualityPassRate != null && (
        <HealthRow
          label="Quality"
          ok={qualityPassRate >= 70}
          value={`${qualityPassRate.toFixed(0)}% pass`}
        />
      )}
    </div>
  );
}

function HealthRow({
  label,
  ok,
  value,
}: {
  label: string;
  ok: boolean;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            ok ? "bg-success" : "bg-destructive",
          )}
        />
        <span className="text-muted-foreground">{label}</span>
      </div>
      <span className={cn("font-medium", ok ? "text-foreground" : "text-destructive")}>
        {value}
      </span>
    </div>
  );
}

function RunStatusBadge({ status }: { status: PipelineRunSummary["status"] }) {
  const config = {
    running: { icon: Loader2, className: "animate-spin text-primary", label: "Running" },
    completed: { icon: CheckCircle2, className: "text-success", label: "Completed" },
    failed: { icon: XCircle, className: "text-destructive", label: "Failed" },
    pending: { icon: Clock, className: "text-muted-foreground", label: "Pending" },
  };
  const { icon: Icon, className, label } = config[status];

  return (
    <span className="flex items-center gap-1.5">
      <Icon className={cn("h-3.5 w-3.5", className)} />
      <span className="text-xs font-medium">{label}</span>
    </span>
  );
}

function MetricCard({
  label,
  icon: Icon,
  loading,
  children,
  testId,
}: {
  label: string;
  icon: React.ElementType;
  loading?: boolean;
  children: React.ReactNode;
  testId: string;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{label}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-8 w-20" /> : children}
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "warning" | "success" | "info";
}) {
  const toneClass = {
    warning: "text-warning",
    success: "text-success",
    info: "text-info",
  };
  return (
    <div>
      <span className={cn("text-2xl font-bold", tone && toneClass[tone])}>{value}</span>
      <span className="text-xs text-muted-foreground ml-1">{label}</span>
    </div>
  );
}
