BATCH BLUEPRINT (SIMPLIFIED CYCLE)
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-67
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          Lead (Ivory Wolf)
Date Issued:              2026-05-04

SIMPLIFIED CYCLE ELIGIBILITY:
  [x] Exactly 1 Task — install umap-learn + hdbscan + add quality metrics
  [x] No existing source files modified (only pip install + new test + metrics)
  [x] No Hard Boundaries required
  [x] Single deliverable

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Install umap-learn and hdbscan packages, verify the existing
fallback code now uses the real algorithms, add cluster quality
metrics (silhouette score, Davies-Bouldin index) to the cluster
service output.

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Install UMAP/HDBSCAN packages and add cluster quality
                    metrics to the cluster service.
  Files in scope:
    - backend/pipeline/gap_analysis/cluster_service.py (modify — add quality metrics)
    - backend/tests/test_pipeline/test_clustering_quality.py (create)
  Acceptance Criteria:
    AC-01: Cluster service uses UMAP (not first 2 dims fallback)
    AC-02: Cluster service uses HDBSCAN (not KMeans fallback)
    AC-03: Cluster report includes silhouette_score and davies_bouldin_index

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: UMAP + HDBSCAN used when packages available
  BAC-02: Quality metrics reported in cluster output
  BAC-03: All documents archived under /docs/aiv/BATCH-67/

═══════════════════════════════════════════════════════════
