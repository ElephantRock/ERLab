import { Card, CardContent } from "@/components/ui/card";
import { ScoreBadge } from "@/components/ideas/score-badge";
import type { IdeaSummary, QualitySummary } from "@/api/types";
import {
  FileText, Lightbulb, Shield, BookOpen, CheckCircle2,
  AlertTriangle, Clock, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface IdeaCardProps {
  idea: IdeaSummary;
  onClick?: () => void;
}

export function IdeaCard({ idea, onClick }: IdeaCardProps) {
  const gov = idea.governance_status ?? null;
  const qs = idea.quality_summary ?? null;
  const refs = idea.reference_count ?? 0;

  return (
    <Card
      className="cursor-pointer transition-all hover:shadow-md hover:border-accent/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none group"
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`View idea: ${idea.title}`}
      data-testid={`idea-card-${idea.id}`}
    >
      <CardContent className="p-4 space-y-3">
        {/* ── Top row: Status badges ── */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {idea.has_proposal ? (
            <StatusPill icon={FileText} label="Proposal" tone="info" />
          ) : (
            <StatusPill icon={Lightbulb} label="Idea Only" tone="neutral" />
          )}
          {qs && qs.total > 0 && (
            <StatusPill
              icon={qs.has_issues ? AlertTriangle : CheckCircle2}
              label={`QC ${qs.passed}/${qs.total}`}
              tone={qs.has_issues ? "warning" : "success"}
            />
          )}
          {gov && (
            <StatusPill
              icon={Shield}
              label={gov.replace(/_/g, " ")}
              tone={
                gov === "approved" ? "success" :
                gov === "denied" ? "danger" :
                "warning"
              }
            />
          )}
          {idea.cited_count && idea.cited_count > 0 && (
            <StatusPill icon={BookOpen} label={`${idea.cited_count} cited`} tone="info" />
          )}
          {idea.supporting_count && idea.supporting_count > 0 && (
            <StatusPill icon={BookOpen} label={`${idea.supporting_count} supp.`} tone="neutral" />
          )}
        </div>

        {/* ── Title ── */}
        <h3 className="text-sm font-medium leading-snug line-clamp-2 group-hover:text-accent transition-colors">
          {idea.title}
        </h3>

        {/* ── Domain ── */}
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="font-mono uppercase tracking-wider bg-muted/40 border border-border px-1.5 py-0.5 rounded">
            {idea.domain}
          </span>
          <span className="flex items-center gap-0.5">
            <Clock className="h-2.5 w-2.5" />
            {formatDate(idea.created_at)}
          </span>
        </div>

        {/* ── Score bar ── */}
        <div className="flex items-center gap-2 pt-1 border-t border-border/40">
          {idea.overall_score != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground">Overall</span>
              <span className={cn(
                "text-sm font-bold font-mono",
                idea.overall_score >= 0.7 ? "text-success" :
                idea.overall_score >= 0.5 ? "text-warning" :
                "text-muted-foreground",
              )}>
                {idea.overall_score.toFixed(2)}
              </span>
            </div>
          )}
          {idea.novelty_score != null && (
            <ScoreBadge score={idea.novelty_score} scale="novelty" />
          )}
          {idea.feasibility_score != null && (
            <ScoreBadge score={idea.feasibility_score} scale="feasibility" />
          )}
          <ChevronRight className="h-4 w-4 text-muted-foreground/40 ml-auto group-hover:text-accent group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
}

// ── Sub-components ──

function StatusPill({
  icon: Icon,
  label,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  tone: "success" | "warning" | "danger" | "info" | "neutral";
}) {
  const toneConfig = {
    success: "bg-success/8 text-success border-success/20",
    warning: "bg-warning/8 text-warning border-warning/20",
    danger: "bg-destructive/8 text-destructive border-destructive/20",
    info: "bg-info/8 text-info border-info/20",
    neutral: "bg-muted/40 text-muted-foreground border-border",
  };
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide",
      toneConfig[tone],
    )}>
      <Icon className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
