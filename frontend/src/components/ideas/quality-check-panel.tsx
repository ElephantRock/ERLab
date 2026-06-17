/**
 * QualityCheckPanel — Shows deterministic quality checks for proposal sections.
 *
 * Displays which sections pass/fail word-count and pattern checks, computed
 * at read time from persisted sections_json. This is the same checklist that
 * ProposalSynthesizer._refine_sections enforces at generation time.
 *
 * When remediation hints are available, failed checks show actionable
 * suggestions inline.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ClipboardCheck,
  Lightbulb,
} from "lucide-react";
import type { QualityCheckResult, RemediationHint } from "@/api/types";
import { cn } from "@/lib/utils";

export function QualityCheckPanel({
  qualityChecks,
  remediationHints,
}: {
  qualityChecks: QualityCheckResult[] | null;
  remediationHints?: RemediationHint[] | null;
}) {
  if (!qualityChecks || qualityChecks.length === 0) return null;

  const passedCount = qualityChecks.filter((c) => c.passed).length;
  const totalCount = qualityChecks.length;
  const allPassed = passedCount === totalCount;
  const missingCount = qualityChecks.filter((c) => !c.present).length;

  // Build a lookup: section → hints for that section
  const hintsBySection = new Map<string, RemediationHint[]>();
  if (remediationHints) {
    for (const hint of remediationHints) {
      const existing = hintsBySection.get(hint.section) ?? [];
      existing.push(hint);
      hintsBySection.set(hint.section, existing);
    }
  }

  return (
    <Card data-testid="quality-check-panel">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4" />
            Proposal Quality Checks
          </CardTitle>
          <Badge
            variant="outline"
            className={cn(
              "text-xs",
              allPassed
                ? "text-success border-success/30"
                : "text-warning border-warning/30",
            )}
            data-testid="quality-check-summary"
          >
            {passedCount}/{totalCount} sections passed
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {missingCount === totalCount && (
          <EmptyState
            icon={AlertTriangle}
            title="No sections found"
            message="This proposal has no detectable prose sections to check."
          />
        )}
        {qualityChecks.map((check) => (
          <div
            key={check.section}
            className={cn(
              "flex items-start gap-3 rounded-lg border p-2.5",
              check.passed
                ? "border-success/20 bg-success/5"
                : check.present
                  ? "border-warning/20 bg-warning/5"
                  : "border-muted bg-muted/30",
            )}
            data-testid={`quality-check-${check.section}`}
          >
            {/* Status icon */}
            <div className="flex-shrink-0 mt-0.5">
              {check.passed ? (
                <CheckCircle2 className="h-4 w-4 text-success" />
              ) : check.present ? (
                <XCircle className="h-4 w-4 text-warning" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              )}
            </div>

            {/* Section details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{check.label}</span>
                {check.present && (
                  <span
                    className={cn(
                      "text-xs font-mono",
                      check.meets_word_count
                        ? "text-muted-foreground"
                        : "text-warning",
                    )}
                  >
                    {check.word_count}/{check.min_words} words
                  </span>
                )}
              </div>

              {/* Pattern check chips */}
              {check.present && check.checks.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {check.checks.map((entry, idx) => (
                    <span
                      key={idx}
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs",
                        entry.passed
                          ? "text-success"
                          : "text-warning bg-warning/10",
                      )}
                    >
                      {entry.passed ? (
                        <CheckCircle2 className="h-2.5 w-2.5" />
                      ) : (
                        <XCircle className="h-2.5 w-2.5" />
                      )}
                      {entry.name}
                    </span>
                  ))}
                </div>
              )}

              {/* Failures list */}
              {check.present && check.failures.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  {check.failures.join("; ")}
                </p>
              )}

              {/* Remediation hints for this section */}
              {!check.passed && hintsBySection.has(check.section) && (
                <div
                  className="mt-2 space-y-1.5"
                  data-testid={`remediation-inline-${check.section}`}
                >
                  {hintsBySection.get(check.section)!.map((hint, hIdx) => (
                    <div
                      key={hIdx}
                      className="flex items-start gap-1.5 rounded bg-warning/5 border border-warning/10 px-2 py-1.5"
                    >
                      <Lightbulb className="h-3 w-3 text-info flex-shrink-0 mt-0.5" />
                      <span className="text-xs text-muted-foreground">
                        {hint.suggestion}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {!check.present && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  Section not present in proposal
                </p>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
