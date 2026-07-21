/**
 * GovernancePanel — Decision panel + audit timeline for an idea.
 *
 * Shows:
 * 1. Decision buttons (approve / deny / needs_changes) with optional note
 * 2. Latest decision status badge
 * 3. Unified audit timeline (decisions, section revisions, comments)
 *
 * Governance panel is placed below the proposal — secondary to reading
 * the research output.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import {
  createGovernanceDecision,
  getGovernanceTimeline,
  type GovernanceDecisionType,
  type TimelineEvent,
} from "@/api/governance";
import { toast } from "sonner";
import {
  Shield,
  CheckCircle2,
  XCircle,
  AlertCircle,
  GitCommit,
  MessageSquare,
  History,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function GovernancePanel({ ideaId }: { ideaId: number }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [pendingDecision, setPendingDecision] = useState<GovernanceDecisionType | null>(null);

  const { data: timeline, isLoading, isError, error } = useQuery({
    queryKey: ["governance-timeline", ideaId],
    queryFn: () => getGovernanceTimeline(ideaId),
  });

  const decisionMutation = useMutation({
    mutationFn: (decision: GovernanceDecisionType) =>
      createGovernanceDecision(ideaId, decision, note.trim() || undefined),
    onMutate: (decision) => setPendingDecision(decision),
    onSuccess: () => {
      toast.success("Decision recorded");
      setNote("");
      setPendingDecision(null);
      queryClient.invalidateQueries({ queryKey: ["governance-timeline", ideaId] });
    },
    onError: (err: Error) => {
      toast.error("Failed to record decision", { description: err.message });
      setPendingDecision(null);
    },
  });

  // Find latest decision for status badge
  const latestDecision = timeline?.events.find((e) => e.type === "decision");

  return (
    <Card data-testid="governance-panel">
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Shield className="h-4 w-4" />
          Governance
          {latestDecision && (
            <DecisionBadge
              decision={latestDecision.detail.decision as GovernanceDecisionType}
            />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Decision buttons */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => decisionMutation.mutate("approved")}
              disabled={pendingDecision !== null}
              data-testid="gov-approve"
              className={cn(
                pendingDecision === "approved" && "opacity-50",
              )}
            >
              {pendingDecision === "approved" ? (
                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
              ) : (
                <CheckCircle2 className="mr-1.5 h-3 w-3 text-success" />
              )}
              Approve
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => decisionMutation.mutate("needs_changes")}
              disabled={pendingDecision !== null}
              data-testid="gov-needs-changes"
              className={cn(pendingDecision === "needs_changes" && "opacity-50")}
            >
              {pendingDecision === "needs_changes" ? (
                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
              ) : (
                <AlertCircle className="mr-1.5 h-3 w-3 text-warning" />
              )}
              Needs Changes
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => decisionMutation.mutate("denied")}
              disabled={pendingDecision !== null}
              data-testid="gov-deny"
              className={cn(pendingDecision === "denied" && "opacity-50")}
            >
              {pendingDecision === "denied" ? (
                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
              ) : (
                <XCircle className="mr-1.5 h-3 w-3 text-destructive" />
              )}
              Deny
            </Button>
          </div>
          <textarea
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder="Optional note explaining your decision..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            data-testid="gov-note-input"
          />
        </div>

        {/* Timeline */}
        <div className="space-y-2" data-testid="governance-timeline">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground uppercase tracking-wide">
            <History className="h-3 w-3" />
            Audit Timeline
          </div>

          {isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {isError && (
            <ErrorCard
              message="Failed to load timeline"
              error={error instanceof Error ? error.message : undefined}
            />
          )}

          {timeline && timeline.events.length === 0 && (
            <p className="text-sm text-muted-foreground py-2">
              No governance activity yet.
            </p>
          )}

          {timeline && timeline.events.length > 0 && (
            <div className="space-y-1.5">
              {timeline.events.map((event, idx) => (
                <TimelineEntry key={idx} event={event} />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DecisionBadge({ decision }: { decision: GovernanceDecisionType }) {
  const config = {
    approved: { label: "Approved", className: "text-success border-success/30" },
    denied: { label: "Denied", className: "text-destructive border-destructive/30" },
    needs_changes: { label: "Needs Changes", className: "text-warning border-warning/30" },
  };
  const c = config[decision];
  return (
    <Badge variant="outline" className={cn("text-xs", c.className)}>
      {c.label}
    </Badge>
  );
}

function TimelineEntry({ event }: { event: TimelineEvent }) {
  const icon = {
    decision: Shield,
    section_revision: GitCommit,
    comment: MessageSquare,
  }[event.type];

  const Icon = icon;

  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-muted p-2 text-xs"
      data-testid={`timeline-${event.type}`}
    >
      <Icon className="h-3 w-3 mt-0.5 flex-shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium">{event.summary}</span>
          <span className="text-muted-foreground whitespace-nowrap">
            {new Date(event.timestamp).toLocaleString()}
          </span>
        </div>
        <span className="text-muted-foreground">by {event.actor}</span>
        {event.type === "decision" && typeof event.detail.note === "string" && event.detail.note && (
          <p className="text-muted-foreground mt-1 italic">
            "{event.detail.note}"
          </p>
        )}
      </div>
    </div>
  );
}
