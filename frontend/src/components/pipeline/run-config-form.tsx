import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StageModelSelector } from "./stage-model-selector";
import { useSession } from "@/hooks/useSession";
import type { ExperimentSpecCatalog, PipelineRunRequest } from "@/api/types";
import { Loader2, ChevronDown, ChevronRight, Zap, Microscope, GraduationCap, BookOpen, Compass, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";

const VALIDATION = {
  domain: { maxLength: 200, default: "AI/NLP" },
  research_question: { maxLength: 2000 },
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
    desc: "Rapid gaps → lightweight ideas → concise proposals. Skips tree search, novelty, metrics, review, and paper synthesis.",
    accent: "text-accent",
  },
  {
    value: "deep_research",
    icon: Microscope,
    title: "Deep Research",
    desc: "Full proposal-to-paper workflow with reflection, novelty checking, evaluation, and citation audit.",
    accent: "text-info",
  },
  {
    value: "academic_proposal",
    icon: GraduationCap,
    title: "Academic Proposal",
    desc: "Academic proposal-to-paper workflow. Uses the same production stage graph as Deep Research.",
    accent: "text-warning",
  },
  {
    value: "literature_review",
    icon: BookOpen,
    title: "Literature Review",
    desc: "Literature search and gap analysis only; no idea, proposal, or paper generation.",
    accent: "text-muted-foreground",
  },
] as const;

interface RunConfigFormProps {
  onSubmit: (config: PipelineRunRequest) => void;
  isLoading?: boolean;
  initialDomain?: string;
  onStrategyChange?: (strategy: string) => void;
  experimentCatalog?: ExperimentSpecCatalog | null;
  experimentCatalogLoading?: boolean;
  experimentCatalogError?: boolean;
  onExperimentSpecChange?: (specId: string | null) => void;
}

export function RunConfigForm({
  onSubmit,
  isLoading,
  initialDomain = "",
  onStrategyChange,
  experimentCatalog = null,
  experimentCatalogLoading = false,
  experimentCatalogError = false,
  onExperimentSpecChange,
}: RunConfigFormProps) {
  const { sessionId, setSessionId } = useSession();
  const [researchQuestion, setResearchQuestion] = useState("");
  const [domain, setDomain] = useState(initialDomain);
  const [maxGaps, setMaxGaps] = useState<number>(VALIDATION.max_gaps.default);
  const [ideasPerRound, setIdeasPerRound] = useState<number>(VALIDATION.ideas_per_round.default);
  const [generationRounds, setGenerationRounds] = useState<number>(VALIDATION.generation_rounds.default);
  const [exportFormat, setExportFormat] = useState<string>(VALIDATION.export_formats[0]);
  const [searchQueries, setSearchQueries] = useState("");
  // Literal-union types from PipelineRunConfig (api/types.ts) — typing the
  // useState generics with these gives both compile-time safety on the
  // setters and assignability to the config fields without a cast.
  const [proposalDepth, setProposalDepth] = useState<"concise" | "standard" | "detailed">("standard");
  const [noveltyDepth, setNoveltyDepth] = useState<"light" | "standard" | "thorough">("standard");
  const [ideaDiversity, setIdeaDiversity] = useState<"focused" | "balanced" | "exploratory">("balanced");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [strategy, setStrategy] = useState<string>("fast_scan");
  const [modelOverrides, setModelOverrides] = useState<Record<string, string>>({});
  const [experimentSpecId, setExperimentSpecId] = useState<string | null>(null);

  const compatibleStrategies = experimentCatalog?.compatible_strategies ?? [];
  const registeredSpecs = experimentCatalog?.specs ?? [];
  const empiricalCompatible = compatibleStrategies.includes(strategy);
  const selectedExperiment = registeredSpecs.find((spec) => spec.spec_id === experimentSpecId) ?? null;
  const activeExperimentSpecId = empiricalCompatible && selectedExperiment ? selectedExperiment.spec_id : null;

  function updateExperimentSpec(specId: string | null) {
    setExperimentSpecId(specId);
    onExperimentSpecChange?.(specId);
  }

  function selectStrategy(value: string) {
    setStrategy(value);
    onStrategyChange?.(value);
    if (experimentSpecId && !compatibleStrategies.includes(value)) {
      updateExperimentSpec(null);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Phase 1 1B: require at least one of research question or domain. Both
    // empty is rejected; entered values are preserved (state is not cleared).
    const rqTrimmed = researchQuestion.trim();
    const domainTrimmed = domain.trim();
    if (!rqTrimmed && !domainTrimmed) {
      window.confirm(
        "Enter a research question (or a research domain) before starting a run."
      );
      return;
    }
    const config: PipelineRunRequest = {
      domain: domainTrimmed || undefined,
      research_question: rqTrimmed || undefined,
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
      experiment_spec_id: activeExperimentSpecId || undefined,
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

          {/* ── Research Question (Phase 1 1B: primary input) ── */}
          <div className="space-y-2">
            <label className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
              Research Question
            </label>
            <textarea
              placeholder="e.g. How can graph-based reasoning and neuro-symbolic methods be combined to improve the verifiability of language-model reasoning?"
              value={researchQuestion}
              onChange={(e) => setResearchQuestion(e.target.value)}
              maxLength={VALIDATION.research_question.maxLength}
              data-testid="research-question-input"
              className="flex min-h-[96px] w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              The primary research intent. When provided, literature search and proposal synthesis anchor on it.
            </p>
          </div>

          {/* ── Domain (optional context) ── */}
          <div className="space-y-2">
            <label className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
              Research Domain <span className="text-muted-foreground/70 normal-case">(optional)</span>
            </label>
            <Input
              placeholder="machine learning, nlp, computer vision..."
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              maxLength={VALIDATION.domain.maxLength}
              data-testid="domain-input"
              className="text-base h-12"
            />
            <p className="text-xs text-muted-foreground">
              Domain context for gap analysis and idea generation. A research question above is sufficient on its own.
            </p>
          </div>

          {/* ── Strategy Cards ── */}
          <div className="space-y-2">
            <label className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
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

          {/* ── Experiment Authority ── */}
          <div className="space-y-2">
            <label className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
              Experiment Authority
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => updateExperimentSpec(null)}
                data-testid="experiment-mode-exploratory"
                className={cn(
                  "text-left rounded-lg border p-3 transition-all",
                  !activeExperimentSpecId
                    ? "border-accent bg-accent/5 ring-1 ring-accent/20"
                    : "border-border hover:border-accent/30 hover:bg-muted/30",
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Compass className={cn("h-4 w-4", !activeExperimentSpecId ? "text-accent" : "text-muted-foreground")} />
                  <span className="text-sm font-medium">Exploratory</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  Develop the research plan from the literature without a pre-registered experiment.
                </p>
              </button>

              <button
                type="button"
                disabled={!empiricalCompatible || registeredSpecs.length === 0 || experimentCatalogLoading || experimentCatalogError}
                onClick={() => {
                  if (empiricalCompatible && registeredSpecs.length > 0) {
                    updateExperimentSpec(registeredSpecs[0]!.spec_id);
                  }
                }}
                data-testid="experiment-mode-registered"
                className={cn(
                  "text-left rounded-lg border p-3 transition-all disabled:cursor-not-allowed disabled:opacity-50",
                  activeExperimentSpecId
                    ? "border-accent bg-accent/5 ring-1 ring-accent/20"
                    : "border-border hover:border-accent/30 hover:bg-muted/30",
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <FlaskConical className={cn("h-4 w-4", activeExperimentSpecId ? "text-accent" : "text-muted-foreground")} />
                  <span className="text-sm font-medium">Registered Experiment</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  Anchor the run to a checked-in experiment specification and execute it before paper synthesis.
                </p>
              </button>
            </div>

            {!empiricalCompatible && (
              <p className="text-xs text-muted-foreground" data-testid="experiment-mode-incompatible">
                Registered experiments are available for Deep Research and Academic Proposal strategies.
              </p>
            )}
            {empiricalCompatible && experimentCatalogLoading && (
              <p className="text-xs text-muted-foreground">Loading registered experiments…</p>
            )}
            {empiricalCompatible && experimentCatalogError && (
              <p className="text-xs text-destructive" data-testid="experiment-catalog-error">
                Registered experiments could not be loaded. Exploratory mode remains available.
              </p>
            )}
            {empiricalCompatible && !experimentCatalogLoading && !experimentCatalogError && registeredSpecs.length === 0 && (
              <p className="text-xs text-muted-foreground" data-testid="experiment-catalog-empty">
                No registered experiment specifications are available.
              </p>
            )}

            {activeExperimentSpecId && selectedExperiment && (
              <div className="rounded-md border border-border bg-muted/20 p-3 space-y-2" data-testid="registered-experiment-config">
                <div className="space-y-1">
                  <label className="text-xs font-medium" htmlFor="experiment-spec-select">Experiment Specification</label>
                  <select
                    id="experiment-spec-select"
                    value={activeExperimentSpecId}
                    onChange={(e) => updateExperimentSpec(e.target.value)}
                    data-testid="experiment-spec-select"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    {registeredSpecs.map((spec) => (
                      <option key={spec.spec_id} value={spec.spec_id}>
                        {spec.spec_id} — {spec.dataset_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p><span className="font-medium text-foreground">Research question:</span> {selectedExperiment.research_question || "—"}</p>
                  <p><span className="font-medium text-foreground">Method:</span> {selectedExperiment.analysis_method || "—"}</p>
                  <p><span className="font-medium text-foreground">Primary metric:</span> {selectedExperiment.primary_metric || "—"}</p>
                  <p>The registered specification is authoritative if its experiment identity conflicts with free-text run inputs.</p>
                </div>
              </div>
            )}
          </div>

          {/* ── Research Intent ── */}
          <div className="space-y-3 pt-2">
            <label className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
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
