/**
 * Idea Detail — The Reading Workspace.
 *
 * PRODUCT.md §1: "Reading is the center." The proposal body is the largest,
 * calmest, most carefully typeset surface in the product. Everything else
 * calibrates against it.
 *
 * INTERFACE_CONTRACT compliance:
 * - §1 useResource + DataView (not raw useQuery)
 * - §3 reading scale (prose-body 17px/1.7, prose-lede 19px/1.6, ui-micro floor)
 * - §6 ScoreReport (not flat ScoreBadge) — scores are inspectable
 * - §7 truthful status (no hardcoded indicators)
 *
 * Two-column layout on desktop:
 *   Left (2/3):  Proposal sections at reading scale, with refinement controls
 *   Right (1/3): Sticky review sidebar (quality, evidence, governance)
 *
 * Refinement is first-class (PRODUCT.md §4): fix-section, regenerate, feedback
 * are always within reach of the artifact they act on.
 */

import { useResource } from "@/lib/useResource";
import { DataView } from "@/components/ui/data-view";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getIdea, refineIdea } from "@/api/ideas";
import type { IdeaDetail } from "@/api/types";
import { ScoreReport, type ScoreAxis } from "@/components/ui/score-report";
import { ExportDialog } from "@/components/export/export-dialog";
import { FeedbackForm } from "@/components/ideas/feedback-form";
import { CommentThread } from "@/components/idea/comment-thread";
import { ShareDialog } from "@/components/idea/share-dialog";
import { NoveltyReportView } from "@/components/ideas/novelty-report-view";
import { FeasibilityReportView } from "@/components/ideas/feasibility-report-view";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { GovernancePanel } from "@/components/ideas/governance-panel";
import { FixSectionButton } from "@/components/ideas/fix-section-button";
import { RevisionHistoryDrawer } from "@/components/ideas/revision-history-drawer";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, RefreshCw, Loader2, CheckCircle2, AlertTriangle,
  Copy, Check, History, Shield,
  FlaskConical, BookOpen, ClipboardCheck,
} from "lucide-react";
import { toast } from "sonner";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { ExperimentResult } from "@/api/types";

export default function IdeaDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const ideaId = Number(id);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [revisionSection, setRevisionSection] = useState<string | null>(null);
  const [highlightedSection, setHighlightedSection] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"proposal" | "novelty" | "feasibility" | "metrics">("proposal");

  function handleJumpToSection(sectionKey: string) {
    const el = document.getElementById(`section-${sectionKey}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedSection(sectionKey);
      setTimeout(() => setHighlightedSection(null), 3000);
    }
  }

  // INTERFACE_CONTRACT §1: useResource is the only sanctioned fetch hook.
  const resource = useResource(
    ["idea", ideaId],
    () => getIdea(ideaId),
    { enabled: !isNaN(ideaId) },
  );

  const refineMutation = useMutation({
    mutationFn: () => refineIdea(ideaId),
    onSuccess: () => {
      toast.success("Idea refined — scores updated");
      queryClient.invalidateQueries({ queryKey: ["idea", ideaId] });
    },
    onError: () => toast.error("Refinement failed"),
  });

  function handleCopySection(sectionKey: string, content: string) {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedSection(sectionKey);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopiedSection(null), 2000);
    }).catch(() => toast.error("Failed to copy"));
  }

  // DataView handles loading/error/empty/ready states — page only writes the ready case.
  return (
    <DataView
      resource={resource}
      testId="idea-detail"
      loading={{ lines: 6 }}
      empty={{ what: "idea", icon: FlaskConical }}
    >
      {(data) => {
        const idea = data.idea;
        if (!idea) {
          return (
            <div className="text-center py-12 text-muted-foreground">
              <FlaskConical className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-ui-meta">Idea not found.</p>
            </div>
          );
        }

        // Derived: quality summary
        const qualityChecks = idea.quality_checks ?? [];
        const passedSections = qualityChecks.filter((q) => q.passed).length;
        const totalSections = qualityChecks.length;
        const allPassed = totalSections > 0 && passedSections === totalSections;
        const failingChecks = qualityChecks.filter((q) => !q.passed);
        const remediationHints = idea.remediation_hints ?? [];

        // ScoreReport axes: extract from novelty_report if available.
        const noveltyAxes = extractNoveltyAxes(idea.novelty_report);

        // Tabs
        const hasNovelty = !!idea.novelty_report;
        const hasFeasibility = !!idea.feasibility_report;
        const hasMetrics = !!idea.mechanical_metrics;
        const hasExperiments = idea.experiment_results && idea.experiment_results.length > 0;

        return (
          <div className="space-y-6 animate-fade-in" data-testid="idea-detail">
            {/* ── Back button ─────────────────────────────────── */}
            <div>
              <Button variant="ghost" size="sm" onClick={() => navigate("/ideas")} data-testid="back-to-ideas">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Results
              </Button>
            </div>

            {/* ── Title Bar ───────────────────────────────────── */}
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1 min-w-0">
                <h1 className="text-ui-display font-display font-semibold tracking-tight leading-tight">
                  {idea.title}
                </h1>
                <div className="flex items-center gap-3 mt-2 flex-wrap">
                  <span className="text-ui-micro text-muted-foreground uppercase tracking-wider bg-muted/50 border border-border px-2 py-0.5 rounded">
                    {idea.domain}
                  </span>
                  {/* INTERFACE_CONTRACT §6: ScoreReport replaces flat ScoreBadge */}
                  {idea.novelty_score != null && (
                    <ScoreReport
                      kind="novelty"
                      summary={idea.novelty_score}
                      axes={noveltyAxes}
                    />
                  )}
                  {idea.feasibility_score != null && (
                    <ScoreReport kind="feasibility" summary={idea.feasibility_score} />
                  )}
                  {qualityChecks.length > 0 && (
                    <span className={cn(
                      "text-ui-micro font-semibold px-2 py-0.5 rounded border",
                      allPassed
                        ? "bg-success/5 text-success border-success/20"
                        : "bg-warning/5 text-warning border-warning/20",
                    )}>
                      {passedSections}/{totalSections} {allPassed ? "PASS" : "ISSUES"}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* PRODUCT.md §4: refinement is first-class, not buried */}
                <ExportDialog ideaId={ideaId} title={idea.title} />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refineMutation.mutate()}
                  disabled={refineMutation.isPending}
                  title="Re-run novelty and feasibility scoring"
                >
                  {refineMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Refine
                </Button>
              </div>
            </div>

            <Separator />

            {/* ── Two-Column Workspace ────────────────────────── */}
            <div className="grid gap-6 lg:grid-cols-3">
              {/* ══ LEFT: Reading Area ══════════════════════════ */}
              <div className="lg:col-span-2 space-y-6">
                {/* Tab selector */}
                <div className="flex items-center gap-1 border-b border-border pb-px">
                  <TabButton active={activeTab === "proposal"} onClick={() => setActiveTab("proposal")}>
                    <ClipboardCheck className="h-3.5 w-3.5" />
                    Proposal
                  </TabButton>
                  {hasNovelty && (
                    <TabButton active={activeTab === "novelty"} onClick={() => setActiveTab("novelty")}>
                      Novelty Report
                    </TabButton>
                  )}
                  {hasFeasibility && (
                    <TabButton active={activeTab === "feasibility"} onClick={() => setActiveTab("feasibility")}>
                      Feasibility Report
                    </TabButton>
                  )}
                  {hasMetrics && (
                    <TabButton active={activeTab === "metrics"} onClick={() => setActiveTab("metrics")}>
                      Metrics
                    </TabButton>
                  )}
                </div>

                {/* ── Proposal Sections (main reading area) ── */}
                {activeTab === "proposal" && (
                  <div className="space-y-6">
                    {/* Summary cards */}
                    <div className="grid gap-3 sm:grid-cols-3">
                      <SummaryCard label="Problem" icon={AlertTriangle}>
                        <p className="text-ui-caption text-muted-foreground line-clamp-3">
                          {idea.problem_statement?.slice(0, 150) ?? "—"}...
                        </p>
                      </SummaryCard>
                      <SummaryCard label="Method" icon={FlaskConical}>
                        <p className="text-ui-caption text-muted-foreground line-clamp-3">
                          {idea.proposed_method?.slice(0, 150) ?? "—"}...
                        </p>
                      </SummaryCard>
                      <SummaryCard label="Contributions" icon={CheckCircle2}>
                        <p className="text-ui-caption text-muted-foreground line-clamp-3">
                          {idea.expected_contributions?.slice(0, 150) ?? "—"}...
                        </p>
                      </SummaryCard>
                    </div>

                    {/* ── The Proposal Body — reading scale ── */}
                    {idea.proposal_md ? (
                      <Card className="card-shadow">
                        <CardContent className="pt-6">
                          {/* Section navigation strip */}
                          {idea.proposal_sections && typeof idea.proposal_sections === "object" && (
                            <div className="flex flex-wrap gap-1 mb-6 pb-4 border-b border-border">
                              {Object.keys(idea.proposal_sections)
                                .filter((key) => key !== "ensemble_review")
                                .map((key) => (
                                  <a
                                    key={key}
                                    href={`#section-${key}`}
                                    className="text-ui-micro text-muted-foreground hover:text-accent hover:bg-accent/5 px-2 py-0.5 rounded transition-colors"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      document.getElementById(`section-${key}`)?.scrollIntoView({ behavior: "smooth" });
                                    }}
                                  >
                                    {formatSectionLabel(key)}
                                  </a>
                                ))}
                              <span className="text-ui-micro text-muted-foreground/50 ml-auto self-center">
                                {idea.proposal_md.split(/\s+/).length.toLocaleString()} words
                              </span>
                            </div>
                          )}

                          {/* Structured sections at reading scale */}
                          {idea.proposal_sections && typeof idea.proposal_sections === "object" ? (
                            <div className="space-y-8">
                              {Object.entries(idea.proposal_sections)
                                .filter(([key]) => key !== "ensemble_review")
                                .map(([key, value]) => (
                                  <div
                                    key={key}
                                    id={`section-${key}`}
                                    className={cn(
                                      "scroll-mt-20 rounded-lg p-2 -m-2 transition-all",
                                      highlightedSection === key && "highlight-ring",
                                    )}
                                    data-testid={`section-${key}`}
                                  >
                                    {/* Section header with actions */}
                                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-border/50">
                                      <h3 className="text-ui-heading font-display font-semibold">
                                        {formatSectionLabel(key)}
                                      </h3>
                                      <div className="flex items-center gap-0.5">
                                        {/* Quality indicator */}
                                        {(() => {
                                          const qc = qualityChecks.find((c) => c.section === key);
                                          if (!qc) return null;
                                          return (
                                            <span
                                              className={cn(
                                                "text-ui-micro font-semibold px-1.5 py-0.5 rounded",
                                                qc.passed
                                                  ? "text-success bg-success/5"
                                                  : "text-warning bg-warning/5",
                                              )}
                                              title={qc.failures.join(", ")}
                                            >
                                              {qc.passed ? "✓" : "!"}
                                            </span>
                                          );
                                        })()}
                                        {/* Fix button — PRODUCT.md §4: within reach */}
                                        {(() => {
                                          const qc = qualityChecks.find((c) => c.section === key);
                                          const hints = remediationHints.filter(
                                            (h) => h.section === key && h.refinement_available,
                                          );
                                          const hash = idea.section_hashes?.[key] ?? "";
                                          if (qc && !qc.passed && hash && hints.length > 0) {
                                            return (
                                              <FixSectionButton
                                                ideaId={ideaId}
                                                sectionKey={key}
                                                sectionLabel={formatSectionLabel(key)}
                                                currentHash={hash}
                                                failureHints={qc.failures}
                                              />
                                            );
                                          }
                                          return null;
                                        })()}
                                        {/* Revision history toggle */}
                                        {idea.section_hashes?.[key] && (
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setRevisionSection(revisionSection === key ? null : key)}
                                            data-testid={`revision-toggle-${key}`}
                                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                                          >
                                            <History className="h-3 w-3" />
                                          </Button>
                                        )}
                                        {/* Copy */}
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => handleCopySection(key, typeof value === "string" ? value : JSON.stringify(value, null, 2))}
                                          data-testid={`copy-section-${key}`}
                                          className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                                        >
                                          {copiedSection === key ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                                        </Button>
                                      </div>
                                    </div>

                                    {/* Section content — READING SCALE */}
                                    <div className="text-prose-body">
                                      <SectionContent value={value} />
                                    </div>

                                    {/* Inline revision drawer */}
                                    {revisionSection === key && idea.section_hashes?.[key] && (
                                      <div className="mt-4 border-l-2 border-accent/20 pl-3">
                                        <RevisionHistoryDrawer
                                          ideaId={ideaId}
                                          sectionKey={key}
                                          sectionLabel={formatSectionLabel(key)}
                                          currentHash={idea.section_hashes[key]}
                                        />
                                      </div>
                                    )}
                                  </div>
                                ))}
                            </div>
                          ) : (
                            <div className="text-prose-body">
                              <MarkdownRenderer content={idea.proposal_md} />
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ) : (
                      <Card>
                        <CardContent className="p-8 text-center text-muted-foreground">
                          <ClipboardCheck className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p className="text-ui-meta">No proposal generated for this idea.</p>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}

                {/* ── Novelty Report ── */}
                {activeTab === "novelty" && hasNovelty && (
                  <Card className="card-shadow">
                    <CardContent className="pt-6">
                      <NoveltyReportView report={idea.novelty_report!} />
                    </CardContent>
                  </Card>
                )}

                {/* ── Feasibility Report ── */}
                {activeTab === "feasibility" && hasFeasibility && (
                  <Card className="card-shadow">
                    <CardContent className="pt-6">
                      <FeasibilityReportView report={idea.feasibility_report!} />
                    </CardContent>
                  </Card>
                )}

                {/* ── Mechanical Metrics ── */}
                {activeTab === "metrics" && hasMetrics && (
                  <Card className="card-shadow">
                    <CardContent className="pt-6">
                      <h3 className="text-ui-heading font-semibold text-muted-foreground mb-4">
                        Mechanical Metrics
                      </h3>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {Object.entries(idea.mechanical_metrics!).map(([key, value]) => (
                          <div key={key} className="rounded-lg border border-border p-3 bg-muted/20">
                            <p className="text-ui-caption text-muted-foreground">
                              {formatSectionLabel(key)}
                            </p>
                            <p className="text-ui-display font-bold font-display">
                              {typeof value === "number" ? value.toFixed(3) : String(value)}
                            </p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* ── Experiments ── */}
                {hasExperiments && (activeTab === "metrics" || (activeTab === "proposal" && !hasMetrics)) && (
                  <div className="space-y-3">
                    <h3 className="text-ui-heading font-semibold text-muted-foreground">
                      Experiment Results
                    </h3>
                    {idea.experiment_results!.map((exp: ExperimentResult) => (
                      <Card key={exp.id}>
                        <CardContent className="pt-4">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {exp.success ? (
                                <CheckCircle2 className="h-4 w-4 text-success" />
                              ) : (
                                <AlertTriangle className="h-4 w-4 text-destructive" />
                              )}
                              <span className="text-ui-label font-medium">Experiment #{exp.id}</span>
                            </div>
                            <div className="flex items-center gap-3 text-ui-meta text-muted-foreground">
                              <span>Exit: {exp.exit_code}</span>
                              <span>{exp.execution_time_seconds.toFixed(1)}s</span>
                            </div>
                          </div>
                          {exp.stdout && (
                            <pre className="text-ui-meta bg-muted p-3 rounded overflow-x-auto max-h-48 mb-2">
                              {exp.stdout.slice(0, 2000)}
                            </pre>
                          )}
                          {exp.error && <p className="text-ui-meta text-destructive">{exp.error}</p>}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}

                {/* ── Feedback + Comments ── */}
                <div className="grid gap-6 sm:grid-cols-2">
                  <FeedbackForm ideaId={ideaId} />
                  <CommentThread ideaId={ideaId} />
                </div>
              </div>

              {/* ══ RIGHT: Review Sidebar ═══════════════════════ */}
              <div className="lg:col-span-1">
                <div className="sticky top-6 space-y-4" data-testid="review-sidebar">
                  {/* Quality Summary */}
                  <ReviewCard
                    icon={ClipboardCheck}
                    title="Quality Checks"
                    status={allPassed ? "success" : failingChecks.length > 0 ? "warning" : "neutral"}
                    statusLabel={allPassed ? "All Passed" : `${failingChecks.length} Issues`}
                  >
                    {totalSections > 0 ? (
                      <>
                        <div className="flex items-baseline gap-2 mb-3">
                          <span className={cn("text-ui-display font-bold", allPassed ? "text-success" : "text-warning")}>
                            {passedSections}/{totalSections}
                          </span>
                          <span className="text-ui-caption text-muted-foreground">sections passed</span>
                        </div>
                        {failingChecks.length > 0 && (
                          <div className="space-y-1.5">
                            {failingChecks.map((qc) => (
                              <div
                                key={qc.section}
                                className="flex items-center gap-2 text-ui-caption cursor-pointer hover:text-accent transition-colors"
                                onClick={() => handleJumpToSection(qc.section)}
                                role="button"
                                tabIndex={0}
                              >
                                <span className="h-1.5 w-1.5 rounded-full bg-warning shrink-0" />
                                <span className="flex-1 truncate">{qc.label}</span>
                                <span className="text-muted-foreground">{qc.failures.length}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-ui-caption text-muted-foreground italic">No quality checks available.</p>
                    )}
                  </ReviewCard>

                  {/* Remediation Hints */}
                  {remediationHints.length > 0 && (
                    <ReviewCard
                      icon={AlertTriangle}
                      title="Remediation Hints"
                      status="warning"
                      statusLabel={`${remediationHints.filter(h => h.refinement_available).length} Fixable`}
                    >
                      <div className="space-y-2">
                        {remediationHints.slice(0, 6).map((hint, idx) => (
                          <div key={idx} className="text-ui-caption space-y-0.5">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={cn(
                                  "h-1.5 w-1.5 rounded-full shrink-0",
                                  hint.severity === "error" ? "bg-destructive" : "bg-warning",
                                )}
                              />
                              <span className="font-medium truncate">{hint.label}</span>
                              {hint.refinement_available && (
                                <Badge variant="outline" className="text-ui-micro py-0 px-1 text-accent border-accent/20">
                                  Fixable
                                </Badge>
                              )}
                            </div>
                            <p className="text-muted-foreground pl-3">{hint.message}</p>
                            {hint.refinement_available && (
                              <button
                                className="text-accent hover:underline pl-3 text-ui-micro"
                                onClick={() => handleJumpToSection(hint.section)}
                              >
                                Jump to section →
                              </button>
                            )}
                          </div>
                        ))}
                        {remediationHints.length > 6 && (
                          <p className="text-ui-micro text-muted-foreground italic">
                            +{remediationHints.length - 6} more
                          </p>
                        )}
                      </div>
                    </ReviewCard>
                  )}

                  {/* Evidence / Provenance Summary */}
                  <ReviewCard
                    icon={BookOpen}
                    title="Evidence & Provenance"
                    status="neutral"
                    statusLabel={idea.proposal_references ? "Traced" : "Partial"}
                  >
                    <EvidenceSummary idea={idea} />
                  </ReviewCard>

                  {/* Governance */}
                  <ReviewCard
                    icon={Shield}
                    title="Governance"
                    status="neutral"
                    statusLabel="Decision"
                  >
                    <GovernancePanel ideaId={ideaId} />
                  </ReviewCard>

                  {/* Share */}
                  <ReviewCard
                    icon={ShareDialog}
                    title="Share & Export"
                    status="neutral"
                  >
                    <ShareDialog ideaId={ideaId} />
                  </ReviewCard>
                </div>
              </div>
            </div>
          </div>
        );
      }}
    </DataView>
  );
}

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════

function formatSectionLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Extract novelty axes from the novelty_report for ScoreReport. */
function extractNoveltyAxes(report: Record<string, unknown> | null): ScoreAxis[] | undefined {
  if (!report) return undefined;
  const axisKeys = ["method_novelty", "problem_novelty", "domain_transfer", "combination_novelty"];
  const axes: ScoreAxis[] = [];
  for (const key of axisKeys) {
    const val = report[key];
    if (typeof val === "number") {
      axes.push({ name: formatSectionLabel(key), score: val, weight: 0 });
    }
  }
  return axes.length > 0 ? axes : undefined;
}

// ═══════════════════════════════════════════════════════════════
// Sub-components (restyled to reading/UI scale)
// ═══════════════════════════════════════════════════════════════

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-ui-label font-medium border-b-2 transition-colors",
        active
          ? "border-accent text-accent"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function SummaryCard({
  label,
  icon: Icon,
  children,
}: {
  label: string;
  icon: React.ElementType;
  children: ReactNode;
}) {
  return (
    <Card className="card-shadow">
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <Icon className="h-3 w-3 text-muted-foreground" />
          {/* Sentence-case ui-heading — NOT telemetry font-mono uppercase */}
          <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

function ReviewCard({
  icon: Icon,
  title,
  status,
  statusLabel,
  children,
}: {
  icon: React.ElementType;
  title: string;
  status: "success" | "warning" | "neutral";
  statusLabel?: string;
  children: ReactNode;
}) {
  const statusConfig = {
    success: "bg-success/5 text-success border-success/20",
    warning: "bg-warning/5 text-warning border-warning/20",
    neutral: "bg-muted/30 text-muted-foreground border-border",
  };
  return (
    <Card className="card-shadow">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-border/50">
          <div className="flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 text-muted-foreground" />
            {/* Sentence-case — not telemetry heading */}
            <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
              {title}
            </span>
          </div>
          {statusLabel && (
            <span className={cn("text-ui-micro font-semibold px-2 py-0.5 rounded border", statusConfig[status])}>
              {statusLabel}
            </span>
          )}
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

function EvidenceSummary({ idea }: { idea: IdeaDetail }) {
  const refs = idea.proposal_references;
  const supportingPapers = idea.supporting_papers ?? [];
  const sourceGaps = idea.source_gaps;

  const refCount = Array.isArray(refs) ? refs.length : typeof refs === "string" ? 1 : 0;
  const citedCount = supportingPapers.filter((p) => p.role === "cited").length;
  const supportingCount = supportingPapers.filter((p) => p.role === "supporting").length;
  const gapCount = Array.isArray(sourceGaps) ? sourceGaps.length : 0;
  const unresolvedCount = refCount - citedCount - supportingCount;

  return (
    <div className="space-y-2 text-ui-caption">
      <EvidenceRow label="Cited Papers" value={citedCount} tone="info" />
      <EvidenceRow label="Supporting Papers" value={supportingCount} tone="neutral" />
      <EvidenceRow label="Total References" value={refCount} />
      {unresolvedCount > 0 && (
        <EvidenceRow label="Unresolved" value={unresolvedCount} tone="warning" />
      )}
      <EvidenceRow label="Source Gaps" value={gapCount} />
      {refCount === 0 && citedCount === 0 && supportingCount === 0 && (
        <p className="text-muted-foreground italic text-ui-micro">No provenance data linked.</p>
      )}
    </div>
  );
}

function EvidenceRow({ label, value, tone }: { label: string; value: number; tone?: "info" | "warning" | "neutral" }) {
  const valueColor = {
    info: "text-info",
    warning: "text-warning",
    neutral: "text-foreground",
  };
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn(
        "font-mono font-semibold",
        value > 0 ? (tone ? valueColor[tone] : "text-foreground") : "text-muted-foreground",
      )}>
        {value}
      </span>
    </div>
  );
}

function SectionContent({ value }: { value: unknown }) {
  if (typeof value === "string") {
    return <MarkdownRenderer content={value} />;
  }
  if (Array.isArray(value)) {
    return (
      <div className="space-y-2">
        {value.map((item, idx) => (
          <div key={idx}>
            {typeof item === "string" ? (
              <MarkdownRenderer content={item} />
            ) : typeof item === "object" && item !== null ? (
              <div className="text-ui-meta text-muted-foreground">
                {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                  <span key={k} className="mr-3">
                    <span className="font-medium">{k}:</span> {String(v)}
                  </span>
                ))}
              </div>
            ) : (
              String(item)
            )}
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object" && value !== null) {
    return (
      <div className="space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([subKey, subVal]) => (
          <div key={subKey}>
            <span className="font-medium text-ui-label">
              {formatSectionLabel(subKey)}:
            </span>{" "}
            {Array.isArray(subVal) ? (
              <span className="text-ui-meta text-muted-foreground">{subVal.join(", ")}</span>
            ) : (
              <span className="text-ui-meta text-muted-foreground">{String(subVal)}</span>
            )}
          </div>
        ))}
      </div>
    );
  }
  return <p className="text-ui-meta text-muted-foreground">{String(value)}</p>;
}
