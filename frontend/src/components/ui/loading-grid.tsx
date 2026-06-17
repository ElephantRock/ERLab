import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingGridProps {
  /** Number of skeleton rows to show (default: 3) */
  count?: number;
  /** Fixed height per row in px (default: 64) */
  rowHeight?: number;
  className?: string;
  testId?: string;
}

/**
 * Skeleton placeholder grid for loading states.
 * Renders `count` animated placeholder rows.
 */
export function LoadingGrid({
  count = 3,
  rowHeight = 64,
  className,
  testId = "loading-grid",
}: LoadingGridProps) {
  return (
    <div
      className={cn("space-y-2", className)}
      data-testid={testId}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          className="w-full rounded-lg"
          style={{ height: `${rowHeight}px` }}
        />
      ))}
    </div>
  );
}
