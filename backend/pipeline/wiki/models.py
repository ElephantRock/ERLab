"""Wiki models — structured wiki entry for research papers.

AIV v5.3 — BATCH-123
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WikiEntry:
    """A structured wiki entry summarizing a research paper.

    30-field JSON representation covering every aspect of the paper.
    """

    paper_id: str = ""

    # Core summary
    one_line_summary: str = ""
    problem_statement: str = ""
    proposed_method: str = ""

    # Insights
    key_insights: list[str] = field(default_factory=list)

    # Method breakdown
    method_details: dict = field(default_factory=dict)
    # Keys: architecture, training_procedure, loss_function, data_strategy,
    #       inference_strategy, key_hyperparameters, computational_requirements

    # Experiments
    experiments: list[dict] = field(default_factory=list)
    # Each dict: dataset, metric, value, baseline_method, baseline_value, key_finding

    # Analysis
    limitations: list[str] = field(default_factory=list)
    future_work: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)

    # Resources
    code_and_resources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Assessment
    novelty_assessment: str = ""  # incremental | significant | breakthrough
    contribution_type: str = ""   # empirical | theoretical | methodological | dataset
    domain: str = ""              # e.g., "NLP", "Computer Vision", "RL"
    subdomain: str = ""           # e.g., "Language Modeling", "Object Detection"

    # Paper metadata (extracted)
    paper_type: str = ""          # conference | journal | preprint | workshop
    publication_venue: str = ""
    authors_summary: str = ""
    year: int = 0

    # Verifier output
    quality_score: float = 0.0           # 0-1, set by WikiVerifier
    unsupported_claims: list[str] = field(default_factory=list)
    verification_results: list = field(default_factory=list)  # List[ClaimVerificationResult]
    trust_tier_summary: str = ""          # Aggregate trust: "3 HIGH, 2 MEDIUM, 1 LOW"

    # Additional
    related_methods: list[str] = field(default_factory=list)
    potential_applications: list[str] = field(default_factory=list)
    reproducibility_notes: str = ""
