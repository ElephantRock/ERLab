import * as React from "react";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ErrorCardProps {
  message: string;
  error?: string;
  className?: string;
  /** Optional data-testid override (defaults to "error-card") */
  testId?: string;
}

/**
 * Inline error display for query failures.
 * Shows a primary message and optional raw error detail.
 *
 * Convention: mutations → toast.error(), queries → <ErrorCard>
 */
export const ErrorCard = React.forwardRef<HTMLDivElement, ErrorCardProps>(
  ({ message, error, className, testId = "error-card" }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive",
        className,
      )}
      data-testid={testId}
      role="alert"
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 flex-shrink-0" />
        <p className="font-medium">{message}</p>
      </div>
      {error && (
        <p className="text-sm mt-1 ml-6 opacity-80">{error}</p>
      )}
    </div>
  ),
);
ErrorCard.displayName = "ErrorCard";
