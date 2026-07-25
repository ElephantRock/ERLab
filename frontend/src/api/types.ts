// --- Pipeline ---

export interface PipelineRunRequest {
  domain?: string;
  // Phase 1 1B: optional natural-language research question — the primary
  // research intent when supplied. Threaded through to literature search and
  // synthesis on the backend.
  research_question?: string | null;
  max_gaps?: number;
  generation_rounds?: number | null;
  ideas_per_round?: number | null;
  search_queries?: string[] | null;
  run_novelty?: boolean;
  run_feasibility?: boolean;
  run_synthesis?: boolean;
  export_format?: string;
  session_id?: string | null;
  strategy?: string;
  model_overrides?: Record<string, string> | null;
  proposal_depth?: "concise" | "standard" | "detailed";
  novelty_depth?: "light" | "standard" | "thorough";
  idea_diversity?: "focused" | "balanced" | "exploratory";
}

export interface PipelineRunSummary {
  id: number;
  status: "pending" | "running" | "completed" | "failed";
  domain: string;
  current_stage: string | null;
  ideas_count: number;
  session_id: string | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  strategy?: string;
}

export interface TreeNode {
  id: string;
  title: string;
  score: number;
  proposed_method: string;
  parent_ids: string[];
}

export interface TreeData {
  engine: string;
  config: {
    beam_width: number;
    max_depth: number;
    ideas_per_node: number;
  };
  nodes: TreeNode[];
}

export interface PipelineRunDetail extends PipelineRunSummary {
  config: Record<string, unknown>;
  stages_completed: string[];
  ideas: IdeaSummary[];
  tree_data: TreeData | null;
}

export interface TriggerRunResponse {
  run_id: string;
  status: string;
}

export interface AutonomousCycleRequest {
  domain?: string;
  max_runs?: number;
}

export interface AutonomousCycleResponse {
  cycle_id: string;
  status: string;
  domain: string;
  max_runs: number;
}

// --- SSE ---

export interface StageProgressEvent {
  stage: string;
  index: number;
  total: number;
  elapsed: number;
}

export interface ProgressDoneEvent {
  done: true;
}

export interface HeartbeatEvent {
  heartbeat: true;
}

export type ProgressEvent = StageProgressEvent | ProgressDoneEvent | HeartbeatEvent;

// --- Ideas ---

export interface QualitySummary {
  passed: number;
  total: number;
  has_issues: boolean;
}

export interface IdeaSummary {
  id: number;
  title: string;
  domain: string;
  novelty_score: number | null;
  feasibility_score: number | null;
  overall_score: number | null;
  source_gap_ids: string[] | null;
  has_proposal: boolean;
  pipeline_run_id: number | null;
  created_at: string;
  quality_summary?: QualitySummary | null;
  governance_status?: "approved" | "denied" | "needs_changes" | null;
  reference_count?: number;
  cited_count?: number;
  supporting_count?: number;
}

export interface ExperimentResult {
  id: number;
  success: boolean;
  exit_code: number;
  execution_time_seconds: number;
  stdout: string | null;
  error: string | null;
  created_at: string;
}

export interface PerspectiveReview {
  perspective: string;
  score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

export interface EnsembleReview {
  overall_score: number;
  methodology: PerspectiveReview | null;
  novelty: PerspectiveReview | null;
  clarity: PerspectiveReview | null;
  consensus_strengths: string[];
  critical_weaknesses: string[];
  actionable_suggestions: string[];
  summary: string;
  risk_flags?: string[];
}

export interface IdeaDetail extends IdeaSummary {
  problem_statement: string;
  proposed_method: string;
  expected_contributions: string;
  source_gap_ids: string[] | null;
  source_gaps: SourceGap[] | null;
  novelty_report: Record<string, unknown> | null;
  feasibility_report: Record<string, unknown> | null;
  proposal_md: string | null;
  proposal_latex: string | null;
  proposal_sections: Record<string, unknown> | null;
  proposal_references: ResolvedReference[] | string | null;
  supporting_papers: SupportingPaper[] | null;
  quality_checks: QualityCheckResult[] | null;
  section_hashes: Record<string, string> | null;
  remediation_hints: RemediationHint[] | null;
  citation_audit: CitationAuditEntry[] | null;
  mechanical_metrics: Record<string, number> | null;
  experiment_results: ExperimentResult[] | null;
  // Phase 1 1C/1D/1F: exposed full-paper artifact + paper-level evaluation.
  paper: PaperArtifact | null;
}

/**
 * Phase 1 1C: the persisted full-paper artifact and its state.
 * State machine: not_requested | pending | ready | failed.
 * An empty/placeholder paper is never reported as ready.
 */
export interface PaperArtifact {
  status: "not_requested" | "pending" | "ready" | "failed";
  paper_md: string | null;
  title: string | null;
  word_count: number | null;
  venue: string | null;
  model_used: string | null;
  source_count: number | null;
  synthesis_strategy: string | null;
  generated_at: string | null;
  source_run_id: number | null;
  /** Phase 1 1D: paper-level evaluation (scope=paper), distinct from proposal evaluation. */
  paper_evaluation: PaperEvaluation | null;
}

/** Phase 1 1D: paper-scoped evaluation. scope is always "paper". */
export interface PaperEvaluation {
  status: "ready" | "failed" | "unavailable";
  scope: "paper";
  evaluated_object?: string;
  dimensions?: Record<string, unknown>;
  error?: string;
}

// ── Phase 2: Trust & Sources review ───────────────────────────────

/** Phase 2 2B: a cited source with resolution, review, and section data. */
export interface ReviewSource {
  source_ref_hash: string;
  citation_marker: string | null;
  ref_number: number | null;
  raw: string;
  title: string | null;
  authors: string | null;
  year: string | null;
  venue: string | null;
  url: string | null;
  doi: string | null;
  resolution_status: "resolved" | "unresolved";
  /** null when unavailable — never fabricated (truth rule). */
  match_method: string | null;
  /** null when unavailable — never fabricated (truth rule). */
  confidence: number | null;
  sections_used: string[];
  human_decision: SourceReviewDecision | null;
}

export interface SourceReviewDecision {
  decision: "accepted" | "flagged" | "exclude_on_next_revision";
  note: string | null;
  reviewer: string;
  reviewed_at: string | null;
}

export interface ReviewAutomatedChecks {
  paper_evaluation: PaperEvaluation | { status: string; scope: "paper" };
  proposal_evaluation:
    | { scope: "proposal"; dimensions?: Record<string, unknown> }
    | { scope: "proposal"; status: string }
    | null;
  citation_audit: CitationAuditEntry[];
  quality_checks: QualityCheckResult[];
}

export interface HumanReviewSummary {
  status: "not_started" | "in_progress" | "completed" | "completed_with_flags";
  reviewable_sources: number;
  reviewed_sources: number;
  accepted: number;
  flagged_or_excluded: number;
  decisions_total: number;
}

/** Phase 2 2B: the normalized review contract. */
export interface ReviewPayload {
  idea_id: number;
  automated_checks: ReviewAutomatedChecks;
  sources: ReviewSource[];
  human_review: HumanReviewSummary;
  regeneration_available: boolean;
}

/** Phase 2 2E: request to record a source-review decision. */
export interface SourceReviewDecisionRequest {
  source_ref_hash: string;
  source_ref_number?: number | null;
  decision: "accepted" | "flagged" | "exclude_on_next_revision";
  note?: string;
  reviewer?: string;
}

export interface SourceGap {
  id: number;
  title: string;
  gap_type: string;
  confidence: number;
  resolved: true;
}

export interface UnresolvedSourceGap {
  raw: string;
  resolved: false;
}

export interface ProposalReference {
  raw: string;
}

export interface QualityCheckEntry {
  name: string;
  passed: boolean;
}

export interface QualityCheckResult {
  section: string;
  label: string;
  present: boolean;
  word_count: number;
  min_words: number;
  meets_word_count: boolean;
  checks: QualityCheckEntry[];
  passed: boolean;
  failures: string[];
}

export interface RemediationHint {
  section: string;
  label: string;
  issue_type: "word_count" | "missing_pattern" | "missing_section";
  severity: "error" | "warning";
  message: string;
  suggestion: string;
  refinement_available: boolean;
}

export interface CitationAuditEntry {
  section: string;
  label: string;
  citation_needed_count: number;
  valid_citation_count: number;
  has_citation_issues: boolean;
  resolved_reference_count?: number;
  unresolved_reference_count?: number;
}

// --- Section Refinement (Release 2) ---

export interface SectionRefinementResponse {
  revision_id: number;
  section_key: string;
  previous_hash: string;
  section_hash: string;
  quality_checks_before: QualityCheckResult[];
  quality_checks_after: QualityCheckResult[];
  model_receipt: {
    requested_model: string;
    served_model: string;
    provider: string;
    endpoint: string;
    timestamp: string;
    context_length: number | null;
  } | null;
}

export interface RevisionEntry {
  id: number;
  source: string;
  trigger: string;
  trigger_detail: Record<string, unknown> | null;
  section_hash: string;
  model_receipt: Record<string, unknown> | null;
  quality_summary: {
    section: string;
    passed: boolean;
    word_count: number;
    min_words: number;
    failures: string[];
  } | null;
  created_at: string;
  is_current: boolean;
}

export interface SyntheticOriginal {
  source: string;
  section_hash: string | null;
  quality_summary: {
    section: string;
    passed: boolean;
    word_count: number;
    min_words: number;
    failures: string[];
  } | null;
  note: string;
}

export interface RevisionHistoryResponse {
  revisions: RevisionEntry[];
  synthetic_original: SyntheticOriginal | null;
  current_hash: string;
}

export interface SupportingPaper {
  id: number;
  title: string;
  year: number | null;
  venue: string | null;
  citation_count: number | null;
  doi: string | null;
  arxiv_id: string | null;
  url: string | null;
  role: string;
}

export interface ResolvedReference {
  raw: string;
  number: number | null;
  authors: string | null;
  year: string | null;
  title: string | null;
  venue: string | null;
  resolved: boolean;
  paper: { id: number; title: string; year: number | null; venue: string | null; doi: string | null; arxiv_id: string | null; url: string | null } | null;
  match_method: string | null;
  match_confidence: number;
}

export interface IdeaListResponse {
  ideas: IdeaSummary[];
  total: number;
  score_guide: Record<string, Record<string, string>>;
}

export interface IdeaFeedbackRequest {
  rating: number;
  notes?: string | null;
}

// --- Gaps ---

export interface RelatedIdea {
  id: number;
  title: string;
  overall_score: number | null;
}

export interface MatchedPaper {
  id: number;
  title: string;
  abstract: string | null;
  year: number | null;
  venue: string | null;
  citation_count: number | null;
}

export interface ResearchGap {
  id: number;
  title: string;
  description: string;
  gap_type: string;
  confidence: number;
  potential_impact: string;
  idea_count: number;
  // Backend exposes pipeline_run_id (int | null) on the gap response
  // (see backend/api/routes/gaps.py and ResearchGapDB model).
  pipeline_run_id?: number | null;
  truth?: { frequency: number; confidence: number; evidence_count: number };
  related_clusters?: number[] | null;
  related_ideas?: RelatedIdea[] | null;
  matched_papers_preview?: MatchedPaper[] | null;
  status?: string;
  user_rating?: number | null;
  user_notes?: string | null;
}

export interface GapListResponse {
  gaps: ResearchGap[];
  total: number;
}

// --- Knowledge ---

export interface KnowledgeSearchResult {
  id: string;
  text: string;
  metadata: Record<string, string>;
  distance: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
}

export interface KnowledgeStats {
  chroma_persist_dir: string;
  embedding_provider: string;
  embedding_model: string;
  total_documents: number;
  total_chunks: number;
}

export interface IngestResponse {
  status: string;
  filename: string;
  chunks: number;
}

// --- Sessions ---

export interface SessionGroup {
  session_id: string;
  run_count: number;
  latest_run_at: string;
}

export interface SessionListResponse {
  sessions: SessionGroup[];
}

// --- Status ---

export interface SystemStatus {
  app_name: string;
  version: string;
  // Config holds mixed-typed flag/string values (e.g. default_provider is a
  // string, governance_enabled/memory_enabled are booleans). Typed as the
  // union to match what the backend actually returns.
  config: Record<string, boolean | string>;
  defaults: Record<string, number>;
}

// --- Global Search (BATCH-48) ---

export interface Notification {
  id: number;
  user_id: number | null;
  type: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
}

// --- Global Search (BATCH-48) ---

export interface IdeaSearchItem {
  id: number;
  title: string;
  domain: string;
  overall_score: number;
}

export interface GapSearchItem {
  id: number;
  title: string;
  gap_type: string;
  confidence: number;
}

export interface PaperSearchItem {
  id: number;
  title: string;
  year: number;
  venue: string;
}

export interface RunSearchItem {
  id: number;
  status: string;
  domain: string;
  created_at: string;
}

export interface GlobalSearchResponse {
  query: string;
  results: {
    ideas?: { total: number; items: IdeaSearchItem[] };
    gaps?: { total: number; items: GapSearchItem[] };
    papers?: { total: number; items: PaperSearchItem[] };
    runs?: { total: number; items: RunSearchItem[] };
  };
  total: number;
}
