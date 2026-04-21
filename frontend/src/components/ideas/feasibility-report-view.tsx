import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface FeasibilityReportViewProps {
  report: Record<string, unknown>;
}

const dimensions = [
  { key: "data_availability", label: "Data Availability" },
  { key: "computational_requirements", label: "Compute Feasibility" },
  { key: "methodological_complexity", label: "Method Complexity" },
  { key: "evaluation_plan", label: "Evaluation Plan" },
  { key: "novelty_grounding", label: "Novelty Grounding" },
  { key: "impact_potential", label: "Impact Potential" },
];

function ScoreBar({ value, max }: { value: number; max: number }) {
  const pct = (value / max) * 100;
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full",
            pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-10 text-right">{value}/10</span>
    </div>
  );
}

export function FeasibilityReportView({ report }: FeasibilityReportViewProps) {
  const reasoning = typeof report.reasoning === "string" ? report.reasoning : null;
  const timeline = typeof report.estimated_timeline === "string" ? report.estimated_timeline : null;
  const risks = Array.isArray(report.key_risks) ? report.key_risks : [];

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {dimensions.map(({ key, label }) => {
          const val = report[key];
          if (typeof val !== "number") return null;
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{label}</span>
              </div>
              <ScoreBar value={val} max={10} />
            </div>
          );
        })}
      </div>

      {timeline && (
        <div>
          <span className="text-sm font-medium">Estimated Timeline: </span>
          <Badge variant="outline">{timeline}</Badge>
        </div>
      )}

      {risks.length > 0 && (
        <div>
          <span className="text-sm font-medium">Key Risks</span>
          <ul className="mt-1 space-y-1">
            {risks.map((risk, i) => (
              <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                <span className="text-red-400 mt-0.5">•</span>
                {String(risk)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {reasoning && (
        <div>
          <h4 className="text-sm font-medium mb-2">Reasoning</h4>
          <MarkdownRenderer content={reasoning} />
        </div>
      )}
    </div>
  );
}
