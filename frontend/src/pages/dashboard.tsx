/**
 * Dashboard — Research Studio Home
 *
 * The landing workspace. Answers in 10 seconds:
 * - What is this? (Hero)
 * - What happened? (Latest Investigation, Outputs)
 * - What needs attention? (Continue Reviewing, Attention Queue)
 * - Is the system healthy? (Research Health)
 * - Where are results? (Recent Proposals)
 */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState, useEffect, lazy, Suspense } from "react";
import {
  Play,
  Clock,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  Server,
  Loader2,
  FlaskConical,
  Lightbulb,
  ArrowRight,
  CheckSquare,
} from "lucide-react";

import { listRuns } from "@/api/pipeline";
import { getSystemStatus } from "@/api/status";
import { listIdeas } from "@/api/ideas";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

import { Card, CardContent } from "@/components/ui/card";
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
    queryKey: ["ideas", { limit: 6 }],
    queryFn: () => listIdeas({ limit: 6 }),
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
    const done = localStorage.getItem("erock_onboarding_complete");
    if (!done && runsData && (runsData.total ?? 0) === 0) setShowOnboarding(true);
  }, [runsData]);

  // Derived
  const latestRun = runsData?.runs[0];
  const activeRun = runsData?.runs.find((r) => r.status === "running");
  const governancePending = governanceData?.pending ?? [];
  const passRate = opsData?.quality_trends?.quality_pass_rate;
  const citationRate = opsData?.quality_trends?.citation_resolution_rate;
  const qualityFailures = opsData?.quality_trends?.common_failures ?? [];
  const remediationCount = opsData?.quality_trends?.remediation_count ?? 0;
  const totalIdeas = ideasData?.total ?? 0;
  const proposalsCount = opsData?.quality_trends?.proposal_count ?? ideasData?.ideas.filter((i) => i.has_proposal).length ?? 0;

  // Focus proposal: first one needing attention or just the latest
  const focusIdea = ideasData?.ideas.find((i) => i.has_proposal) ?? ideasData?.ideas[0];

  const attentionCount = qualityFailures.reduce((a, f) => a + f.count, 0) + governancePending.length;

  const hasChartData = (chartIdeas?.ideas.length ?? 0) > 0 || (chartRuns?.runs.length ?? 0) > 0;

  return (
    <div className="space-y-8 animate-fade-in" data-testid="dashboard">
      {/* ── Hero ───────────────────────────────────────────────── */}
      <div className="bg-card border border-border rounded-xl p-8 relative overflow-hidden card-shadow" data-testid="hero-section">
        <div className="relative z-10 space-y-4">
          <div className="text-[10px] font-mono font-bold tracking-widest text-accent uppercase">
            Elephant Rock Research Studio
          </div>
          <h1 className="text-3xl font-display font-semibold tracking-tight leading-tight">
            Welcome to Research Studio
          </h1>
          <p className="text-muted-foreground text-sm max-w-2xl leading-relaxed">
            Turn a research domain into traceable, reviewable proposals. Scan the literature,
            map critical gaps, and formulate rigorous designs under live quality gates.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Button onClick={() => navigate("/pipeline/new")} size="lg" data-testid="hero-new-run">
              <Play className="mr-2 h-4 w-4" />
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
                Continue Latest Run
              </Button>
            )}
            <Button
              variant="outline"
              size="lg"
              onClick={() => navigate("/governance")}
              data-testid="hero-review"
            >
              <CheckSquare className="mr-2 h-4 w-4" />
              Open Review Panel
            </Button>
          </div>
        </div>
      </div>

      {/* ── Summary Cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Latest Investigation */}
        <Card className="card-shadow card-shadow-hover transition-all" data-testid="stat-latest-run">
          <CardContent className="p-6 space-y-2">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Latest Investigation
            </p>
            {runsLoading ? (
              <Skeleton className="h-6 w-32" />
            ) : latestRun ? (
              <>
                <h2 className="text-lg font-semibold leading-snug line-clamp-2">
                  {activeRun ? activeRun.domain : latestRun.domain}
                </h2>
                <div className="text-xs text-muted-foreground flex items-center gap-2 font-mono">
                  <span className={cn("inline-block h-2 w-2 rounded-full", activeRun ? "bg-accent animate-pulse" : "bg-success")} />
                  <span>
                    {activeRun ? (activeRun.current_stage ?? "Synthesizing") : `Completed ${new Date(latestRun.created_at).toLocaleDateString()}`}
                  </span>
                </div>
                <div className="pt-3 border-t border-border mt-3 flex items-center justify-between">
                  <span className="text-[11px] text-muted-foreground font-mono">Run #{latestRun.id}</span>
                  <Button variant="link" size="sm" className="p-0 h-auto text-xs font-semibold text-accent"
                    onClick={() => navigate(`/runs/${latestRun.id}`)}>
                    Open Run <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </>
            ) : (
              <div className="py-3">
                <p className="text-sm text-muted-foreground">No runs yet</p>
                <Button variant="link" size="sm" className="p-0 mt-1"
                  onClick={() => navigate("/pipeline/new")}>
                  Start your first run
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Research Outputs */}
        <Card className="card-shadow card-shadow-hover transition-all" data-testid="stat-outputs">
          <CardContent className="p-6 space-y-3">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Research Outputs
            </p>
            {ideasLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <>
                <div className="grid grid-cols-3 gap-2">
                  <div className="text-center bg-muted/50 p-2 rounded">
                    <p className="text-xl font-semibold">{totalIdeas}</p>
                    <p className="text-[9px] text-muted-foreground uppercase font-mono">ideas</p>
                  </div>
                  <div className="text-center bg-muted/50 p-2 rounded">
                    <p className="text-xl font-semibold">{proposalsCount}</p>
                    <p className="text-[9px] text-muted-foreground uppercase font-mono">proposals</p>
                  </div>
                  <div className="text-center bg-muted/50 p-2 rounded">
                    <p className="text-xl font-semibold">{governancePending.length}</p>
                    <p className="text-[9px] text-muted-foreground uppercase font-mono">pending</p>
                  </div>
                </div>
                <div className="pt-3 border-t border-border flex items-center justify-end">
                  <Button variant="link" size="sm" className="p-0 h-auto text-xs font-semibold text-accent"
                    onClick={() => navigate("/ideas")}>
                    Browse Results <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Needs Attention */}
        <Card className="card-shadow card-shadow-hover transition-all" data-testid="stat-attention">
          <CardContent className="p-6 space-y-2">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Needs Attention
            </p>
            <h2 className="text-2xl font-light">
              <span className={cn("font-semibold", attentionCount > 0 ? "text-warning" : "text-success")}>
                {attentionCount}
              </span>
              <span className="text-muted-foreground"> issues</span>
            </h2>
            <p className="text-xs text-muted-foreground">
              {attentionCount > 0
                ? `${qualityFailures.length} quality checks, ${governancePending.length} governance items`
                : "All criteria verified"
              }
            </p>
            <div className="pt-3 border-t border-border flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground font-mono">
                {remediationCount > 0 && `${remediationCount} remediated`}
              </span>
              {attentionCount > 0 && (
                <Button variant="link" size="sm" className="p-0 h-auto text-xs font-semibold text-warning"
                  onClick={() => navigate("/ideas")}>
                  Review Now <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Continue Reviewing + Research Health ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Continue Reviewing */}
        <Card className="card-shadow" data-testid="continue-reviewing">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
                Continue Reviewing
              </h2>
              {qualityFailures.length > 0 && (
                <span className="text-[9px] bg-warning/10 text-warning px-2 py-0.5 font-mono rounded font-bold uppercase border border-warning/20">
                  Needs Attention
                </span>
              )}
            </div>

            {ideasLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : focusIdea ? (
              <div className="space-y-3">
                <div>
                  <h3
                    className="text-sm font-semibold leading-snug cursor-pointer hover:text-accent transition-colors"
                    onClick={() => navigate(`/ideas/${focusIdea.id}`)}
                  >
                    {focusIdea.title}
                  </h3>
                  <div className="flex gap-2 mt-1.5 flex-wrap">
                    <span className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded font-mono uppercase">
                      {focusIdea.domain}
                    </span>
                    {focusIdea.novelty_score != null && (
                      <span className="text-[10px] text-muted-foreground font-mono">
                        Novelty: {(focusIdea.novelty_score * 100).toFixed(0)}%
                      </span>
                    )}
                    {focusIdea.has_proposal && (
                      <span className="text-[10px] bg-accent/10 text-accent px-2 py-0.5 rounded font-mono uppercase">
                        Proposal Ready
                      </span>
                    )}
                  </div>
                </div>
                {qualityFailures.length > 0 && (
                  <div className="bg-muted/50 border border-border p-3 rounded text-xs space-y-1">
                    <div className="flex items-center gap-1.5 text-warning font-semibold text-[11px]">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      <span>Quality Flag: {qualityFailures[0]?.failure}</span>
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      {qualityFailures[0]?.count} section{qualityFailures[0]?.count !== 1 ? "s" : ""} affected.
                      Use section regeneration to fix.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-6 text-center italic">No proposals registered.</p>
            )}

            {focusIdea && (
              <div className="flex items-center gap-2 pt-3 border-t border-border">
                <Button size="sm" className="flex-1" onClick={() => navigate(`/ideas/${focusIdea.id}`)}>
                  Open Proposal
                </Button>
                {qualityFailures.length > 0 && (
                  <Button size="sm" variant="outline" className="flex-1" onClick={() => navigate(`/ideas/${focusIdea.id}`)}>
                    Fix Quality
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Research Health */}
        <Card className="card-shadow" data-testid="system-health">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
                Research Health
              </h2>
              {passRate != null && passRate >= 80 && (
                <span className="text-[9px] bg-success/10 text-success px-2 py-0.5 font-mono rounded font-bold uppercase border border-success/20">
                  Healthy
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              {passRate != null ? (
                <div className="bg-muted/50 p-3 rounded border border-border">
                  <p className="text-xs text-muted-foreground font-mono">Quality pass rate</p>
                  <p className={cn("text-2xl font-semibold mt-1", passRate >= 80 ? "text-success" : "text-warning")}>
                    {passRate.toFixed(0)}%
                  </p>
                </div>
              ) : (
                <div className="bg-muted/50 p-3 rounded border border-border">
                  <p className="text-xs text-muted-foreground font-mono">Quality</p>
                  <p className="text-sm text-muted-foreground mt-1">Not available</p>
                </div>
              )}
              {citationRate != null && (
                <div className="bg-muted/50 p-3 rounded border border-border">
                  <p className="text-xs text-muted-foreground font-mono">Citation resolution</p>
                  <p className={cn("text-2xl font-semibold mt-1", citationRate >= 80 ? "text-success" : "text-warning")}>
                    {citationRate.toFixed(0)}%
                  </p>
                </div>
              )}
              <div className="bg-muted/50 p-3 rounded border border-border col-span-2">
                <p className="text-xs text-muted-foreground font-mono">Model route</p>
                <p className="text-sm font-semibold font-mono mt-1">
                  {status?.config?.default_provider ?? "—"}
                </p>
              </div>
            </div>

            {/* Source health badges */}
            {opsData?.source_health?.sources && opsData.source_health.sources.length > 0 && (
              <div className="pt-1">
                <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2">
                  Sources Connected
                </p>
                <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                  {opsData.source_health.sources.map((s) => (
                    <span
                      key={s.source}
                      className={cn(
                        "px-2 py-0.5 border rounded",
                        s.papers > 0
                          ? "bg-success/5 text-success border-success/20"
                          : "bg-muted text-muted-foreground border-border",
                      )}
                    >
                      {s.source} {s.papers > 0 ? "OK" : "Idle"}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-border flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground font-mono">Telemetry live</span>
              <Button variant="link" size="sm" className="p-0 h-auto text-xs font-semibold text-accent"
                onClick={() => navigate("/ops")}>
                Open Operations
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Recent Proposals ───────────────────────────────────── */}
      <div className="space-y-4">
        <div className="flex items-end justify-between pb-2 border-b border-border">
          <div>
            <h2 className="text-lg font-semibold">Recent Proposals</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Research briefs with full traceable provenance
            </p>
          </div>
          <Button variant="link" size="sm" className="p-0 text-xs font-semibold text-accent font-mono uppercase"
            onClick={() => navigate("/ideas")}>
            All Results ({totalIdeas})
          </Button>
        </div>

        {ideasLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        ) : ideasData?.ideas.length ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {ideasData.ideas.slice(0, 6).map((idea) => (
              <ProposalCard key={idea.id} idea={idea} onClick={() => navigate(`/ideas/${idea.id}`)} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <FlaskConical className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No proposals yet. Start a run to generate research outputs.</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* ── Analytics ──────────────────────────────────────────── */}
      {hasChartData && (
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Analytics</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="card-shadow">
                <CardContent className="pt-6">
                  <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted-foreground mb-4">Score Distribution</h3>
                  <ScoreDistributionChart ideas={chartIdeas?.ideas ?? []} />
                </CardContent>
              </Card>
              <Card className="card-shadow">
                <CardContent className="pt-6">
                  <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted-foreground mb-4">Run Status</h3>
                  <RunStatusChart runs={chartRuns?.runs ?? []} />
                </CardContent>
              </Card>
            </div>
          </div>
        </Suspense>
      )}

      {showOnboarding && (
        <OnboardingOverlay
          onStartPipeline={(t) => navigate(`/pipeline/new?topic=${encodeURIComponent(t)}`)}
          onDismiss={() => setShowOnboarding(false)}
        />
      )}
    </div>
  );
}

// ── Proposal Card ────────────────────────────────────────────────

function ProposalCard({ idea, onClick }: { idea: IdeaSummary; onClick: () => void }) {
  return (
    <Card
      className="card-shadow card-shadow-hover transition-all duration-200 cursor-pointer"
      onClick={onClick}
      role="button"
      tabIndex={0}
      data-testid={`recent-output-${idea.id}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); }
      }}
    >
      <CardContent className="p-5 flex flex-col justify-between min-h-[200px]">
        <div>
          <div className="flex items-start justify-between gap-2 mb-3">
            <span className="text-[10px] font-mono text-muted-foreground uppercase bg-muted/50 border border-border px-2 py-0.5 rounded">
              {idea.domain}
            </span>
            {idea.has_proposal ? (
              <span className="text-[9px] bg-accent/10 text-accent px-2 py-0.5 rounded font-mono font-bold uppercase border border-accent/20">
                Proposal
              </span>
            ) : (
              <span className="text-[9px] text-muted-foreground px-2 py-0.5 rounded font-mono uppercase">
                Idea only
              </span>
            )}
          </div>

          <h3 className="text-sm font-semibold leading-snug line-clamp-2 mb-2 hover:text-accent transition-colors">
            {idea.title}
          </h3>

          <div className="grid grid-cols-3 gap-2 py-2.5 border-y border-border text-center font-mono text-[10px] text-muted-foreground bg-muted/30 rounded">
            <div>
              <span className="block text-xs font-semibold text-foreground">
                {idea.novelty_score != null ? (idea.novelty_score * 100).toFixed(0) : "—"}
              </span>
              <span>Novelty</span>
            </div>
            <div>
              <span className="block text-xs font-semibold text-foreground">
                {idea.feasibility_score != null ? idea.feasibility_score.toFixed(1) : "—"}
              </span>
              <span>Feasibility</span>
            </div>
            <div>
              <span className="block text-xs font-semibold text-foreground">
                {idea.overall_score != null ? idea.overall_score.toFixed(2) : "—"}
              </span>
              <span>Overall</span>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between text-xs">
          <span className="text-[10px] font-mono text-muted-foreground">
            #{idea.id}
          </span>
          <span className="text-xs font-semibold text-accent flex items-center gap-0.5">
            Open <ChevronRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
