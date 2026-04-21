import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { cn } from "@/lib/utils";

interface NoveltyReportViewProps {
  report: Record<string, unknown>;
}

const dimensions = [
  { key: "method_novelty", label: "Method Novelty" },
  { key: "problem_novelty", label: "Problem Novelty" },
  { key: "domain_transfer", label: "Domain Transfer" },
  { key: "combination_novelty", label: "Combination Novelty" },
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
      <span className="text-xs text-muted-foreground w-10 text-right">{value.toFixed(2)}</span>
    </div>
  );
}

export function NoveltyReportView({ report }: NoveltyReportViewProps) {
  const args = typeof report.novelty_arguments === "string" ? report.novelty_arguments : null;

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
              <ScoreBar value={val} max={1} />
            </div>
          );
        })}
      </div>

      {args && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2">Analysis</h4>
          <MarkdownRenderer content={args} />
        </div>
      )}
    </div>
  );
}
