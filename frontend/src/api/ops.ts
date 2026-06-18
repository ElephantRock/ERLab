/** Ops Dashboard API client. */

import { apiFetch } from "./client";

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

export function getOpsDashboard(
  days?: number,
  limit?: number,
): Promise<OpsDashboard> {
  const params = new URLSearchParams();
  if (days) params.set("days", String(days));
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return apiFetch(`/ops/dashboard${qs ? `?${qs}` : ""}`);
}
