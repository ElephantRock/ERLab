import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  message?: string;
  action?: React.ReactNode;
  className?: string;
  testId?: string;
}

/**
 * Consistent empty-state display for lists and pages.
 *
 * Shows an icon, title, optional message, and optional action button.
 */
export function EmptyState({
  icon: Icon,
  title,
  message,
  action,
  className,
  testId = "empty-state",
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center text-muted-foreground",
        className,
      )}
      data-testid={testId}
    >
      <Icon className="h-10 w-10 mb-3 opacity-40" />
      <p className="text-sm font-medium">{title}</p>
      {message && <p className="text-xs mt-1 max-w-sm">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
