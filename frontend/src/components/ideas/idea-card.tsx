import { Card, CardContent } from "@/components/ui/card";
import { ScoreBadge } from "@/components/ideas/score-badge";
import type { IdeaSummary } from "@/api/types";
import { Lightbulb, FileText } from "lucide-react";

interface IdeaCardProps {
  idea: IdeaSummary;
  onClick?: () => void;
}

export function IdeaCard({ idea, onClick }: IdeaCardProps) {
  return (
    <Card className="cursor-pointer transition-colors hover:bg-accent/50" onClick={onClick}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <Lightbulb className="h-5 w-5 text-warning" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-2">
              <h3 className="text-sm font-medium leading-tight line-clamp-2 flex-1">{idea.title}</h3>
              {idea.has_proposal && (
                <FileText
                  className="h-4 w-4 text-info flex-shrink-0 mt-0.5"
                  aria-label="Has proposal"
                />
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">{idea.domain}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {idea.overall_score != null && (
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  Score: {idea.overall_score.toFixed(2)}
                </span>
              )}
              {idea.novelty_score != null && (
                <ScoreBadge score={idea.novelty_score} scale="novelty" />
              )}
              {idea.feasibility_score != null && (
                <ScoreBadge score={idea.feasibility_score} scale="feasibility" />
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
