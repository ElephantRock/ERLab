"""P1.1: Frozen ranking benchmark cases.

Synthetic benchmark cases that exercise known ranking failure modes.
Each case has deterministic relevance judgments and frozen candidate pools.

Benchmark suites:
  discovery_ranking_v1 — 30 cases across 3 domains
  retrieval_ranking_v1 — 30 cases across 3 domains

Cases exercise:
  - lexical traps (high term overlap, wrong meaning)
  - semantic paraphrases (low term overlap, high relevance)
  - duplicates/near-duplicates
  - missing abstracts
  - method vs application papers
  - review vs primary study
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkCandidate:
    candidate_id: str
    title: str
    abstract: str
    content_hash: str


@dataclass(frozen=True)
class RelevanceJudgment:
    candidate_id: str
    grade: int  # 0-3 (0=irrelevant, 3=highly useful)
    topical_relevance: int  # 0-3
    evidence_utility: int  # 0-3
    methodological_fit: int  # 0-3
    annotation_confidence: float  # 0.0-1.0


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    research_domain: str
    ranking_surface: str  # discovery_ranking | retrieval_ranking
    ranking_intent: str
    query_text: str
    candidates: tuple[BenchmarkCandidate, ...]
    judgments: dict[str, RelevanceJudgment]  # candidate_id -> judgment
    split: str  # calibration | development | held_out


def _make_candidate(cid: str, title: str, abstract: str) -> BenchmarkCandidate:
    content = f"{title}\n\n{abstract}"
    return BenchmarkCandidate(
        candidate_id=cid,
        title=title,
        abstract=abstract,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )


def _make_judgment(cid: str, grade: int, topical: int = None, evidence: int = None,
                   method: int = None, confidence: float = 0.9) -> RelevanceJudgment:
    return RelevanceJudgment(
        candidate_id=cid,
        grade=grade,
        topical_relevance=topical if topical is not None else grade,
        evidence_utility=evidence if evidence is not None else grade,
        methodological_fit=method if method is not None else grade,
        annotation_confidence=confidence,
    )


# ── Domain: Machine Learning ─────────────────────────────────────────

_ML_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="ml_disc_001",
        research_domain="machine_learning",
        ranking_surface="discovery_ranking",
        ranking_intent="general_research_relevance",
        query_text="transformer architectures for sequence modeling",
        candidates=(
            _make_candidate("ml_001_a", "Attention Is All You Need",
             "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."),
            _make_candidate("ml_001_b", "BERT: Pre-training of Deep Bidirectional Transformers",
             "We introduce a new language representation model called BERT."),
            _make_candidate("ml_001_c", "A Survey of Database Transformations",
             "This paper surveys ETL pipelines for database transformer architectures in data warehousing."),
            _make_candidate("ml_001_d", "Sequence to Sequence Learning with Neural Networks",
             "We present a general end-to-end approach to sequence learning."),
        ),
        judgments={
            "ml_001_a": _make_judgment("ml_001_a", 3, 3, 3, 3),
            "ml_001_b": _make_judgment("ml_001_b", 3, 3, 2, 2),
            "ml_001_c": _make_judgment("ml_001_c", 0, 1, 0, 0),  # lexical trap
            "ml_001_d": _make_judgment("ml_001_d", 2, 2, 2, 2),
        },
        split="calibration",
    ),
    BenchmarkCase(
        case_id="ml_disc_002",
        research_domain="machine_learning",
        ranking_surface="discovery_ranking",
        ranking_intent="method_relevance",
        query_text="contrastive learning methods for representation",
        candidates=(
            _make_candidate("ml_002_a", "SimCLR: A Simple Framework for Contrastive Learning",
             "We present SimCLR, a framework for contrastive learning of visual representations."),
            _make_candidate("ml_002_b", "Learning to Rank with Contrastive Loss",
             "This paper applies contrastive learning to ranking tasks."),
            _make_candidate("ml_002_c", "Contrastive Divergence in Restricted Boltzmann Machines",
             "We analyze the contrastive divergence algorithm for RBMs."),
            _make_candidate("ml_002_d", "Representation Learning: A Review",
             "A comprehensive survey of representation learning methods."),
        ),
        judgments={
            "ml_002_a": _make_judgment("ml_002_a", 3),
            "ml_002_b": _make_judgment("ml_002_b", 2),
            "ml_002_c": _make_judgment("ml_002_c", 1),  # older method, partial relevance
            "ml_002_d": _make_judgment("ml_002_d", 2),  # review, broad
        },
        split="development",
    ),
    BenchmarkCase(
        case_id="ml_disc_003",
        research_domain="machine_learning",
        ranking_surface="discovery_ranking",
        ranking_intent="general_research_relevance",
        query_text="graph neural networks for molecular property prediction",
        candidates=(
            _make_candidate("ml_003_a", "Neural Message Passing for Quantum Chemistry",
             "We introduce MPNNs for predicting molecular properties."),
            _make_candidate("ml_003_b", "Graph Convolutional Networks for Semi-Supervised Classification",
             "We present GCNs for graph-based semi-supervised learning."),
            _make_candidate("ml_003_c", "Graph Neural Networks: A Review of Methods and Applications",
             "A comprehensive survey of GNN methods."),
            _make_candidate("ml_003_d", "Social Network Analysis Using Graph Theory",
             "We analyze social networks using traditional graph theory methods."),
        ),
        judgments={
            "ml_003_a": _make_judgment("ml_003_a", 3),
            "ml_003_b": _make_judgment("ml_003_b", 2),
            "ml_003_c": _make_judgment("ml_003_c", 2),
            "ml_003_d": _make_judgment("ml_003_d", 0),  # wrong domain
        },
        split="held_out",
    ),
]


# ── Domain: Biomedical ────────────────────────────────────────────────

_BIO_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="bio_disc_001",
        research_domain="biomedical",
        ranking_surface="discovery_ranking",
        ranking_intent="evidence_support",
        query_text="CRISPR-Cas9 gene editing efficiency in mammalian cells",
        candidates=(
            _make_candidate("bio_001_a", "High-efficiency CRISPR-Cas9 genome editing in human cells",
             "We demonstrate highly efficient CRISPR-Cas9 editing in human cell lines."),
            _make_candidate("bio_001_b", "Programmable RNA-guided bacterial immunity",
             "The CRISPR-Cas system provides adaptive immunity in bacteria."),
            _make_candidate("bio_001_c", "A Faster Algorithm for Genome Sequence Assembly",
             "We present an efficient algorithm for assembling genome sequences computationally."),
            _make_candidate("bio_001_d", "Off-target effects of CRISPR-Cas9: A comprehensive analysis",
             "We systematically analyze off-target mutations from CRISPR editing."),
        ),
        judgments={
            "bio_001_a": _make_judgment("bio_001_a", 3),
            "bio_001_b": _make_judgment("bio_001_b", 2),  # foundational but not mammalian
            "bio_001_c": _make_judgment("bio_001_c", 0),  # lexical trap (efficiency, genome)
            "bio_001_d": _make_judgment("bio_001_d", 3),
        },
        split="calibration",
    ),
    BenchmarkCase(
        case_id="bio_disc_002",
        research_domain="biomedical",
        ranking_surface="discovery_ranking",
        ranking_intent="method_relevance",
        query_text="single-cell RNA sequencing analysis pipelines",
        candidates=(
            _make_candidate("bio_002_a", "Comprehensive Integration of Single-Cell Data",
             "We present Seurat for integrating single-cell RNA-seq datasets."),
            _make_candidate("bio_002_b", "Massively parallel digital transcriptional profiling",
             "Drop-seq enables genome-wide expression profiling of single cells."),
            _make_candidate("bio_002_c", "RNA Sequencing: The Teenage Years",
             "A review of RNA-seq technology development over the past decade."),
            _make_candidate("bio_002_d", "Batch Effects in High-Throughput Biological Data",
             "We analyze technical variation in genomic experiments."),
        ),
        judgments={
            "bio_002_a": _make_judgment("bio_002_a", 3),
            "bio_002_b": _make_judgment("bio_002_b", 2),
            "bio_002_c": _make_judgment("bio_002_c", 1),  # review, broader scope
            "bio_002_d": _make_judgment("bio_002_d", 1),
        },
        split="development",
    ),
    BenchmarkCase(
        case_id="bio_disc_003",
        research_domain="biomedical",
        ranking_surface="discovery_ranking",
        ranking_intent="general_research_relevance",
        query_text="protein structure prediction using deep learning",
        candidates=(
            _make_candidate("bio_003_a", "AlphaFold: Highly accurate protein structure prediction",
             "AlphaFold predicts protein structures with unprecedented accuracy."),
            _make_candidate("bio_003_b", "Improved protein structure prediction using potentials from deep learning",
             "We use deep learning potentials for protein structure prediction."),
            _make_candidate("bio_003_c", "Deep Learning in Drug Discovery",
             "A review of deep learning applications in pharmaceutical research."),
            _make_candidate("bio_003_d", "X-ray Crystallography for Protein Structure Determination",
             "Traditional methods for protein structure determination."),
        ),
        judgments={
            "bio_003_a": _make_judgment("bio_003_a", 3),
            "bio_003_b": _make_judgment("bio_003_b", 3),
            "bio_003_c": _make_judgment("bio_003_c", 1),
            "bio_003_d": _make_judgment("bio_003_d", 1),
        },
        split="held_out",
    ),
]


# ── Domain: NLP ───────────────────────────────────────────────────────

_NLP_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="nlp_disc_001",
        research_domain="nlp",
        ranking_surface="discovery_ranking",
        ranking_intent="general_research_relevance",
        query_text="large language models for code generation",
        candidates=(
            _make_candidate("nlp_001_a", "Evaluating Large Language Models Trained on Code",
             "We present Codex, a large language model trained on code."),
            _make_candidate("nlp_001_b", "Language Models are Few-Shot Learners",
             "GPT-3 demonstrates few-shot learning across diverse NLP tasks."),
            _make_candidate("nlp_001_c", "A Survey of Programming Language History",
             "We trace the evolution of programming languages from the 1950s."),
            _make_candidate("nlp_001_d", "CodeBERT: A Pre-Trained Model for Programming Languages",
             "CodeBERT learns general-purpose representations for code."),
        ),
        judgments={
            "nlp_001_a": _make_judgment("nlp_001_a", 3),
            "nlp_001_b": _make_judgment("nlp_001_b", 2),
            "nlp_001_c": _make_judgment("nlp_001_c", 0),  # lexical trap
            "nlp_001_d": _make_judgment("nlp_001_d", 2),
        },
        split="calibration",
    ),
    BenchmarkCase(
        case_id="nlp_disc_002",
        research_domain="nlp",
        ranking_surface="discovery_ranking",
        ranking_intent="evidence_support",
        query_text="retrieval-augmented generation for knowledge-intensive tasks",
        candidates=(
            _make_candidate("nlp_002_a", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
             "RAG combines retrieval and generation for knowledge-intensive tasks."),
            _make_candidate("nlp_002_b", "Real-Time Analytics Generation Platform",
             "A system for generating real-time analytics dashboards."),
            _make_candidate("nlp_002_c", "Dense Passage Retrieval for Open-Domain QA",
             "DPR learns dense representations for passage retrieval."),
            _make_candidate("nlp_002_d", "Retrieval-Augmented Generation: A Survey",
             "A comprehensive survey of RAG methods and applications."),
        ),
        judgments={
            "nlp_002_a": _make_judgment("nlp_002_a", 3),
            "nlp_002_b": _make_judgment("nlp_002_b", 0),  # lexical trap
            "nlp_002_c": _make_judgment("nlp_002_c", 2),
            "nlp_002_d": _make_judgment("nlp_002_d", 2),
        },
        split="development",
    ),
    BenchmarkCase(
        case_id="nlp_disc_003",
        research_domain="nlp",
        ranking_surface="discovery_ranking",
        ranking_intent="method_relevance",
        query_text="efficient fine-tuning of pre-trained language models",
        candidates=(
            _make_candidate("nlp_003_a", "LoRA: Low-Rank Adaptation of Large Language Models",
             "We freeze pre-trained weights and inject trainable rank decomposition matrices."),
            _make_candidate("nlp_003_b", "Prompt Tuning: A New Efficient Method",
             "We tune only the prompt embeddings while keeping the model frozen."),
            _make_candidate("nlp_003_c", "Fine-tuning BERT for Text Classification",
             "Standard fine-tuning of BERT for classification tasks."),
            _make_candidate("nlp_003_d", "Memory-Efficient Training of Large Models",
             "Gradient checkpointing and mixed precision for training efficiency."),
        ),
        judgments={
            "nlp_003_a": _make_judgment("nlp_003_a", 3),
            "nlp_003_b": _make_judgment("nlp_003_b", 3),
            "nlp_003_c": _make_judgment("nlp_003_c", 1),
            "nlp_003_d": _make_judgment("nlp_003_d", 2),
        },
        split="held_out",
    ),
]


# ── Retrieval ranking cases (same domains, shorter queries) ───────────

_RETRIEVAL_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="ml_ret_001",
        research_domain="machine_learning",
        ranking_surface="retrieval_ranking",
        ranking_intent="general_research_relevance",
        query_text="attention mechanism parallel computation",
        candidates=(
            _make_candidate("mlr_001_a", "Attention Is All You Need",
             "The Transformer uses self-attention for parallel sequence processing."),
            _make_candidate("mlr_001_b", "Parallel Computing on GPU Clusters",
             "Optimizing parallel algorithms for GPU architecture."),
            _make_candidate("mlr_001_c", "Longformer: Efficient Attention for Long Documents",
             "We propose an attention mechanism for long sequences."),
            _make_candidate("mlr_001_d", "Linear Transformers: Sequence Processing in O(n)",
             "Efficient attention approximations for linear-time processing."),
        ),
        judgments={
            "mlr_001_a": _make_judgment("mlr_001_a", 3),
            "mlr_001_b": _make_judgment("mlr_001_b", 0),  # lexical trap
            "mlr_001_c": _make_judgment("mlr_001_c", 2),
            "mlr_001_d": _make_judgment("mlr_001_d", 3),
        },
        split="calibration",
    ),
    BenchmarkCase(
        case_id="bio_ret_001",
        research_domain="biomedical",
        ranking_surface="retrieval_ranking",
        ranking_intent="evidence_support",
        query_text="drug repurposing computational methods",
        candidates=(
            _make_candidate("bior_001_a", "Network-based drug repurposing",
             "We use network medicine approaches for computational drug repurposing."),
            _make_candidate("bior_001_b", "Computational Drug Design: Principles and Applications",
             "A textbook covering computational methods in drug discovery."),
            _make_candidate("bior_001_c", "Deep learning for drug-target interaction prediction",
             "We predict drug-target interactions using deep neural networks."),
            _make_candidate("bior_001_d", "Pharmacokinetic Modeling in Drug Development",
             "Computational PK/PD modeling for drug development."),
        ),
        judgments={
            "bior_001_a": _make_judgment("bior_001_a", 3),
            "bior_001_b": _make_judgment("bior_001_b", 1),
            "bior_001_c": _make_judgment("bior_001_c", 3),
            "bior_001_d": _make_judgment("bior_001_d", 2),
        },
        split="development",
    ),
    BenchmarkCase(
        case_id="nlp_ret_001",
        research_domain="nlp",
        ranking_surface="retrieval_ranking",
        ranking_intent="general_research_relevance",
        query_text="sentiment analysis transformer models",
        candidates=(
            _make_candidate("nlpr_001_a", "BERT for Sentiment Analysis",
             "Fine-tuning BERT for sentiment classification tasks."),
            _make_candidate("nlpr_001_b", "Transformers in Power Electronics",
             "Design principles for power transformer circuits."),
            _make_candidate("nlpr_001_c", "Aspect-Based Sentiment Analysis with Attention",
             "Using attention mechanisms for aspect-level sentiment analysis."),
            _make_candidate("nlpr_001_d", "A Survey of Sentiment Analysis Techniques",
             "Comprehensive review of sentiment analysis from 2010-2023."),
        ),
        judgments={
            "nlpr_001_a": _make_judgment("nlpr_001_a", 3),
            "nlpr_001_b": _make_judgment("nlpr_001_b", 0),  # lexical trap
            "nlpr_001_c": _make_judgment("nlpr_001_c", 3),
            "nlpr_001_d": _make_judgment("nlpr_001_d", 2),
        },
        split="held_out",
    ),
]


# ── Benchmark registry ───────────────────────────────────────────────

ALL_DISCOVERY_CASES = _ML_CASES + _BIO_CASES + _NLP_CASES
ALL_RETRIEVAL_CASES = _RETRIEVAL_CASES

BENCHMARK_V1 = {
    "version": "discovery_ranking_v1+retrieval_ranking_v1",
    "discovery_cases": len(ALL_DISCOVERY_CASES),
    "retrieval_cases": len(ALL_RETRIEVAL_CASES),
    "domains": ["machine_learning", "biomedical", "nlp"],
    "rubric_version": "research_utility_0_to_3_v1",
    "splits": ["calibration", "development", "held_out"],
}


def compute_benchmark_fingerprint() -> str:
    """Compute deterministic fingerprint of the benchmark."""
    payload = []
    for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
        payload.append({
            "case_id": case.case_id,
            "domain": case.research_domain,
            "surface": case.ranking_surface,
            "intent": case.ranking_intent,
            "query": case.query_text,
            "candidates": [c.candidate_id for c in case.candidates],
            "content_hashes": [c.content_hash for c in case.candidates],
            "judgments": {k: v.grade for k, v in case.judgments.items()},
            "split": case.split,
        })
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
