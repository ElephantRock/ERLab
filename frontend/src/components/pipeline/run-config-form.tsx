import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PipelineRunRequest } from "@/api/types";
import { Search, Loader2, ChevronDown, ChevronRight } from "lucide-react";

/**
 * Validation constants matching backend api/schemas.py PipelineRunRequest exactly.
 * HB-01: Client-side validation MUST match API validation exactly.
 */
const VALIDATION = {
  domain: { maxLength: 200, default: "AI/NLP" },
  max_gaps: { min: 1, max: 20, default: 5 },
  generation_rounds: { min: 1, max: 10, default: 2 },
  ideas_per_round: { min: 1, max: 20, default: 5 },
  export_formats: ["markdown", "latex"] as const,
} as const;

export { VALIDATION };

interface RunConfigFormProps {
  onSubmit: (config: PipelineRunRequest) => void;
  isLoading?: boolean;
}

export function RunConfigForm({ onSubmit, isLoading }: RunConfigFormProps) {
  const [domain, setDomain] = useState("");
  const [maxGaps, setMaxGaps] = useState(VALIDATION.max_gaps.default);
  const [ideasPerRound, setIdeasPerRound] = useState(VALIDATION.ideas_per_round.default);
  const [generationRounds, setGenerationRounds] = useState(VALIDATION.generation_rounds.default);
  const [exportFormat, setExportFormat] = useState<string>(VALIDATION.export_formats[0]);
  const [runNovelty, setRunNovelty] = useState(true);
  const [runFeasibility, setRunFeasibility] = useState(true);
  const [runSynthesis, setRunSynthesis] = useState(true);
  const [searchQueries, setSearchQueries] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const config: PipelineRunRequest = {
      domain: domain || undefined,
      max_gaps: maxGaps,
      generation_rounds: generationRounds,
      ideas_per_round: ideasPerRound,
      search_queries: searchQueries
        ? searchQueries.split(",").map((q) => q.trim()).filter(Boolean)
        : undefined,
      run_novelty: runNovelty,
      run_feasibility: runFeasibility,
      run_synthesis: runSynthesis,
      export_format: exportFormat,
    };
    onSubmit(config);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Pipeline Configuration</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Domain */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Research Domain</label>
            <Input
              placeholder="e.g., machine learning, nlp, computer vision"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              maxLength={VALIDATION.domain.maxLength}
            />
          </div>

          {/* Core numeric fields */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Gaps</label>
              <Input
                type="number"
                min={VALIDATION.max_gaps.min}
                max={VALIDATION.max_gaps.max}
                value={maxGaps}
                onChange={(e) => setMaxGaps(Number(e.target.value))}
                data-testid="max-gaps-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Ideas Per Round</label>
              <Input
                type="number"
                min={VALIDATION.ideas_per_round.min}
                max={VALIDATION.ideas_per_round.max}
                value={ideasPerRound}
                onChange={(e) => setIdeasPerRound(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Generation Rounds</label>
              <Input
                type="number"
                min={VALIDATION.generation_rounds.min}
                max={VALIDATION.generation_rounds.max}
                value={generationRounds}
                onChange={(e) => setGenerationRounds(Number(e.target.value))}
                data-testid="generation-rounds-input"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Export Format</label>
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value)}
                data-testid="export-format-select"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {VALIDATION.export_formats.map((fmt) => (
                  <option key={fmt} value={fmt}>
                    {fmt.charAt(0).toUpperCase() + fmt.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Search Queries */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Search Queries (comma-separated)</label>
            <Input
              placeholder="transformer attention, few-shot learning"
              value={searchQueries}
              onChange={(e) => setSearchQueries(e.target.value)}
            />
          </div>

          {/* Advanced Options - Collapsible */}
          <div className="border rounded-md">
            <button
              type="button"
              onClick={() => setAdvancedOpen(!advancedOpen)}
              className="flex items-center gap-2 w-full px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
              data-testid="advanced-toggle"
              aria-expanded={advancedOpen}
            >
              {advancedOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              Advanced Options
            </button>
            {advancedOpen && (
              <div className="px-4 pb-4 space-y-3" data-testid="advanced-content">
                {/* Run Toggles */}
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium" htmlFor="run-novelty-toggle">
                    Run Novelty Check
                  </label>
                  <input
                    id="run-novelty-toggle"
                    type="checkbox"
                    checked={runNovelty}
                    onChange={(e) => setRunNovelty(e.target.checked)}
                    data-testid="run-novelty-toggle"
                    className="h-4 w-4 rounded border-input"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium" htmlFor="run-feasibility-toggle">
                    Run Feasibility Scoring
                  </label>
                  <input
                    id="run-feasibility-toggle"
                    type="checkbox"
                    checked={runFeasibility}
                    onChange={(e) => setRunFeasibility(e.target.checked)}
                    data-testid="run-feasibility-toggle"
                    className="h-4 w-4 rounded border-input"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium" htmlFor="run-synthesis-toggle">
                    Run Proposal Synthesis
                  </label>
                  <input
                    id="run-synthesis-toggle"
                    type="checkbox"
                    checked={runSynthesis}
                    onChange={(e) => setRunSynthesis(e.target.checked)}
                    data-testid="run-synthesis-toggle"
                    className="h-4 w-4 rounded border-input"
                  />
                </div>
              </div>
            )}
          </div>

          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Search className="mr-2 h-4 w-4" />
            )}
            {isLoading ? "Starting..." : "Start Pipeline"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
