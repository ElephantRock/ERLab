/**
 * ScoreReport — the score primitive that kills the Flat Score anti-pattern.
 *
 * INTERFACE_CONTRACT.md §6 (cites PRODUCT.md §2 "Trust Must Be Earned Visibly"):
 * A score is never a flat number. It is a summary + an inspectable breakdown.
 *
 * The summary pill survives (scannable in triage) but is always backed by a
 * breakdown reachable on hover — axis bars with weights, confidence rendered
 * (uncertainty visible), closest prior work. A 0.5 "unverifiable" novelty
 * shows *as* uncertain, never dressed as confident.
 *
 * This primitive cannot flatten a score by construction: the pill always has
 * a breakdown behind it. If axes/evidence are absent, the breakdown shows the
 * raw number with a "no breakdown available" note — still not a flat pill,
 * because the honesty is in the "no breakdown" admission.
 */

import * as Tooltip from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";
import { getScoreBg } from "@/lib/score-utils";

export type ScoreKind = "novelty" | "feasibility" | "overall";

export interface ScoreAxis {
  name: string;
  score: number;
  weight: number;
}

export interface PriorWork {
  title: string;
  similarity?: number;
  authors?: string;
  year?: number;
}

export interface ScoreEvidence {
  closestPriorWork?: PriorWork[];
  dimensions?: ScoreAxis[];
}

export interface ScoreReportProps {
  /** Which score type — determines the scale (novelty 0-1, feasibility 0-10). */
  kind: ScoreKind;
  /** The headline number. Still shown as the pill for scannability. */
  summary: number;
  /**
   * Confidence 0-1. When low, the pill renders with reduced opacity / dashed
   * border — uncertainty is visible, not hidden (PRODUCT.md §2).
   */
  confidence?: number;
  /** Named axes with scores and weights (novelty: 4, feasibility: 6, etc). */
  axes?: ScoreAxis[];
  /** Closest prior work + dimension evidence for provenance. */
  evidence?: ScoreEvidence;
  /** Compact variant for triage cards (pill only, no hover breakdown). */
  compact?: boolean;
  className?: string;
}

const KIND_LABELS: Record<ScoreKind, string> = {
  novelty: "Novelty",
  feasibility: "Feasibility",
  overall: "Overall",
};

function formatScore(score: number, kind: ScoreKind): string {
  if (kind === "feasibility") return `${score.toFixed(1)}/10`;
  return score.toFixed(2);
}

function normalize(score: number, kind: ScoreKind): number {
  return kind === "feasibility" ? score / 10 : score;
}

/** The confidence threshold below which the pill renders as "uncertain." */
const LOW_CONFIDENCE_THRESHOLD = 0.5;

export function ScoreReport({
  kind,
  summary,
  confidence,
  axes,
  evidence,
  compact = false,
  className,
}: ScoreReportProps) {
  const normalized = normalize(summary, kind);
  const scoreBg = getScoreBg(normalized, "novelty"); // treats normalized as 0-1
  const isLowConfidence = confidence !== undefined && confidence < LOW_CONFIDENCE_THRESHOLD;
  const hasBreakdown = !compact && (axes?.length || evidence?.closestPriorWork?.length);

  const pill = (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-ui-micro font-semibold",
        scoreBg,
        // Uncertainty visible: low-confidence scores render with dashed border + reduced opacity
        isLowConfidence && "opacity-70 border border-dashed border-warning/50",
        className,
      )}
      aria-label={`${KIND_LABELS[kind]}: ${formatScore(summary, kind)}${
        confidence !== undefined ? `, confidence ${Math.round(confidence * 100)}%` : ""
      }`}
    >
      {formatScore(summary, kind)}
      {isLowConfidence && <span className="ml-1" title="Low confidence">⚠</span>}
    </span>
  );

  // Compact mode: pill only, no breakdown (for triage card density).
  // PRODUCT.md §5: density serves the step. Triage may be dense.
  if (compact || !hasBreakdown) {
    if (compact) return pill;
    // Non-compact but no breakdown data: show pill with an inline "no breakdown" note
    // rather than a flat pill that implies completeness.
    return (
      <span className="inline-flex items-center gap-1.5">
        {pill}
        <span className="text-ui-micro text-muted-foreground italic">no breakdown</span>
      </span>
    );
  }

  // Full mode: pill backed by hover breakdown via Radix Tooltip.
  // PRODUCT.md §2: every score is one click/hover from its evidence.
  return (
    <Tooltip.Provider delayDuration={300}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button type="button" className="inline-flex cursor-help items-center focus:outline-none focus:ring-2 focus:ring-ring rounded-full">
            {pill}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            sideOffset={6}
            className="z-50 max-w-sm rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg animate-fade-in"
          >
            <ScoreBreakdown
              kind={kind}
              summary={summary}
              confidence={confidence}
              axes={axes}
              evidence={evidence}
            />
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

/** The breakdown panel shown on hover. Renders axes as bars, confidence, prior work. */
function ScoreBreakdown({
  kind,
  summary,
  confidence,
  axes,
  evidence,
}: {
  kind: ScoreKind;
  summary: number;
  confidence?: number;
  axes?: ScoreAxis[];
  evidence?: ScoreEvidence;
}) {
  const allAxes = axes ?? evidence?.dimensions ?? [];

  return (
    <div className="space-y-2.5">
      {/* Header: kind + headline + confidence */}
      <div className="flex items-center justify-between gap-3 border-b pb-1.5">
        <span className="text-ui-label font-semibold">{KIND_LABELS[kind]}</span>
        <div className="flex items-center gap-2">
          <span className="text-ui-label font-bold">{formatScore(summary, kind)}</span>
          {confidence !== undefined && (
            <span
              className={cn(
                "text-ui-micro",
                confidence < LOW_CONFIDENCE_THRESHOLD
                  ? "text-warning font-semibold"
                  : "text-muted-foreground",
              )}
            >
              {Math.round(confidence * 100)}% conf
            </span>
          )}
        </div>
      </div>

      {/* Axis bars with weights */}
      {allAxes.length > 0 && (
        <div className="space-y-1.5">
          {allAxes.map((axis) => {
            const axisNormalized = normalize(axis.score, kind);
            return (
              <div key={axis.name} className="space-y-0.5">
                <div className="flex items-center justify-between text-ui-micro">
                  <span className="text-foreground">{axis.name}</span>
                  <span className="text-muted-foreground">
                    {formatScore(axis.score, kind)}
                    {axis.weight > 0 && ` · ${(axis.weight * 100).toFixed(0)}% wt`}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      axisNormalized >= 0.6 ? "bg-success" : axisNormalized >= 0.3 ? "bg-warning" : "bg-destructive",
                    )}
                    style={{ width: `${Math.max(axisNormalized * 100, 3)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Closest prior work — provenance for novelty scores */}
      {evidence?.closestPriorWork && evidence.closestPriorWork.length > 0 && (
        <div className="border-t pt-1.5">
          <div className="text-ui-micro text-muted-foreground mb-1">Closest prior work</div>
          <div className="space-y-0.5">
            {evidence.closestPriorWork.slice(0, 3).map((pw, i) => (
              <div key={i} className="text-ui-micro text-foreground">
                {pw.title}
                {pw.similarity !== undefined && (
                  <span className="text-muted-foreground ml-1">
                    ({Math.round(pw.similarity * 100)}% match)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
