/** Ops Dashboard API client. */

import { callContract } from "./contracts/common";
import { getOpsDashboardContract } from "./contracts/dashboard";

export interface OpsDashboard {
  window: { days: number; from: string; to: string };
  run_health: {
    total_runs: number;
    completed: number;
    failed: number;
    cancelled: number;
    running: number;
    pending: number;
    average_duration_s: number;
    slowest_stages: {
      stage: string;
      avg_seconds: number;
      max_seconds: number;
      samples: number;
    }[];
    error?: string;
  };
  model_usage: {
    models: {
      provider: string;
      served_model: string;
      calls: number;
    }[];
    total_receipts: number;
    warnings: string[];
    error?: string;
  };
  source_health: {
    papers_found_total: number;
    zero_result_runs: number;
    sources: { source: string; papers: number }[];
    error?: string;
  };
  quality_trends: {
    proposal_count: number;
    quality_pass_rate: number;
    common_failures: { failure: string; count: number }[];
    citation_resolution_rate: number | null;
    total_citation_needed: number;
    total_valid_citations: number;
    remediation_count: number;
    restore_count: number;
    error?: string;
  };
}

export function getOpsDashboard(days = 7, limit?: number): Promise<OpsDashboard> {
  // F1.3a: migrated from apiFetchUnchecked to callContract
  return callContract(getOpsDashboardContract, { query: { days, limit } });
}
