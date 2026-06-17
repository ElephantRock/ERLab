/**
 * EvidencePanel — Shows traceability from idea to source gaps, supporting
 * papers, and structured proposal references with honest resolution status.
 *
 * Part of Phase B: Source Traceability & Evidence UX.
 * Updated: Schema-Backed Provenance — supporting papers via IdeaPaperLink,
 * structured references with match_method and confidence.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  GitBranch,
  FileText,
  AlertCircle,
  ExternalLink,
  BookOpen,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import type {
  SourceGap,
  UnresolvedSourceGap,
  ProposalReference,
  SupportingPaper,
  ResolvedReference,
} from "@/api/types";

interface EvidencePanelProps {
  sourceGaps: (SourceGap | UnresolvedSourceGap)[] | null;
  supportingPapers: SupportingPaper[] | null;
  proposalReferences: ResolvedReference[] | ProposalReference[] | string | null;
  mechanicalMetrics: Record<string, number> | null;
}

function isResolved(gap: SourceGap | UnresolvedSourceGap): gap is SourceGap {
  return gap.resolved === true;
}

function isStructuredRefs(
  refs: ResolvedReference[] | ProposalReference[] | string | null,
): refs is ResolvedReference[] {
  return Array.isArray(refs) && refs.length > 0 && "resolved" in refs[0]!;
}

function SupportPaperCard({ paper }: { paper: SupportingPaper }) {
  return (
    <div
      className="rounded-lg border p-3 space-y-1"
      data-testid={`supporting-paper-${paper.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug">{paper.title}</p>
        <Badge variant="outline" className="text-xs flex-shrink-0">
          {paper.role}
        </Badge>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        {paper.year && <span>{paper.year}</span>}
        {paper.venue && (
          <span className="italic truncate max-w-[200px]">{paper.venue}</span>
        )}
        {paper.citation_count != null && (
          <span>{paper.citation_count.toLocaleString()} citations</span>
        )}
      </div>
      {(paper.doi || paper.arxiv_id || paper.url) && (
        <div className="flex gap-3 text-xs">
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline flex items-center gap-0.5"
            >
              DOI <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
          {paper.arxiv_id && (
            <a
              href={`https://arxiv.org/abs/${paper.arxiv_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline flex items-center gap-0.5"
            >
              arXiv <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function ReferenceItem({
  reference,
  idx,
}: {
  reference: ResolvedReference;
  idx: number;
}) {
  return (
    <div
      className="text-xs pl-3 border-l-2 space-y-0.5"
      data-testid={`reference-item-${idx}`}
    >
      <div className="flex items-start gap-1.5">
        {reference.resolved ? (
          <CheckCircle2 className="h-3 w-3 text-success flex-shrink-0 mt-0.5" />
        ) : (
          <HelpCircle className="h-3 w-3 text-muted-foreground flex-shrink-0 mt-0.5" />
        )}
        <div className="flex-1">
          <span className={reference.resolved ? "" : "text-muted-foreground"}>
            {reference.title || reference.raw}
          </span>
          {reference.resolved && reference.paper && (
            <span className="text-success ml-1">
              → matched to "{reference.paper.title}"
            </span>
          )}
        </div>
      </div>
      {reference.resolved && reference.match_method && (
        <div className="ml-4.5 flex items-center gap-1.5">
          <Badge variant="outline" className="text-xs">
            {reference.match_method}
          </Badge>
          <span className="text-muted-foreground">
            {Math.round(reference.match_confidence * 100)}% confidence
          </span>
        </div>
      )}
      {!reference.resolved && (
        <div className="ml-4.5">
          <Badge variant="outline" className="text-xs text-muted-foreground">
            unresolved
          </Badge>
        </div>
      )}
    </div>
  );
}

export function EvidencePanel({
  sourceGaps,
  supportingPapers,
  proposalReferences,
  mechanicalMetrics,
}: EvidencePanelProps) {
  const navigate = useNavigate();

  const hasContent =
    (sourceGaps && sourceGaps.length > 0) ||
    (supportingPapers && supportingPapers.length > 0) ||
    proposalReferences ||
    mechanicalMetrics;

  if (!hasContent) return null;

  // Partition structured references into resolved and unresolved
  const structuredRefs = isStructuredRefs(proposalReferences)
    ? (proposalReferences as ResolvedReference[])
    : null;
  const resolvedRefs = structuredRefs?.filter((r) => r.resolved) ?? [];
  const unresolvedRefs = structuredRefs?.filter((r) => !r.resolved) ?? [];

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

        {/* Supporting Papers (from IdeaPaperLink junction) */}
        {supportingPapers && supportingPapers.length > 0 && (
          <>
            <Separator />
            <div data-testid="evidence-supporting-papers">
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                Supporting Papers ({supportingPapers.length})
              </h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {supportingPapers.map((paper) => (
                  <SupportPaperCard key={paper.id} paper={paper} />
                ))}
              </div>
            </div>
          </>
        )}

        {/* Proposal References */}
        {proposalReferences && (
          <>
            <Separator />
            <div data-testid="evidence-references">
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <FileText className="h-3 w-3" />
                {structuredRefs
                  ? resolvedRefs.length > 0
                    ? `Resolved Proposal References (${resolvedRefs.length}/${structuredRefs.length})`
                    : `Unresolved References (${unresolvedRefs.length})`
                  : "Proposal References"}
              </h4>
              {typeof proposalReferences === "string" ? (
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {proposalReferences}
                </pre>
              ) : structuredRefs ? (
                <div className="space-y-2">
                  {structuredRefs.map((reference, idx) => (
                    <ReferenceItem key={idx} reference={reference} idx={idx} />
                  ))}
                </div>
              ) : (
                <ul className="space-y-1">
                  {(proposalReferences as ProposalReference[]).map((ref, idx) => (
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
