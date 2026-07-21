import {
  Search,
  FileText,
  GitBranch,
  Lightbulb,
  Shield,
  BarChart3,
  FilePen,
  Download,
  Activity,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

// F1.1 M4: renamed from StageInfo to PipelineStage to disambiguate from
// the backend-mirror StageInfo in api/settings.ts ({name, label, category,
// needs_llm}). This is a UI presentation constant (key + label + icon);
// the backend mirror is a different shape for a different purpose.
export interface PipelineStage {
  key: string;
  label: string;
  icon: LucideIcon;
}

export const PIPELINE_STAGES: readonly PipelineStage[] = [
  { key: "literature_search", label: "Literature Search", icon: Search },
  { key: "ingestion", label: "PDF Ingestion", icon: FileText },
  { key: "gap_analysis", label: "Gap Analysis", icon: GitBranch },
  { key: "idea_generation", label: "Idea Generation", icon: Lightbulb },
  { key: "novelty_checking", label: "Novelty Checking", icon: Shield },
  { key: "feasibility_scoring", label: "Feasibility Scoring", icon: BarChart3 },
  { key: "proposal_synthesis", label: "Proposal Synthesis", icon: FilePen },
  { key: "mechanical_metrics", label: "Mechanical Metrics", icon: Activity },
  { key: "proposal_deepening", label: "Proposal Deepening", icon: Sparkles },
  { key: "export", label: "Export", icon: Download },
] as const;

export const API_PREFIX = "/api/v1";
