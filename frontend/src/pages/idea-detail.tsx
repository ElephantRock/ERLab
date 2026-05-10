import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getIdea, refineIdea } from "@/api/ideas";
import { ScoreBadge } from "@/components/ideas/score-badge";
import { ExportDialog } from "@/components/export/export-dialog";
import { FeedbackForm } from "@/components/ideas/feedback-form";
import { CommentThread } from "@/components/idea/comment-thread";
import { ShareDialog } from "@/components/idea/share-dialog";
import { NoveltyReportView } from "@/components/ideas/novelty-report-view";
import { FeasibilityReportView } from "@/components/ideas/feasibility-report-view";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, Loader2, GitBranch, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function IdeaDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const ideaId = Number(id);

  const { data, isLoading } = useQuery({
    queryKey: ["idea", ideaId],
    queryFn: () => getIdea(ideaId),
    enabled: !isNaN(ideaId),
  });

  const refineMutation = useMutation({
    mutationFn: () => refineIdea(ideaId),
    onSuccess: () => {
      toast.success("Idea refined — scores updated");
      queryClient.invalidateQueries({ queryKey: ["idea", ideaId] });
    },
    onError: (err) => {
      toast.error(err.message || "Refinement failed");
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!data?.idea) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p>Idea not found.</p>
      </div>
    );
  }

  const idea = data.idea;

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate("/ideas")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Ideas
        </Button>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{idea.title}</h1>
          <p className="text-muted-foreground mt-1">{idea.domain}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {idea.novelty_score != null ? (
              <ScoreBadge score={idea.novelty_score} scale="novelty" />
            ) : (
              <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                Novelty: Not scored
              </span>
            )}
            {idea.feasibility_score != null ? (
              <ScoreBadge score={idea.feasibility_score} scale="feasibility" />
            ) : (
              <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                Feasibility: Not scored
              </span>
            )}
            {idea.overall_score != null ? (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                Overall: {idea.overall_score.toFixed(2)}
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                Overall: Not scored — click Refine to generate scores
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ExportDialog
            ideaId={ideaId}
            title={idea.title}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => refineMutation.mutate()}
            disabled={refineMutation.isPending}
            title="Re-run novelty and feasibility scoring with updated parameters"
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

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Problem Statement</CardTitle>
        </CardHeader>
        <CardContent>
          <MarkdownRenderer content={idea.problem_statement} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Proposed Method</CardTitle>
        </CardHeader>
        <CardContent>
          <MarkdownRenderer content={idea.proposed_method} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Expected Contributions</CardTitle>
        </CardHeader>
        <CardContent>
          <MarkdownRenderer content={idea.expected_contributions} />
        </CardContent>
      </Card>

      {idea.source_gap_ids && idea.source_gap_ids.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Source Research Gaps
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {idea.source_gap_ids.map((gapId, idx) => (
                <li key={idx} className="flex items-center gap-2 text-sm">
                  <span className="inline-block h-2 w-2 rounded-full bg-amber-500 flex-shrink-0" />
                  <button
                    className="text-blue-600 hover:underline cursor-pointer bg-transparent border-none p-0"
                    onClick={() => navigate(`/gaps/${gapId}`)}
                    data-testid="source-gap-link"
                  >
                    {gapId}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {(idea.proposal_md || idea.novelty_report || idea.feasibility_report || idea.mechanical_metrics) && (
        <Tabs defaultValue={idea.proposal_md ? "proposal" : idea.novelty_report ? "novelty" : idea.feasibility_report ? "feasibility" : "metrics"}>
          <TabsList>
            {idea.proposal_md && <TabsTrigger value="proposal">Proposal</TabsTrigger>}
            {idea.novelty_report && <TabsTrigger value="novelty">Novelty Report</TabsTrigger>}
            {idea.feasibility_report && <TabsTrigger value="feasibility">Feasibility Report</TabsTrigger>}
            {idea.mechanical_metrics && <TabsTrigger value="metrics">Mechanical Metrics</TabsTrigger>}
            {idea.experiment_results && idea.experiment_results.length > 0 && (
              <TabsTrigger value="experiments">Experiments ({idea.experiment_results.length})</TabsTrigger>
            )}
          </TabsList>
          {idea.proposal_md && (
            <TabsContent value="proposal">
              <div className="grid gap-6 lg:grid-cols-4">
                {/* Table of Contents sidebar */}
                {idea.proposal_sections && typeof idea.proposal_sections === "object" && (
                  <Card className="lg:col-span-1">
                    <CardHeader>
                      <CardTitle className="text-sm">Contents</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <nav className="space-y-1">
                        {Object.keys(idea.proposal_sections).map((key) => (
                          <a
                            key={key}
                            href={`#section-${key}`}
                            className="block text-sm text-muted-foreground hover:text-foreground truncate"
                            onClick={(e) => {
                              e.preventDefault();
                              document.getElementById(`section-${key}`)?.scrollIntoView({ behavior: "smooth" });
                            }}
                          >
                            {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                          </a>
                        ))}
                      </nav>
                      <Separator className="my-3" />
                      <p className="text-xs text-muted-foreground">
                        {idea.proposal_md.split(/\s+/).length.toLocaleString()} words
                      </p>
                    </CardContent>
                  </Card>
                )}
                {/* Main proposal content */}
                <Card className={idea.proposal_sections ? "lg:col-span-3" : "lg:col-span-4"}>
                  <CardContent className="pt-6">
                    {idea.proposal_sections && typeof idea.proposal_sections === "object" ? (
                      /* Structured section rendering */
                      <div className="space-y-8">
                        {Object.entries(idea.proposal_sections).map(([key, value]) => (
                          <div key={key} id={`section-${key}`}>
                            <h3 className="text-lg font-semibold mb-3">
                              {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                            </h3>
                            {typeof value === "string" ? (
                              <MarkdownRenderer content={value} />
                            ) : Array.isArray(value) ? (
                              <div className="space-y-2">
                                {value.map((item: unknown, idx: number) => (
                                  <div key={idx} className="text-sm">
                                    {typeof item === "string" ? (
                                      <MarkdownRenderer content={item} />
                                    ) : typeof item === "object" && item !== null ? (
                                      <div className="text-muted-foreground">
                                        {Object.entries(item as Record<string, unknown>).map(
                                          ([k, v]) => (
                                            <span key={k} className="mr-3">
                                              <span className="font-medium">{k}:</span>{" "}
                                              {String(v)}
                                            </span>
                                          )
                                        )}
                                      </div>
                                    ) : (
                                      String(item)
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : typeof value === "object" && value !== null ? (
                              <div className="space-y-2">
                                {Object.entries(value as Record<string, unknown>).map(
                                  ([subKey, subVal]) => (
                                    <div key={subKey}>
                                      <span className="font-medium text-sm">
                                        {subKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}:
                                      </span>{" "}
                                      {Array.isArray(subVal) ? (
                                        <span className="text-sm text-muted-foreground">
                                          {subVal.join(", ")}
                                        </span>
                                      ) : (
                                        <span className="text-sm text-muted-foreground">
                                          {String(subVal)}
                                        </span>
                                      )}
                                    </div>
                                  )
                                )}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground">{String(value)}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      /* Fallback: raw markdown blob */
                      <MarkdownRenderer content={idea.proposal_md} />
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          )}
          {idea.novelty_report && (
            <TabsContent value="novelty">
              <Card>
                <CardContent className="pt-6">
                  <NoveltyReportView report={idea.novelty_report} />
                </CardContent>
              </Card>
            </TabsContent>
          )}
          {idea.feasibility_report && (
            <TabsContent value="feasibility">
              <Card>
                <CardContent className="pt-6">
                  <FeasibilityReportView report={idea.feasibility_report} />
                </CardContent>
              </Card>
            </TabsContent>
          )}
          {idea.mechanical_metrics && (
            <TabsContent value="metrics">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Mechanical Metrics (zero LLM)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(idea.mechanical_metrics).map(([key, value]) => (
                      <div key={key} className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground">
                          {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </p>
                        <p className="text-2xl font-bold">
                          {typeof value === "number" ? value.toFixed(3) : String(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          )}
          {idea.experiment_results && idea.experiment_results.length > 0 && (
            <TabsContent value="experiments">
              <div className="space-y-4">
                {idea.experiment_results.map((exp: { id: number; success: boolean; exit_code: number; execution_time_seconds: number; stdout?: string | null; error?: string | null; created_at: string }) => (
                  <Card key={exp.id}>
                    <CardContent className="pt-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {exp.success ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-destructive" />
                          )}
                          <span className="text-sm font-medium">
                            Experiment #{exp.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span>Exit: {exp.exit_code}</span>
                          <span>{exp.execution_time_seconds.toFixed(1)}s</span>
                          <span>{new Date(exp.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                      {exp.stdout && (
                        <pre className="text-xs bg-muted p-3 rounded overflow-x-auto max-h-48 mb-2">
                          {exp.stdout.slice(0, 2000)}
                        </pre>
                      )}
                      {exp.error && (
                        <p className="text-xs text-destructive">{exp.error}</p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          )}
        </Tabs>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <FeedbackForm ideaId={ideaId} />
          <div className="mt-6">
            <CommentThread ideaId={ideaId} />
          </div>
        </div>
        <div className="space-y-6">
          <ShareDialog ideaId={ideaId} />
        </div>
      </div>
    </div>
  );
}
