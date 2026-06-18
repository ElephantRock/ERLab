/**
 * RemediationBanner — Summary of quality issues with actionable insights.
 *
 * Shows above the proposal sections when quality checks fail or citation
 * issues are detected. Provides a concise summary of what needs attention,
 * grouped by issue type. Pure read-only — no mutations.
 */

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  FileWarning,
  MessageSquareWarning,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useState } from "react";
import type { RemediationHint, CitationAuditEntry } from "@/api/types";
import { cn } from "@/lib/utils";

export function RemediationBanner({
  remediationHints,
  citationAudit,
  onJumpToSection,
}: {
  remediationHints: RemediationHint[] | null;
  citationAudit: CitationAuditEntry[] | null;
  onJumpToSection?: (sectionKey: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!remediationHints || remediationHints.length === 0) return null;

  // Get citation issues from audit
  const citationSummary = citationAudit?.find(
    (e) => e.section === "_summary",
  );
  const citationIssues = citationAudit?.filter(
    (e) => e.section !== "_summary" && e.has_citation_issues,
  );

  // Don't show if everything is actually fine
  if (
    remediationHints.length === 0 &&
    (!citationSummary || citationSummary.citation_needed_count === 0)
  ) {
    return null;
  }

  // Group hints by issue type
  const wordCountIssues = remediationHints.filter(
    (h) => h.issue_type === "word_count",
  );
  const patternIssues = remediationHints.filter(
    (h) => h.issue_type === "missing_pattern",
  );
  const missingSections = remediationHints.filter(
    (h) => h.issue_type === "missing_section",
  );

  const errorCount = remediationHints.filter(
    (h) => h.severity === "error",
  ).length;
  const warningCount = remediationHints.filter(
    (h) => h.severity === "warning",
  ).length;

  return (
    <Card
      data-testid="remediation-banner"
      className="border-warning/30 bg-warning/5"
    >
      <CardContent className="pt-4">
        {/* Header row — always visible */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between text-left"
          data-testid="remediation-toggle"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <span className="text-sm font-medium">
              Quality issues detected
            </span>
            <div className="flex items-center gap-1.5 ml-2">
              {errorCount > 0 && (
                <Badge
                  variant="outline"
                  className="text-xs text-destructive border-destructive/30"
                >
                  {errorCount} missing section{errorCount !== 1 ? "s" : ""}
                </Badge>
              )}
              {wordCountIssues.length > 0 && (
                <Badge
                  variant="outline"
                  className="text-xs text-warning border-warning/30"
                >
                  {wordCountIssues.length} word count
                </Badge>
              )}
              {patternIssues.length > 0 && (
                <Badge
                  variant="outline"
                  className="text-xs text-warning border-warning/30"
                >
                  {patternIssues.length} missing pattern
                </Badge>
              )}
              {citationSummary && citationSummary.citation_needed_count > 0 && (
                <Badge
                  variant="outline"
                  className="text-xs text-destructive border-destructive/30"
                >
                  {citationSummary.citation_needed_count} citation needed
                </Badge>
              )}
            </div>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {/* Expanded details */}
        {expanded && (
          <div className="mt-4 space-y-4">
            {/* Citation issues */}
            {citationIssues && citationIssues.length > 0 && (
              <div
                className="space-y-2"
                data-testid="remediation-citation-issues"
              >
                <h4 className="text-xs font-semibold text-destructive uppercase tracking-wide flex items-center gap-1">
                  <MessageSquareWarning className="h-3 w-3" />
                  Citation Issues
                </h4>
                {citationIssues.map((entry) => (
                  <div
                    key={entry.section}
                    className={cn(
                      "flex items-center justify-between rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2",
                      onJumpToSection && "cursor-pointer hover:bg-destructive/10 transition-colors",
                    )}
                    onClick={() => onJumpToSection?.(entry.section)}
                    data-testid={`jump-citation-${entry.section}`}
                  >
                    <span className="text-sm font-medium">{entry.label}</span>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-destructive font-mono">
                        {entry.citation_needed_count} [Citation needed]
                      </span>
                      <span className="text-muted-foreground font-mono">
                        {entry.valid_citation_count} valid
                      </span>
                      {entry.resolved_reference_count !== undefined && (
                        <span className="text-success font-mono">
                          {entry.resolved_reference_count}/
                          {entry.resolved_reference_count +
                            (entry.unresolved_reference_count ?? 0)}{" "}
                          refs resolved
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Remediation hints */}
            <div
              className="space-y-2"
              data-testid="remediation-hints-list"
            >
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <FileWarning className="h-3 w-3" />
                Suggested Fixes
              </h4>
              {missingSections.map((hint, idx) => (
                <HintRow key={`missing-${idx}`} hint={hint} onJumpToSection={onJumpToSection} />
              ))}
              {wordCountIssues.map((hint, idx) => (
                <HintRow key={`wc-${idx}`} hint={hint} onJumpToSection={onJumpToSection} />
              ))}
              {patternIssues.map((hint, idx) => (
                <HintRow key={`pat-${idx}`} hint={hint} onJumpToSection={onJumpToSection} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HintRow({
  hint,
  onJumpToSection,
}: {
  hint: RemediationHint;
  onJumpToSection?: (sectionKey: string) => void;
}) {
  const isError = hint.severity === "error";
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border px-3 py-2",
        isError
          ? "border-destructive/20 bg-destructive/5"
          : "border-warning/20 bg-warning/5",
        onJumpToSection && "cursor-pointer hover:bg-warning/10 transition-colors",
      )}
      onClick={() => onJumpToSection?.(hint.section)}
      data-testid={`remediation-hint-${hint.section}`}
    >
      <div className="flex-shrink-0 mt-0.5">
        {isError ? (
          <AlertTriangle className="h-4 w-4 text-destructive" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-warning" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">{hint.label}</span>
          <div className="flex items-center gap-2">
            {onJumpToSection && hint.refinement_available && (
              <Badge variant="outline" className="text-xs text-success border-success/30">
                Fixable
              </Badge>
            )}
            <span className="text-xs text-muted-foreground capitalize">
              {hint.issue_type.replace(/_/g, " ")}
            </span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          {hint.suggestion}
        </p>
      </div>
    </div>
  );
}
