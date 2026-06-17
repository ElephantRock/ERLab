// --- Pipeline ---

export interface PipelineRunRequest {
  domain?: string;
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
  proposal_references: ProposalReference[] | string | null;
  mechanical_metrics: Record<string, number> | null;
  experiment_results: ExperimentResult[] | null;
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
  config: Record<string, boolean>;
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
