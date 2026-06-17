import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { IdeaSummary } from "@/api/types";

interface IdeaListItemProps {
  idea: IdeaSummary;
  /** Override click navigation. Defaults to /ideas/:id */
  onClick?: () => void;
}

/**
 * Compact idea row for list contexts (dashboard, run detail, pipeline results).
 * Renders title, domain, and overall score badge.
 *
 * Uses <button> for keyboard accessibility.
 */
export function IdeaListItem({ idea, onClick }: IdeaListItemProps) {
  const navigate = useNavigate();

  return (
    <Card
      role="button"
      tabIndex={0}
      className="cursor-pointer hover:bg-accent/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={onClick ?? (() => navigate(`/ideas/${idea.id}`))}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          (onClick ?? (() => navigate(`/ideas/${idea.id}`)))();
        }
      }}
      data-testid={`idea-list-item-${idea.id}`}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium line-clamp-1">{idea.title}</p>
            <p className="text-xs text-muted-foreground">{idea.domain}</p>
          </div>
          {idea.overall_score != null && (
            <Badge variant="secondary" className="flex-shrink-0">
              {(idea.overall_score * 100).toFixed(0)}%
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
