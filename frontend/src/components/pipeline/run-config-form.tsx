import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StageModelSelector } from "./stage-model-selector";
import { useSession } from "@/hooks/useSession";
import type { PipelineRunRequest } from "@/api/types";
import { Loader2, ChevronDown, ChevronRight, Zap, Microscope, GraduationCap, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

const VALIDATION = {
  domain: { maxLength: 200, default: "AI/NLP" },
  max_gaps: { min: 1, max: 20, default: 5 },
  generation_rounds: { min: 1, max: 10, default: 2 },
  ideas_per_round: { min: 1, max: 20, default: 5 },
  export_formats: ["markdown", "latex"] as const,
} as const;

export { VALIDATION };

// ── Strategy definitions ──
const STRATEGIES = [
  {
    value: "fast_scan",
    icon: Zap,
    title: "Quick Scan",
    time: "~2-5 min",
    desc: "Fast scan skips tree search and metrics for rapid results.",
    accent: "text-accent",
  },
  {
    value: "deep_research",
    icon: Microscope,
    title: "Deep Research",
    time: "~25 min",
    desc: "Full pipeline with tree search, novelty checking, and proposal synthesis.",
    accent: "text-info",
  },
  {
    value: "academic_proposal",
    icon: GraduationCap,
    title: "Academic Proposal",
    time: "~45 min",
    desc: "Stricter thresholds and longer timeouts for academic-grade proposals.",
    accent: "text-warning",
  },
  {
    value: "literature_review",
    icon: BookOpen,
    title: "Literature Review",
    time: "~10 min",
    desc: "Literature search and gap analysis only, no proposal generation.",
    accent: "text-muted-foreground",
  },
] as const;

interface RunConfigFormProps {
  onSubmit: (config: PipelineRunRequest) => void;
  isLoading?: boolean;
  initialDomain?: string;
  onStrategyChange?: (strategy: string) => void;
}

export function RunConfigForm({ onSubmit, isLoading, initialDomain = "", onStrategyChange }: RunConfigFormProps) {
  const { sessionId, setSessionId } = useSession();
  const [domain, setDomain] = useState(initialDomain);
  const [maxGaps, setMaxGaps] = useState(VALIDATION.max_gaps.default);
  const [ideasPerRound, setIdeasPerRound] = useState(VALIDATION.ideas_per_round.default);
  const [generationRounds, setGenerationRounds] = useState(VALIDATION.generation_rounds.default);
  const [exportFormat, setExportFormat] = useState<string>(VALIDATION.export_formats[0]);
  const [searchQueries, setSearchQueries] = useState("");
  const [proposalDepth, setProposalDepth] = useState<string>("standard");
  const [noveltyDepth, setNoveltyDepth] = useState<string>("standard");
  const [ideaDiversity, setIdeaDiversity] = useState<string>("balanced");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [strategy, setStrategy] = useState<string>("fast_scan");
  const [modelOverrides, setModelOverrides] = useState<Record<string, string>>({});

  function selectStrategy(value: string) {
    setStrategy(value);
    onStrategyChange?.(value);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim()) {
      const confirmed = window.confirm(
        "No research domain specified. The pipeline will use 'AI/NLP' as default. Continue?"
      );
      if (!confirmed) return;
    }
    const config: PipelineRunRequest = {
      domain: domain || undefined,
      max_gaps: maxGaps,
      generation_rounds: generationRounds,
      ideas_per_round: ideasPerRound,
      search_queries: searchQueries
        ? searchQueries.split(",").map((q) => q.trim()).filter(Boolean)
        : undefined,
      run_novelty: true,
      run_feasibility: true,
      run_synthesis: true,
      export_format: exportFormat,
      strategy,
      model_overrides: Object.keys(modelOverrides).length > 0 ? modelOverrides : undefined,
      proposal_depth: proposalDepth,
      novelty_depth: noveltyDepth,
      idea_diversity: ideaDiversity,
    };
    onSubmit(config);
  }

  return (
    <Card className="card-shadow" data-testid="run-config-form">
      <CardHeader>
        <CardTitle className="text-base">Research Configuration</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">

          {/* ── Domain Hero ── */}
          <div className="space-y-2">
            <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Research Domain
            </label>
            <Input
              placeholder="machine learning, nlp, computer vision..."
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              maxLength={VALIDATION.domain.maxLength}
              data-testid="domain-input"
              className="text-base h-12"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              The domain guides literature search, gap analysis, and idea generation.
            </p>
          </div>

          {/* ── Strategy Cards ── */}
          <div className="space-y-2">
            <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Research Strategy
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              {STRATEGIES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => selectStrategy(s.value)}
                  data-testid={`strategy-card-${s.value}`}
                  className={cn(
                    "text-left rounded-lg border p-3 transition-all",
                    strategy === s.value
                      ? "border-accent bg-accent/5 ring-1 ring-accent/20"
                      : "border-border hover:border-accent/30 hover:bg-muted/30",
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <s.icon className={cn("h-4 w-4", strategy === s.value ? s.accent : "text-muted-foreground")} />
                    <span className="text-sm font-medium">{s.title}</span>
                    <span className="ml-auto text-[10px] font-mono text-muted-foreground">{s.time}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-tight">{s.desc}</p>
                </button>
              ))}
            </div>
            {/* Hidden select for backward compat */}
            <select
              value={strategy}
              onChange={(e) => selectStrategy(e.target.value)}
              data-testid="strategy-select"
              className="hidden"
              aria-hidden
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.title}</option>
              ))}
            </select>
          </div>

          {/* ── Research Intent ── */}
          <div className="space-y-3 pt-2">
            <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
              Research Intent
            </label>

            {/* Proposal Depth */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Proposal Depth</label>
              <div className="flex gap-2">
                {(["concise", "standard", "detailed"] as const).map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setProposalDepth(level)}
                    className={cn(
                      "flex-1 px-3 py-1.5 text-xs rounded-md border transition-colors capitalize",
                      proposalDepth === level
                        ? "border-accent bg-accent/10 text-accent font-medium"
                        : "border-input text-muted-foreground hover:bg-muted/50",
                    )}
                    data-testid={`proposal-depth-${level}`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {/* Novelty Depth */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Novelty Check</label>
              <div className="flex gap-2">
                {(["light", "standard", "thorough"] as const).map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setNoveltyDepth(level)}
                    className={cn(
                      "flex-1 px-3 py-1.5 text-xs rounded-md border transition-colors capitalize",
                      noveltyDepth === level
                        ? "border-accent bg-accent/10 text-accent font-medium"
                        : "border-input text-muted-foreground hover:bg-muted/50",
                    )}
                    data-testid={`novelty-depth-${level}`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {/* Idea Diversity */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Idea Diversity</label>
              <div className="flex gap-2">
                {(["focused", "balanced", "exploratory"] as const).map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setIdeaDiversity(level)}
                    className={cn(
                      "flex-1 px-3 py-1.5 text-xs rounded-md border transition-colors capitalize",
                      ideaDiversity === level
                        ? "border-accent bg-accent/10 text-accent font-medium"
                        : "border-input text-muted-foreground hover:bg-muted/50",
                    )}
                    data-testid={`idea-diversity-${level}`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Advanced Options ── */}
          <div className="border rounded-md">
            <button
              type="button"
              onClick={() => setAdvancedOpen(!advancedOpen)}
              className="flex items-center gap-2 w-full px-4 py-2.5 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
              data-testid="advanced-toggle"
              aria-expanded={advancedOpen}
            >
              {advancedOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              Advanced Options
            </button>
            {advancedOpen && (
              <div className="px-4 pb-4 space-y-3" data-testid="advanced-content">
                {/* Core numeric fields */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="max-gaps-input">Max Gaps</label>
                    <Input
                      id="max-gaps-input"
                      type="number"
                      min={VALIDATION.max_gaps.min}
                      max={VALIDATION.max_gaps.max}
                      value={maxGaps}
                      onChange={(e) => setMaxGaps(Number(e.target.value))}
                      data-testid="max-gaps-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="ideas-per-round-input">Ideas Per Round</label>
                    <Input
                      id="ideas-per-round-input"
                      type="number"
                      min={VALIDATION.ideas_per_round.min}
                      max={VALIDATION.ideas_per_round.max}
                      value={ideasPerRound}
                      onChange={(e) => setIdeasPerRound(Number(e.target.value))}
                      data-testid="ideas-per-round-input"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium" htmlFor="generation-rounds-input">Generation Rounds</label>
                    <Input
                      id="generation-rounds-input"
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
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
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
                    data-testid="search-queries-input"
                  />
                </div>

                {/* Session ID */}
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="session-id-input">
                    Session ID (optional)
                  </label>
                  <input
                    id="session-id-input"
                    type="text"
                    placeholder="my-session-name"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    data-testid="session-id-input"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    maxLength={200}
                  />
                </div>

                {/* Model Selection */}
                <div className="space-y-2 pt-2 border-t">
                  <label className="text-sm font-medium">Model Selection</label>
                  <StageModelSelector value={modelOverrides} onChange={setModelOverrides} />
                </div>
              </div>
            )}
          </div>

          {/* ── Start Button ── */}
          <Button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 text-base"
            data-testid="start-pipeline-btn"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting Pipeline...
              </>
            ) : (
              <>
                Start Pipeline
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
