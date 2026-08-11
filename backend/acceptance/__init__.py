"""Live-paper acceptance framework.

Test/acceptance-only package. Builds a typed acceptance layer around the
existing production runner (``run_e2e_pipeline.py``) and the real
``deep_research`` orchestrator. Acceptance code classifies results and
emits evidence; it MUST NOT generate research content (ideas, proposals,
papers, evaluations, or citations).
"""
