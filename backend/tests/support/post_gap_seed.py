"""Typed synthetic post-gap seed for downstream-pipeline proof.

This module defines the canonical typed fixture that replaces the first
three pipeline stages (literature search, ingestion, gap analysis) for
deterministic, network-free downstream testing.

Provenance contract — every synthetic identity clearly indicates its
origin:

    source = "synthetic"
    paper IDs prefixed SYN-
    paper URLs use urn:erlab:synthetic:
    gap titles are human-readable and clearly synthetic

The checked-in JSON fixture (``post_gap/low_resource_mt_v1.json``) MUST
equal the canonical serialized model output. A drift test
(``test_post_gap_seed_schema.py``) enforces this independently of any
pipeline execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.pipeline.gap_analysis.models import (
    ClusterInfo,
    ClusterReport,
    ResearchGap,
)
from backend.pipeline.literature.models import Author, Paper

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "post_gap"
FIXTURE_PATH = FIXTURE_DIR / "low_resource_mt_v1.json"


class SyntheticPostGapSeed(BaseModel):
    """Canonical typed seed carrying the inputs a real gap-analysis stage
    would produce: papers, the cluster report, and the identified gaps.

    Downstream stages consume ``papers`` and ``gaps`` exactly as production
    code would; only the model responses are synthetic (Commit 5).
    """

    schema_version: Literal["erlab.post_gap_seed.v1"] = "erlab.post_gap_seed.v1"
    fixture_id: str
    synthetic: Literal[True] = True
    domain: str
    research_question: str
    papers: list[Paper]
    cluster_report: ClusterReport
    gaps: list[ResearchGap]


def _syn_paper(pid: str, title: str, abstract: str, year: int, cluster: int) -> Paper:
    """Build a clearly-synthetic paper with explicit provenance."""
    return Paper(
        id=f"SYN-{pid}",
        source="synthetic",
        title=title,
        abstract=abstract,
        authors=[Author(name="Synthetic Author")],
        year=year,
        venue="Synthetic Workshop",
        citation_count=0,
        url=f"urn:erlab:synthetic:paper:{pid}",
        doi=None,
        arxiv_id=None,
        embedding=None,
    )


def build_low_resource_mt_seed() -> SyntheticPostGapSeed:
    """Construct the canonical low-resource machine-translation seed.

    Scenario: cross-lingual transfer for low-resource languages is
    underexplored. Two research clusters emerge from three synthetic
    surveys; two valid research gaps are identified.

    Returns a deterministic, network-free seed. The checked-in fixture
    must equal this model's canonical JSON serialization.
    """
    papers = [
        _syn_paper(
            "lrmt-001",
            "A Survey of Low-Resource Machine Translation Benchmarks",
            (
                "We survey benchmarks for low-resource machine translation, "
                "covering 40 language pairs and evaluating data scarcity, "
                "tokenization, and evaluation metric reliability. We find that "
                "standard BLEU scores under-report quality for morphologically "
                "rich languages and that few benchmarks include truly low-"
                "resource African or Oceanic languages."
            ),
            2023,
            cluster=0,
        ),
        _syn_paper(
            "lrmt-002",
            "Cross-Lingual Transfer for Endangered Languages: A Review",
            (
                "Cross-lingual transfer from multilingual encoders has advanced "
                "for medium-resource languages but struggles for endangered "
                "languages with minimal monolingual data. We review transfer "
                "techniques and identify open problems in script normalization, "
                "code-switching, and dialect continua."
            ),
            2024,
            cluster=0,
        ),
        _syn_paper(
            "lrmt-003",
            "Evaluation Metrics for Morphologically Rich Languages",
            (
                "Standard MT evaluation metrics assume whitespace tokenization "
                "and fail on morphologically rich, agglutinative languages. We "
                "propose morpheme-aware metrics and show that chrF under-estimates "
                "fluency for polysynthetic languages."
            ),
            2023,
            cluster=1,
        ),
    ]

    cluster_report = ClusterReport(
        clusters=[
            ClusterInfo(
                cluster_id=0,
                label="low-resource transfer",
                paper_count=2,
                top_terms=["transfer", "low-resource", "endangered"],
                avg_citations=0.0,
            ),
            ClusterInfo(
                cluster_id=1,
                label="evaluation metrics",
                paper_count=1,
                top_terms=["metrics", "morphology", "chrf"],
                avg_citations=0.0,
            ),
        ],
        total_papers=3,
        silhouette_score=None,
        davies_bouldin_index=None,
    )

    gaps = [
        ResearchGap(
            title="Lack of truly low-resource African and Oceanic language pairs in MT benchmarks",
            description=(
                "Existing low-resource MT benchmarks rarely include truly "
                "low-resource African or Oceanic languages with under 10k "
                "parallel sentences. Transfer methods are validated on medium-"
                "resource pairs, leaving their effectiveness on the lowest-"
                "resource settings unmeasured."
            ),
            gap_type="empirical",
            related_clusters=[0],
            potential_impact=(
                "Robust benchmarks for the lowest-resource languages would "
                "expose where cross-lingual transfer actually breaks and guide "
                "targeted data collection."
            ),
            confidence=0.82,
        ),
        ResearchGap(
            title="Morpheme-aware evaluation metrics are unvalidated for polysynthetic languages",
            description=(
                "Morpheme-aware metrics have been proposed but never validated "
                "on polysynthetic languages where a single word encodes a full "
                "clause. It is unknown whether such metrics correlate with human "
                "fluency judgments in these settings."
            ),
            gap_type="methodological",
            related_clusters=[1],
            potential_impact=(
                "Validated morpheme-aware metrics would make MT evaluation "
                "trustworthy for the languages where it currently fails most."
            ),
            confidence=0.76,
        ),
    ]

    return SyntheticPostGapSeed(
        fixture_id="low_resource_mt_v1",
        synthetic=True,
        domain="NLP / Machine Translation",
        research_question=(
            "How can cross-lingual transfer and evaluation be made reliable for "
            "truly low-resource languages?"
        ),
        papers=papers,
        cluster_report=cluster_report,
        gaps=gaps,
    )


def load_seed(path: Path | None = None) -> SyntheticPostGapSeed:
    """Load and validate the checked-in fixture against the current models."""
    target = path or FIXTURE_PATH
    return SyntheticPostGapSeed.model_validate_json(target.read_text(encoding="utf-8"))


def serialize_seed(seed: SyntheticPostGapSeed | None = None) -> str:
    """Return the canonical deterministic JSON for the seed."""
    model = seed or build_low_resource_mt_seed()
    return json.dumps(
        model.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
