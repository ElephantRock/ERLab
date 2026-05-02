/**
 * MemoryStats — BATCH-19/TASK-01
 *
 * Displays memory system statistics: total count and per-type breakdown.
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Brain } from "lucide-react";
import type { MemoryStats as MemoryStatsData } from "@/api/memory";

interface MemoryStatsProps {
  stats: MemoryStatsData;
}

export function MemoryStats({ stats }: MemoryStatsProps) {
  return (
    <Card data-testid="memory-stats">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Brain className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-2xl font-bold" data-testid="total-memories">
              {stats.total_memories}
            </p>
            <p className="text-xs text-muted-foreground">Total Memories</p>
          </div>
          <div className="flex flex-wrap gap-1.5" data-testid="type-breakdown">
            {Object.entries(stats.by_type).map(([type, count]) =>
              count > 0 ? (
                <Badge key={type} variant="outline" className="text-xs">
                  {type}: {count}
                </Badge>
              ) : null,
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
