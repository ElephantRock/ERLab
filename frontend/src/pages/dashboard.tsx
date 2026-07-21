/**
 * Dashboard — the action queue.
 *
 * PRODUCT.md anti-pattern "The Trophy Case": the old dashboard was a hero +
 * charts + stat cards that existed to display the pipeline's sophistication.
 * This version answers one question: what needs attention right now?
 *
 * PRODUCT.md anti-pattern "The Static Marketing Hero": the old dashboard had
 * a generic "Welcome to Research Studio" hero with marketing copy. Gone.
 *
 * The dashboard is now four queues, each answering "what should I do next":
 * - Is a run active? (DIRECT)
 * - What proposals need review? (JUDGE)
 * - What's flagged for quality? (REFINE)
 * - What's waiting for governance? (GOVERN)
 *
 * F1.3: Each of the four resources has an INDEPENDENT lifecycle. A failure
 * in one resource (e.g. governance) does not erase the data from another
 * (e.g. runs). A failed resource renders an explicit failure widget, NOT
 * an empty array or a zero count. A backend outage renders a degraded
 * dashboard with visible failures, not a calm dashboard that looks healthy.
 *
 * INTERFACE_CONTRACT compliance:
 * - §1 useResource (not raw useQuery)
 * - §3 ui-scale typography (no text-[8px]/[9px]/[10px], no telemetry headings)
 * - §7 truthful status (no SYS_OK, no pulsing dots without a real query)
 */

import { useResource } from "@/lib/useResource";
import { useNavigate } from "react-router-dom";
import {
  Play,
  ChevronRight,
  AlertTriangle,
  Shield,
  Clock,
  FlaskConical,
  Loader2,
  AlertCircle,
} from "lucide-react";

import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { getPending } from "@/api/governance";
import { getOpsDashboard } from "@/api/ops";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ── Per-widget failure indicator ────────────────────────────────────

function WidgetError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="border-destructive/20" data-testid="widget-error">
      <CardContent className="p-4 flex items-center gap-3">
        <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
        <p className="text-ui-meta text-muted-foreground flex-1">{message}</p>
        <Button variant="outline" size="sm" onClick={onRetry} data-testid="widget-retry">
          Retry
        </Button>
      </CardContent>
    </Card>
  );
}

function WidgetLoading({ label }: { label: string }) {
  return (
    <Card className="opacity-60">
      <CardContent className="p-4 flex items-center gap-3">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
        <p className="text-ui-meta text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();

  // Each queue uses useResource (the sanctioned fetch hook).
  // F1.3: resources remain INDEPENDENT — a failure in one does not collapse the others.
  const runs = useResource(["runs", { limit: 5 }], () => listRuns({ limit: 5 }));
  const ideas = useResource(["ideas", { limit: 6 }], () => listIdeas({ limit: 6 }));
  const governance = useResource(["governance-pending"], () => getPending());
  const ops = useResource(["ops-dashboard", 7], () => getOpsDashboard(7));

  // ── Derive data ONLY from ready resources ────────────────────────
  // Error/loading resources do NOT contribute to counts or data.
  const activeRun = runs.status === "ready" ? runs.data.runs.find((r) => r.status === "running") : null;
  const latestRun = runs.status === "ready" ? runs.data.runs[0] : null;
  const recentIdeas = ideas.status === "ready" ? ideas.data.ideas.filter((i) => i.has_proposal).slice(0, 4) : [];
  const governancePending = governance.status === "ready" ? governance.data.pending ?? [] : [];
  const qualityFailures = ops.status === "ready" ? ops.data.quality_trends?.common_failures ?? [] : [];
  const totalIdeas = ideas.status === "ready" ? ideas.data.total : 0;

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl mx-auto" data-testid="dashboard">
      {/* ── Active Run / Quick Start ──────────────────────────── */}
      {runs.status === "loading" ? (
        <WidgetLoading label="Loading runs..." />
      ) : runs.status === "error" ? (
        <WidgetError message="Failed to load runs" onRetry={runs.retry} />
      ) : activeRun ? (
        <Card className="card-shadow border-accent/20" data-testid="active-run-card">
          <CardContent className="p-5 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
              </span>
              <div>
                <p className="text-ui-label font-medium">{activeRun.domain}</p>
                <p className="text-ui-meta text-muted-foreground">
                  Running · {activeRun.current_stage ?? "processing"}
                </p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => navigate(`/runs/${activeRun.id}`)}>
              Watch progress <ChevronRight className="ml-1 h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card className="card-shadow" data-testid="quick-start">
          <CardContent className="p-5 flex items-center justify-between gap-4">
            <div>
              <p className="text-ui-heading font-display font-semibold">Start a new research run</p>
              <p className="text-ui-meta text-muted-foreground mt-0.5">
                Generate cited proposals from any research domain
              </p>
            </div>
            <Button onClick={() => navigate("/pipeline/new")} size="sm" data-testid="hero-new-run">
              <Play className="mr-2 h-4 w-4" />
              New Run
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── Needs Attention (governance + quality) ────────────── */}
      <div>
        <h2 className="text-ui-heading font-display font-semibold mb-3">Needs Attention</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {/* Governance widget — independent lifecycle */}
          {governance.status === "loading" ? (
            <WidgetLoading label="Loading governance queue..." />
          ) : governance.status === "error" ? (
            <WidgetError message="Failed to load governance queue" onRetry={governance.retry} />
          ) : governancePending.length > 0 ? (
            <ActionCard
              icon={Shield}
              title={`${governancePending.length} awaiting governance`}
              description="Proposals pending approval or denial"
              action="Review"
              onClick={() => navigate("/governance")}
              tone="warning"
              testId="action-governance"
            />
          ) : (
            <Card>
              <CardContent className="p-4 flex items-center gap-3 text-muted-foreground">
                <Shield className="h-4 w-4 opacity-50" />
                <p className="text-ui-meta">No governance items pending.</p>
              </CardContent>
            </Card>
          )}

          {/* Quality widget — independent lifecycle */}
          {ops.status === "loading" ? (
            <WidgetLoading label="Loading quality trends..." />
          ) : ops.status === "error" ? (
            <WidgetError message="Failed to load quality trends" onRetry={ops.retry} />
          ) : qualityFailures.length > 0 ? (
            <ActionCard
              icon={AlertTriangle}
              title={`${qualityFailures.reduce((a, f) => a + f.count, 0)} quality issues`}
              description={qualityFailures[0]?.failure ?? "Sections failing quality checks"}
              action="Fix"
              onClick={() => navigate("/ideas")}
              tone="warning"
              testId="action-quality"
            />
          ) : (
            <Card>
              <CardContent className="p-4 flex items-center gap-3 text-muted-foreground">
                <AlertTriangle className="h-4 w-4 opacity-50" />
                <p className="text-ui-meta">No quality issues detected.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ── Recent Proposals ──────────────────────────────────── */}
      <div>
        <div className="flex items-end justify-between mb-3">
          <div>
            <h2 className="text-ui-heading font-display font-semibold">Recent Proposals</h2>
            {ideas.status === "ready" && (
              <p className="text-ui-meta text-muted-foreground mt-0.5">
                {totalIdeas > 0 ? `${totalIdeas} total` : "No proposals yet"}
              </p>
            )}
          </div>
          {totalIdeas > 0 && (
            <Button variant="link" size="sm" className="p-0 text-ui-label text-accent"
              onClick={() => navigate("/ideas")}>
              All results <ChevronRight className="ml-0.5 h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {ideas.status === "loading" ? (
          <WidgetLoading label="Loading proposals..." />
        ) : ideas.status === "error" ? (
          <WidgetError message="Failed to load proposals" onRetry={ideas.retry} />
        ) : recentIdeas.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {recentIdeas.map((idea) => (
              <CompactProposalRow
                key={idea.id}
                title={idea.title}
                domain={idea.domain}
                noveltyScore={idea.novelty_score}
                feasibilityScore={idea.feasibility_score}
                hasIssues={idea.quality_summary?.has_issues}
                onClick={() => navigate(`/ideas/${idea.id}`)}
              />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <FlaskConical className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-ui-meta">
                {latestRun
                  ? "Proposals are still being generated."
                  : "Start a run to generate research proposals."}
              </p>
              {!latestRun && (
                <Button size="sm" className="mt-3" onClick={() => navigate("/pipeline/new")}>
                  <Play className="mr-2 h-3.5 w-3.5" />
                  Start First Run
                </Button>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* ── Latest Run (if no active run) ─────────────────────── */}
      {!activeRun && latestRun && (
        <div>
          <h2 className="text-ui-heading font-display font-semibold mb-3">Latest Run</h2>
          <Card className="card-shadow">
            <CardContent className="p-5 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-ui-label font-medium">{latestRun.domain}</p>
                  <p className="text-ui-meta text-muted-foreground">
                    {latestRun.status === "completed"
                      ? `Completed · ${new Date(latestRun.created_at).toLocaleDateString()}`
                      : latestRun.status}
                  </p>
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={() => navigate(`/runs/${latestRun.id}`)}>
                Open <ChevronRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────

function ActionCard({
  icon: Icon,
  title,
  description,
  action,
  onClick,
  tone,
  testId,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  action: string;
  onClick: () => void;
  tone: "warning" | "neutral";
  testId: string;
}) {
  return (
    <Card
      className="card-shadow card-shadow-hover transition-all cursor-pointer"
      onClick={onClick}
      role="button"
      tabIndex={0}
      data-testid={testId}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}
    >
      <CardContent className="p-5 flex items-center gap-3">
        <div className={cn(
          "flex items-center justify-center h-10 w-10 rounded-lg shrink-0",
          tone === "warning" ? "bg-warning/10 text-warning" : "bg-muted text-muted-foreground",
        )}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-ui-label font-medium truncate">{title}</p>
          <p className="text-ui-meta text-muted-foreground truncate">{description}</p>
        </div>
        <span className="text-ui-label text-accent font-medium flex items-center gap-0.5 shrink-0">
          {action} <ChevronRight className="h-3.5 w-3.5" />
        </span>
      </CardContent>
    </Card>
  );
}

function CompactProposalRow({
  title,
  domain,
  noveltyScore,
  feasibilityScore,
  hasIssues,
  onClick,
}: {
  title: string;
  domain: string;
  noveltyScore: number | null;
  feasibilityScore: number | null;
  hasIssues?: boolean;
  onClick: () => void;
}) {
  return (
    <Card
      className="card-shadow card-shadow-hover transition-all cursor-pointer"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="text-ui-label font-medium leading-snug line-clamp-2 flex-1">
            {title}
          </h3>
          {hasIssues && (
            <span className="text-ui-micro bg-warning/10 text-warning px-1.5 py-0.5 rounded font-medium shrink-0">
              issues
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-ui-micro text-muted-foreground">
          <span className="uppercase tracking-wider">{domain}</span>
          {noveltyScore != null && (
            <span>N: {(noveltyScore * 100).toFixed(0)}%</span>
          )}
          {feasibilityScore != null && (
            <span>F: {feasibilityScore.toFixed(1)}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
