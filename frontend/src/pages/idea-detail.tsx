import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getIdea, refineIdea } from "@/api/ideas";
import { ScoreBadge } from "@/components/ideas/score-badge";
import { ExportButton } from "@/components/ideas/export-button";
import { FeedbackForm } from "@/components/ideas/feedback-form";
import { NoveltyReportView } from "@/components/ideas/novelty-report-view";
import { FeasibilityReportView } from "@/components/ideas/feasibility-report-view";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, Loader2 } from "lucide-react";
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
            {idea.novelty_score != null && (
              <ScoreBadge score={idea.novelty_score} scale="novelty" />
            )}
            {idea.feasibility_score != null && (
              <ScoreBadge score={idea.feasibility_score} scale="feasibility" />
            )}
            {idea.overall_score != null && (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                Overall: {idea.overall_score.toFixed(2)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ExportButton
            proposalMd={idea.proposal_md}
            proposalLatex={idea.proposal_latex}
            title={idea.title}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => refineMutation.mutate()}
            disabled={refineMutation.isPending}
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

      {(idea.proposal_md || idea.novelty_report || idea.feasibility_report) && (
        <Tabs defaultValue={idea.proposal_md ? "proposal" : idea.novelty_report ? "novelty" : "feasibility"}>
          <TabsList>
            {idea.proposal_md && <TabsTrigger value="proposal">Proposal</TabsTrigger>}
            {idea.novelty_report && <TabsTrigger value="novelty">Novelty Report</TabsTrigger>}
            {idea.feasibility_report && <TabsTrigger value="feasibility">Feasibility Report</TabsTrigger>}
          </TabsList>
          {idea.proposal_md && (
            <TabsContent value="proposal">
              <Card>
                <CardContent className="pt-6">
                  <MarkdownRenderer content={idea.proposal_md} />
                </CardContent>
              </Card>
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
        </Tabs>
      )}

      <FeedbackForm ideaId={ideaId} />
    </div>
  );
}
