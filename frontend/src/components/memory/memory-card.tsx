/**
 * MemoryCard — BATCH-19/TASK-01
 *
 * Displays a single memory entry with content preview, type badge,
 * confidence indicator, creation date, and optional delete button.
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MemoryRecallResult } from "@/api/memory";

interface MemoryCardProps {
  memory: MemoryRecallResult;
  /** When provided, shows a delete button that triggers this callback. */
  onDelete?: (memory: MemoryRecallResult) => void;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-500";
  if (confidence >= 0.6) return "bg-emerald-500";
  if (confidence >= 0.3) return "bg-amber-500";
  return "bg-red-500";
}

function typeBadgeVariant(type: string): "default" | "secondary" | "outline" {
  switch (type) {
    case "semantic":
      return "default";
    case "episodic":
      return "secondary";
    default:
      return "outline";
  }
}

export function MemoryCard({ memory, onDelete }: MemoryCardProps) {
  const createdDate = memory.created_at
    ? new Date(memory.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "Unknown date";

  return (
    <Card data-testid="memory-card">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm leading-relaxed">{memory.content}</p>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant={typeBadgeVariant(memory.type)} className="text-xs">
                {memory.type}
              </Badge>
              <span className="text-xs text-muted-foreground">{createdDate}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">
                {(memory.confidence * 100).toFixed(0)}%
              </span>
              <div className="h-2 w-14 rounded-full bg-secondary overflow-hidden">
                <div
                  className={cn("h-full rounded-full", confidenceColor(memory.confidence))}
                  style={{ width: `${memory.confidence * 100}%` }}
                  data-testid="confidence-bar"
                />
              </div>
            </div>
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                onClick={() => onDelete(memory)}
                aria-label="Delete memory"
                data-testid="delete-memory-btn"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
