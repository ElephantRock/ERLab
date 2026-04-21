import {
  Search,
  FileText,
  GitBranch,
  Lightbulb,
  Shield,
  BarChart3,
  FilePen,
  Download,
  type LucideIcon,
} from "lucide-react";

export interface StageInfo {
  key: string;
  label: string;
  icon: LucideIcon;
}

export const PIPELINE_STAGES: readonly StageInfo[] = [
  { key: "literature_search", label: "Literature Search", icon: Search },
  { key: "ingestion", label: "PDF Ingestion", icon: FileText },
  { key: "gap_analysis", label: "Gap Analysis", icon: GitBranch },
  { key: "idea_generation", label: "Idea Generation", icon: Lightbulb },
  { key: "novelty_checking", label: "Novelty Checking", icon: Shield },
  { key: "feasibility_scoring", label: "Feasibility Scoring", icon: BarChart3 },
  { key: "proposal_synthesis", label: "Proposal Synthesis", icon: FilePen },
  { key: "export", label: "Export", icon: Download },
] as const;

export const API_PREFIX = "/api/v1";
