/**
 * EvidencePanel — Shows traceability from idea to source gaps, proposal
 * references, and mechanical metrics provenance.
 *
 * Part of Phase B: Source Traceability & Evidence UX.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { GitBranch, FileText, AlertCircle, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type {
  SourceGap,
  UnresolvedSourceGap,
  ProposalReference,
} from "@/api/types";

interface EvidencePanelProps {
  sourceGaps: (SourceGap | UnresolvedSourceGap)[] | null;
  proposalReferences: ProposalReference[] | string | null;
  mechanicalMetrics: Record<string, number> | null;
}

function isResolved(gap: SourceGap | UnresolvedSourceGap): gap is SourceGap {
  return gap.resolved === true;
}

export function EvidencePanel({
  sourceGaps,
  proposalReferences,
  mechanicalMetrics,
}: EvidencePanelProps) {
  const navigate = useNavigate();

  const hasContent =
    (sourceGaps && sourceGaps.length > 0) ||
    proposalReferences ||
    mechanicalMetrics;

  if (!hasContent) return null;

  return (
    <Card data-testid="evidence-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch className="h-4 w-4" />
          Evidence &amp; Provenance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Source Gaps */}
        {sourceGaps && sourceGaps.length > 0 && (
          <div data-testid="evidence-source-gaps">
            <h4 className="text-sm font-medium text-muted-foreground mb-2">
              Source Research Gaps
            </h4>
            <ul className="space-y-2">
              {sourceGaps.map((gap, idx) => (
                <li
                  key={idx}
                  className="flex items-center gap-2 text-sm"
                  data-testid={`source-gap-item-${idx}`}
                >
                  {isResolved(gap) ? (
                    <>
                      <span className="inline-block h-2 w-2 rounded-full bg-warning flex-shrink-0" />
                      <Button
                        variant="link"
                        className="p-0 h-auto text-sm"
                        onClick={() => navigate(`/gaps/${gap.id}`)}
                        data-testid={`source-gap-link-${idx}`}
                      >
                        {gap.title}
                      </Button>
                      <Badge variant="outline" className="text-xs">
                        {gap.gap_type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {Math.round(gap.confidence * 100)}% conf.
                      </span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                      <span className="text-muted-foreground" data-testid={`unresolved-gap-${idx}`}>
                        {gap.raw}
                      </span>
                      <Badge variant="outline" className="text-xs text-muted-foreground">
                        unresolved
                      </Badge>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Proposal References */}
        {proposalReferences && (
          <>
            <Separator />
            <div data-testid="evidence-references">
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <FileText className="h-3 w-3" />
                Proposal References
              </h4>
              {typeof proposalReferences === "string" ? (
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {proposalReferences}
                </pre>
              ) : (
                <ul className="space-y-1">
                  {proposalReferences.map((ref, idx) => (
                    <li
                      key={idx}
                      className="text-xs text-muted-foreground pl-3 border-l-2 border-muted"
                      data-testid={`reference-item-${idx}`}
                    >
                      {ref.raw}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}

        {/* Mechanical Metrics Provenance */}
        {mechanicalMetrics && Object.keys(mechanicalMetrics).length > 0 && (
          <>
            <Separator />
            <div data-testid="evidence-metrics-provenance">
              <h4 className="text-sm font-medium text-muted-foreground mb-2">
                Mechanical Metrics (zero-LLM, deterministic)
              </h4>
              <div className="grid gap-2 sm:grid-cols-3">
                {Object.entries(mechanicalMetrics).map(([key, value]) => (
                  <div key={key} className="text-xs">
                    <span className="text-muted-foreground">
                      {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <span className="ml-1 font-medium">
                      {typeof value === "number" ? value.toFixed(3) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
