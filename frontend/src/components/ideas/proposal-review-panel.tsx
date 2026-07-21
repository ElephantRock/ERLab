import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CheckCircle2, AlertTriangle, Lightbulb, Shield, Eye, Sparkles, FileQuestion } from "lucide-react";
import type { EnsembleReview, PerspectiveReview } from "@/api/types";
import { cn } from "@/lib/utils";

function scoreColor(score: number): string {
  if (score >= 0.75) return "text-success";
  if (score >= 0.5) return "text-warning";
  return "text-destructive";
}

function scoreLabel(score: number): string {
  if (score >= 0.8) return "Strong";
  if (score >= 0.6) return "Good";
  if (score >= 0.4) return "Fair";
  return "Weak";
}

function PerspectiveRow({ label, review }: { label: string; review: PerspectiveReview | null }) {
  if (!review) return null;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
        <div className="flex items-center gap-2">
          <span className={cn("text-sm font-mono font-bold", scoreColor(review.score))}>
            {(review.score * 100).toFixed(0)}
          </span>
          <Badge variant="outline" className={cn("text-xs", scoreColor(review.score))}>
            {scoreLabel(review.score)}
          </Badge>
        </div>
      </div>
      {review.strengths.length > 0 && (
        <ul className="space-y-0.5 ml-3">
          {review.strengths.slice(0, 3).map((s, i) => (
            <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
              <CheckCircle2 className="h-3 w-3 text-success flex-shrink-0 mt-0.5" />
              {s}
            </li>
          ))}
        </ul>
      )}
      {review.weaknesses.length > 0 && (
        <ul className="space-y-0.5 ml-3">
          {review.weaknesses.slice(0, 3).map((w, i) => (
            <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
              <AlertTriangle className="h-3 w-3 text-destructive flex-shrink-0 mt-0.5" />
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ProposalReviewPanel({
  proposalSections,
}: {
  proposalSections: Record<string, unknown> | null;
}) {
  const review = useMemo<EnsembleReview | null>(() => {
    if (!proposalSections) return null;
    const raw = proposalSections.ensemble_review;
    if (!raw || typeof raw !== "object") return null;
    if (Array.isArray(raw)) return null;  // arrays are objects in JS
    return raw as EnsembleReview;
  }, [proposalSections]);

  // No proposal at all
  if (!proposalSections) {
    return (
      <Card data-testid="proposal-review-panel">
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Proposal Review
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={FileQuestion}
            title="No proposal synthesized"
            message="This idea has not been through proposal synthesis yet."
          />
        </CardContent>
      </Card>
    );
  }

  // Proposal exists but no ensemble review
  if (!review) {
    return (
      <Card data-testid="proposal-review-panel">
        <CardHeader>
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Proposal Review
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={FileQuestion}
            title="No review data"
            message="Ensemble review was not run for this proposal. This may indicate the ensemble reviewer was disabled during the run."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="proposal-review-panel">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Proposal Review
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Overall</span>
            <span
              className={cn("text-lg font-mono font-bold", scoreColor(review.overall_score))}
              data-testid="review-overall-score"
            >
              {(review.overall_score * 100).toFixed(0)}
            </span>
            <Badge variant="outline" className={cn("text-xs", scoreColor(review.overall_score))}>
              {scoreLabel(review.overall_score)}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary */}
        {review.summary && (
          <div className="p-3 rounded-lg bg-muted/50 border" data-testid="review-summary">
            <p className="text-sm italic text-muted-foreground">"{review.summary}"</p>
          </div>
        )}

        {/* Per-perspective scores */}
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Perspective Scores
          </h4>
          <PerspectiveRow label="Methodology" review={review.methodology} />
          <PerspectiveRow label="Novelty" review={review.novelty} />
          <PerspectiveRow label="Clarity" review={review.clarity} />
        </div>

        {/* Consensus Strengths */}
        {review.consensus_strengths.length > 0 && (
          <div className="space-y-2" data-testid="review-strengths">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
              <Sparkles className="h-3 w-3 text-success" />
              Consensus Strengths
            </h4>
            <ul className="space-y-1">
              {review.consensus_strengths.map((s, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0 mt-0.5" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Critical Weaknesses */}
        {review.critical_weaknesses.length > 0 && (
          <div className="space-y-2" data-testid="review-weaknesses">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
              <AlertTriangle className="h-3 w-3 text-destructive" />
              Critical Weaknesses
            </h4>
            <ul className="space-y-1">
              {review.critical_weaknesses.map((w, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risk Flags */}
        {review.risk_flags && review.risk_flags.length > 0 && (
          <div className="space-y-2 p-3 rounded-lg border border-destructive/30 bg-destructive/5" data-testid="review-risk-flags">
            <h4 className="text-xs font-semibold text-destructive uppercase tracking-wide flex items-center gap-1">
              <Shield className="h-3 w-3" />
              Risk Flags
            </h4>
            <ul className="space-y-1">
              {review.risk_flags.map((flag, i) => (
                <li key={i} className="text-sm flex items-start gap-2 text-destructive">
                  <Shield className="h-4 w-4 flex-shrink-0 mt-0.5" />
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actionable Suggestions */}
        {review.actionable_suggestions.length > 0 && (
          <div className="space-y-2" data-testid="review-suggestions">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
              <Lightbulb className="h-3 w-3 text-info" />
              Actionable Suggestions
            </h4>
            <ul className="space-y-1">
              {review.actionable_suggestions.map((s, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <Eye className="h-4 w-4 text-info flex-shrink-0 mt-0.5" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
