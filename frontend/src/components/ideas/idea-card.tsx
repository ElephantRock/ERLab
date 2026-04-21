import { Card, CardContent } from "@/components/ui/card";
import { ScoreBadge } from "@/components/ideas/score-badge";
import type { IdeaSummary } from "@/api/types";
import { Lightbulb } from "lucide-react";

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
            <Lightbulb className="h-5 w-5 text-amber-500" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium leading-tight line-clamp-2">{idea.title}</h3>
            <p className="text-xs text-muted-foreground mt-1">{idea.domain}</p>
            <div className="flex flex-wrap gap-2 mt-2">
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
