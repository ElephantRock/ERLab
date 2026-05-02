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
}

export interface PipelineRunSummary {
  id: number;
  status: "pending" | "running" | "completed" | "failed";
  domain: string;
  current_stage: string | null;
  ideas_count: number;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  config: Record<string, unknown>;
  stages_completed: string[];
  ideas: IdeaSummary[];
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

export interface IdeaDetail extends IdeaSummary {
  problem_statement: string;
  proposed_method: string;
  expected_contributions: string;
  source_gap_ids: string[] | null;
  novelty_report: Record<string, unknown> | null;
  feasibility_report: Record<string, unknown> | null;
  proposal_md: string | null;
  proposal_latex: string | null;
  proposal_sections: Record<string, unknown> | null;
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

export interface ResearchGap {
  id: number;
  title: string;
  description: string;
  gap_type: string;
  confidence: number;
  potential_impact: string;
  idea_count: number;
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

// --- Status ---

export interface SystemStatus {
  app_name: string;
  version: string;
  config: Record<string, boolean>;
  defaults: Record<string, number>;
}
