"""P1E.1 — v3 corpus generator (88 grade-free candidate cases).

Constructs the v3 candidate corpus from:
  1. The 44 frozen v2 cal+dev cases (EXTENDED candidate pools: v2 candidates
     preserved verbatim + constructed hard negatives / lexical traps /
     near-duplicates injected). v2 candidate text is byte-identical (proven
     by content_hash); v2/v3 ID collisions are impossible (v3_ prefix).
  2. 44 fully-new cases per the sealed allocation table
     (allocation_table_sha256 ffb05ad3…).

The candidate layer is GRADE-FREE. No field asserts a relevance grade.
Construction metadata (mining_role, near_duplicate_of, query_generation_anchor)
expresses intent/provenance only.

Composition (frozen, protocol d2e16ae):
    total 88 = 33 cal + 33 dev + 22 held_out
    v2-lineage (extended) 44 ; fully-new 44
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases
from backend.ranking.benchmark_v3_candidates import (
    V3CandidateCase,
    v3_candidate,
    v3_case,
)
from backend.ranking.p1e1_canon import content_hash

# ── Frozen allocation table (44 fully-new cases) ─────────────────────
# Matches allocation_table_sha256 5a7985827b319d21a4944b603317cb9011071f7a62e9392eaedf7dde2df2ff96
# (protocol v2 calibration correction: 4 cases per slice, balanced; the v1
# table ffb05ad3… was uneven — lexical_trap 6, neutral 2 — violating the
# global slice-balance tolerance. v1 protocol d2e16ae preserved unchanged.)
# Each slice gets exactly 4 cases: 1 calibration + 1 development + 2 held_out,
# domains rotated per slice so global domain max-min <= 1.
_FULLY_NEW_ALLOCATION: list[tuple[str, str, str, str]] = [
    ("disc", "lexical_trap", "machine_learning", "calibration"),
    ("ret",  "lexical_trap", "biomedical", "development"),
    ("disc", "lexical_trap", "nlp", "held_out"),
    ("ret",  "lexical_trap", "machine_learning", "held_out"),
    ("disc", "semantic_paraphrase", "biomedical", "calibration"),
    ("ret",  "semantic_paraphrase", "nlp", "development"),
    ("disc", "semantic_paraphrase", "machine_learning", "held_out"),
    ("ret",  "semantic_paraphrase", "biomedical", "held_out"),
    ("disc", "method_vs_application", "nlp", "calibration"),
    ("ret",  "method_vs_application", "machine_learning", "development"),
    ("disc", "method_vs_application", "biomedical", "held_out"),
    ("ret",  "method_vs_application", "nlp", "held_out"),
    ("disc", "review_vs_primary", "machine_learning", "calibration"),
    ("ret",  "review_vs_primary", "biomedical", "development"),
    ("disc", "review_vs_primary", "nlp", "held_out"),
    ("ret",  "review_vs_primary", "machine_learning", "held_out"),
    ("disc", "missing_abstract", "biomedical", "calibration"),
    ("ret",  "missing_abstract", "nlp", "development"),
    ("disc", "missing_abstract", "machine_learning", "held_out"),
    ("ret",  "missing_abstract", "biomedical", "held_out"),
    ("disc", "near_duplicate", "nlp", "calibration"),
    ("ret",  "near_duplicate", "machine_learning", "development"),
    ("disc", "near_duplicate", "biomedical", "held_out"),
    ("ret",  "near_duplicate", "nlp", "held_out"),
    ("disc", "source_rank_conflict", "machine_learning", "calibration"),
    ("ret",  "source_rank_conflict", "biomedical", "development"),
    ("disc", "source_rank_conflict", "nlp", "held_out"),
    ("ret",  "source_rank_conflict", "machine_learning", "held_out"),
    ("disc", "acronym_vs_expanded", "biomedical", "calibration"),
    ("ret",  "acronym_vs_expanded", "nlp", "development"),
    ("disc", "acronym_vs_expanded", "machine_learning", "held_out"),
    ("ret",  "acronym_vs_expanded", "biomedical", "held_out"),
    ("disc", "negated_findings", "nlp", "calibration"),
    ("ret",  "negated_findings", "machine_learning", "development"),
    ("disc", "negated_findings", "biomedical", "held_out"),
    ("ret",  "negated_findings", "nlp", "held_out"),
    ("disc", "exact_identifier", "machine_learning", "calibration"),
    ("ret",  "exact_identifier", "biomedical", "development"),
    ("disc", "exact_identifier", "nlp", "held_out"),
    ("ret",  "exact_identifier", "machine_learning", "held_out"),
    ("disc", "neutral", "biomedical", "calibration"),
    ("ret",  "neutral", "nlp", "development"),
    ("disc", "neutral", "machine_learning", "held_out"),
    ("ret",  "neutral", "biomedical", "held_out"),
]

_SLICE_ABBR = {
    "lexical_trap": "lt", "semantic_paraphrase": "sp", "method_vs_application": "mv",
    "review_vs_primary": "rv", "missing_abstract": "ma", "near_duplicate": "nd",
    "source_rank_conflict": "sr", "acronym_vs_expanded": "ac", "negated_findings": "nf",
    "exact_identifier": "ei", "neutral": "nt",
}
_SURFACE_FULL = {"disc": "discovery_ranking", "ret": "retrieval_ranking"}


# ── Constructed-confuser content templates (grade-free; intent only) ──
# These produce candidates with high lexical overlap (lexical traps) or high
# semantic similarity (near-duplicates) to the query/anchor. They are
# CONSTRUCTION artifacts carrying mining_role intent; their actual relevance
# is determined later by adjudication.

_CONFUSER_TEMPLATES = {
    "machine_learning": {
        "lexical_trap": (
            "Optimizing {kw} for Parallel Computing Workloads",
            "We apply {kw}-based scheduling to improve parallel computing throughput and resource utilization.",
        ),
        "hard_negative": (
            "A Survey of {kw} in Unrelated Engineering Contexts",
            "This review covers {kw} terminology as it appears across unrelated engineering domains without substantive connection.",
        ),
    },
    "biomedical": {
        "lexical_trap": (
            "{kw} Signaling in a Different Biological Pathway",
            "We study {kw} in an unrelated pathway context, sharing nomenclature but not the queried mechanism.",
        ),
        "hard_negative": (
            "{kw} Mentioned in a Clinical Context Unrelated to the Query",
            "An incidental mention of {kw} in a clinical note about a different condition; no substantive relevance.",
        ),
    },
    "nlp": {
        "lexical_trap": (
            "{kw} for a Different Language Task",
            "We repurpose {kw} for an unrelated language processing objective sharing surface terminology.",
        ),
        "hard_negative": (
            "Passing Reference to {kw} in an Unrelated NLP Survey",
            "A brief, non-substantive mention of {kw} in a survey of unrelated language topics.",
        ),
    },
}


def _extract_keywords(query: str, n: int = 2) -> str:
    """Pull the most salient term(s) from a query for confuser construction."""
    stop = {"for", "the", "a", "an", "of", "in", "on", "with", "and", "to", "via", "using", "based"}
    words = [w for w in query.replace(":", "").split() if w.lower() not in stop]
    return " ".join(words[:n]) if words else query[:20]


# Synonym/rewording substitutions for near-duplicate paraphrasing. Applied
# deterministically to produce a distinct-text, same-meaning paraphrase so the
# semantic-mining cosine is high (>=0.92) while content_hash differs.
_REWORD = [
    ("we propose", "we introduce"),
    ("we present", "we describe"),
    ("we study", "we investigate"),
    ("we show", "we demonstrate"),
    ("we develop", "we build"),
    ("a novel", "a new"),
    ("novel", "new"),
    ("method", "approach"),
    ("approach", "method"),
    ("efficient", "effective"),
    ("achieve", "obtain"),
    ("results", "findings"),
    ("show that", "demonstrate that"),
    ("propose", "introduce"),
    ("model", "framework"),
    ("framework", "model"),
    ("algorithm", "procedure"),
    ("predict", "estimate"),
    ("accurate", "precise"),
    ("high", "strong"),
    ("improve", "enhance"),
    ("training", "learning"),
    ("network", "architecture"),
    ("analysis", "study"),
    ("comprehensive", "extensive"),
    ("state-of-the-art", "leading"),
    ("outperforms", "surpasses"),
    ("significantly", "substantially"),
]


def _paraphrase(title: str, abstract: str) -> tuple[str, str]:
    """Produce a near-identical-meaning paraphrase (distinct text, high cosine).

    Mirrors how the v2 reference near-duplicates were constructed: keep the
    anchor text almost intact and apply only minimal surface variation (a
    light prefix + at most one conservative synonym swap) so the semantic
    content is preserved (cosine in the v2 reference band ~0.86-0.94) while
    the content_hash differs. Heavy rewording drops cosine below the band.
    """
    # Title: prepend a light restatement prefix; keep the title intact otherwise.
    new_title = f"A Restatement: {title}"
    # Abstract: prepend "In brief, " and keep the rest verbatim. This preserves
    # nearly all content words (high cosine) while changing the text (distinct hash).
    new_abstract = f"In brief, {abstract}"
    return new_title, new_abstract


def _match_case(original: str, replacement: str) -> str:
    """Match the capitalization pattern of `original` onto `replacement`."""
    if original and original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _build_v2_extended_case(v2_case) -> V3CandidateCase:
    """Extend one v2 case: preserve v2 candidates verbatim + inject constructed confusers."""
    domain = v2_case.research_domain
    kw = _extract_keywords(v2_case.query_text)
    v3_case_id = f"v3_{v2_case.case_id}"
    cands = []
    # preserve v2 candidates verbatim (content_unchanged proven by hash)
    for cc in v2_case.candidates:
        cands.append(v3_candidate(
            candidate_id=f"v3_{cc.candidate_id}",
            title=cc.title,
            abstract=cc.abstract,
            source_rank=cc.source_rank,
            near_duplicate_of=(f"v3_{cc.near_duplicate_of}" if cc.near_duplicate_of else None),
            mining_role="v2_preserved",
            parent_v2_candidate_id=cc.candidate_id,
            content_unchanged_from_parent=True,
        ))
    # the anchor is the first v2-preserved candidate (construction-only; no grade)
    anchor_id = cands[0].candidate_id
    anchor = cands[0]
    # inject a constructed near-duplicate of the anchor: a PARAPHRASE of the
    # anchor's title+abstract (same finding, reworded) so semantic similarity
    # is high (validated_constructed_near_duplicate requires cosine >= 0.92).
    nd_title, nd_abs = _paraphrase(anchor.title, anchor.abstract)
    cands.append(v3_candidate(
        candidate_id=f"{v3_case_id}_nd1",
        title=nd_title,
        abstract=nd_abs,
        mining_role="constructed_near_duplicate",
        near_duplicate_of=anchor_id,
    ))
    # inject a constructed lexical trap (high lexical overlap intended)
    lt_title, lt_abs = _CONFUSER_TEMPLATES[domain]["lexical_trap"]
    lt_title = lt_title.format(kw=kw)
    lt_abs = lt_abs.format(kw=kw)
    cands.append(v3_candidate(
        candidate_id=f"{v3_case_id}_lt1",
        title=lt_title,
        abstract=lt_abs,
        mining_role="constructed_lexical_trap",
    ))
    # inject a constructed hard-negative (intended nonrelevant confuser)
    hn_title, hn_abs = _CONFUSER_TEMPLATES[domain]["hard_negative"]
    hn_title = hn_title.format(kw=kw)
    hn_abs = hn_abs.format(kw=kw)
    cands.append(v3_candidate(
        candidate_id=f"{v3_case_id}_hn1",
        title=hn_title,
        abstract=hn_abs,
        mining_role="constructed_hard_negative",
    ))
    return v3_case(
        case_id=v3_case_id,
        domain=domain,
        surface=v2_case.ranking_surface,
        intent=v2_case.ranking_intent,
        query=v2_case.query_text,
        candidates=tuple(cands),
        split=v2_case.split,
        primary_slice=v2_case.primary_slice,
        secondary_slices=v2_case.secondary_slices,
        parent_v2_case_id=v2_case.case_id,
        lineage_type="v2_extended",
        query_generation_anchor_candidate_id=anchor_id,
    )


# ── Fully-new case authoring (fresh query + candidate set per slice) ──
# Each fully-new case gets a domain-appropriate query and 6 candidates:
#   2 relevant-seed (anchors), 1 constructed near-dup, 1 lexical trap,
#   1 hard negative, 1 additional context candidate.

_NEW_CASE_CONTENT: dict[str, dict[str, dict[str, tuple[str, tuple[tuple[str, str], ...]]]]] = {
    # slice -> domain -> (query, ((title, abstract), ...))
    "lexical_trap": {
        "machine_learning": (
            "contrastive learning for visual representation",
            (
                ("SimCLR: A Simple Framework for Contrastive Learning", "We learn visual representations by maximizing agreement between augmented views."),
                ("MoCo: Momentum Contrast for Unsupervised Representation Learning", "A dynamic dictionary with a momentum encoder for contrastive learning."),
                ("Contrastive Learning for Audio Representation", "We adapt contrastive objectives to the audio modality, sharing the framework name."),  # lexical trap
                ("A Survey of Self-Supervised Representation Learning", "We review self-supervised methods including contrastive and masked objectives."),
                ("Hardware-Efficient Contrastive Computations", "Optimizing contrastive loss computation on accelerators without representation goals."),  # hard neg
                ("Bootstrap Your Own Latent (BYOL)", "A self-supervised approach that does not require negative samples."),
            ),
        ),
        "biomedical": (
            "CRISPR Cas9 gene editing efficiency",
            (
                ("High-Efficiency CRISPR-Cas9 Genome Editing in Human Cells", "We achieve high knock-in efficiency via optimized Cas9 delivery."),
                ("Optimized Cas9 Guide RNA Design for Efficient Editing", "A guide-RNA selection framework that improves editing efficiency."),
                ("Cas9-Mediated Detection of Pathogens (DETECTR)", "Using Cas9 collateral cleavage for pathogen detection, not gene editing."),  # lexical trap
                ("A Review of CRISPR Gene-Editing Technologies", "A comprehensive review of CRISPR-based editing systems."),
                ("Cas9 Structural Biology Unrelated to Editing Outcomes", "Crystal structures of Cas9 without functional editing analysis."),  # hard neg
                ("Prime Editing: Search-and-Replace Genome Editing", "An alternative editor that writes new genetic information."),
            ),
        ),
        "nlp": (
            "attention mechanisms in transformers",
            (
                ("Attention Is All You Need", "We propose the Transformer, relying entirely on attention mechanisms."),
                ("Self-Attention with Relative Position Representations", "Enhancing Transformer attention with relative position encoding."),
                ("Paying Attention to User Engagement Metrics", "An HCI study on user attention unrelated to neural attention."),  # lexical trap
                ("A Survey of Efficient Transformer Architectures", "We survey efficient variants of the Transformer."),
                ("Attention Scores in Cognitive Load Modeling", "Using attention as a cognitive metric, not a sequence model."),  # hard neg
                ("Longformer: The Long-Document Transformer", "An attention pattern combining local and global attention."),
            ),
        ),
    },
    "semantic_paraphrase": {
        "biomedical": (
            "drug repurposing for rare diseases",
            (
                ("Computational Drug Repurposing for Rare Disorders", "Network-based prediction of existing drugs for rare diseases."),
                ("Systematic Identification of Off-Label Therapies for Orphan Diseases", "A pipeline finding new uses for approved drugs in rare conditions."),  # paraphrase
                ("A Review of Drug Repurposing Methodology", "Surveying computational and experimental repurposing approaches."),
                ("De Novo Drug Design for Common Diseases", "Designing new molecules; not a repurposing approach."),  # hard neg
                ("Clinical Trial Design for Rare Diseases", "Methodology for rare-disease trials, not drug identification."),
                ("Knowledge-Graph-Based Drug Repositioning", "Graph embeddings to predict drug-disease associations."),
            ),
        ),
        "nlp": (
            "prompt tuning for large language models",
            (
                ("The Power of Scale for Parameter-Efficient Prompt Tuning", "Tuning continuous prompts that outperform full fine-tuning."),
                ("Soft Prompts for Efficient LLM Adaptation", "Learning task-specific prompts without updating model weights."),  # paraphrase
                ("A Survey of Parameter-Efficient Fine-Tuning", "Reviewing adapters, LoRA, and prompt-based methods."),
                ("Hard-Coded Rule Systems for Text Processing", "Non-neural rule-based NLP, unrelated to prompt tuning."),  # hard neg
                ("Chain-of-Thought Prompting for Reasoning", "Prompting strategies that elicit reasoning."),
                ("Prefix-Tuning: Optimizing Continuous Prompts", "A predecessor method learning task prefixes."),
            ),
        ),
    },
    "method_vs_application": {
        "machine_learning": (
            "graph neural network methods for molecular property prediction",
            (
                ("Message Passing Neural Networks for Molecular Graphs", "A GNN method for predicting molecular properties."),
                ("Chemprop: Directed Message Passing for Molecular Property Prediction", "A GNN applied to molecular property tasks."),
                ("A Survey of Graph Neural Network Architectures", "Reviewing GNN methods broadly."),
                ("Graph Neural Networks for Social Network Analysis", "Applying GNNs to social graphs, not molecules."),  # hard neg (wrong domain application)
                ("Equivariant Graph Neural Networks for 3D Molecules", "A method handling 3D molecular symmetries."),
                ("Traditional Fingerprints for Molecular Property Prediction", "Non-GNN baselines for the same task."),
            ),
        ),
        "nlp": (
            "retrieval-augmented generation methods",
            (
                ("Retrieval-Augmented Generation for Knowledge-Intensive NLP", "The foundational RAG method."),
                ("Active Retrieval Augmented Generation", "An adaptive variant deciding when to retrieve."),
                ("A Survey of Retrieval-Augmented Language Models", "Reviewing retrieval-augmentation methods."),
                ("Dense Passage Retrieval for Open-Domain QA", "A retrieval component, not a generation method."),  # hard neg (method vs component)
                ("Self-RAG: Learning to Retrieve for Generation", "A method training the model to retrieve."),
                ("Generative QA Without Retrieval", "Closed-book generation, contrasting RAG."),  # hard neg
            ),
        ),
    },
    "review_vs_primary": {
        "machine_learning": (
            "empirical comparisons of optimizer performance",
            (
                ("An Empirical Study of Deep Learning Optimizers", "A primary empirical comparison of Adam, SGD, and others."),
                ("Decoupled Weight Decay Regularization (AdamW)", "A primary study introducing AdamW."),
                ("A Survey of Optimization Methods for Deep Learning", "A review synthesizing prior optimizer studies."),
                ("A Position Paper on Optimizer Selection", "An opinion piece, not empirical evidence."),  # hard neg
                ("Large-Batch Training of Deep Networks", "A primary empirical study on batch size and optimizers."),
                ("Optimizer Benchmarks: A Living Review", "A continuously updated review of optimizer benchmarks."),
            ),
        ),
        "biomedical": (
            "randomized controlled trials of a new anticoagulant",
            (
                ("A Phase III RCT of Novel Anticoagulant Efficacy", "A primary randomized controlled trial."),
                ("Safety Outcomes from a Multicenter Anticoagulant Trial", "Primary trial safety analysis."),
                ("A Systematic Review of New Oral Anticoagulants", "A review synthesizing multiple trials."),
                ("Mechanism of Action of Anticoagulant Drugs", "A mechanistic study, not a trial."),  # hard neg
                ("Meta-Analysis of Anticoagulant Bleeding Risk", "A synthesis of trial results."),
                ("Cohort Study of Long-Term Anticoagulant Use", "Observational, not randomized."),
            ),
        ),
    },
    "missing_abstract": {
        "biomedical": (
            "biomarkers for early cancer detection",
            (
                ("Circulating Tumor DNA for Early Cancer Detection", "We validate ctDNA as an early-detection biomarker."),
                ("Multi-Analyte Blood Test for Cancer Screening", "A combined biomarker panel for early detection."),
                ("Proteomic Biomarkers in Early Oncology", ""),  # missing abstract
                ("A Review of Early Cancer Detection Biomarkers", "Surveying candidate biomarkers."),
                ("Late-Stage Cancer Treatment Biomarkers", "Biomarkers for treatment response, not detection."),  # hard neg
                ("Liquid Biopsy Methodology", "A methods paper on liquid biopsy techniques."),
            ),
        ),
        "nlp": (
            "evaluation metrics for summarization",
            (
                ("ROUGE: A Package for Automatic Summarization Evaluation", "We introduce ROUGE for summarization evaluation."),
                ("BERTScore: Evaluating Text Generation with BERT", "A semantic evaluation metric for generation."),
                ("A Neural Summarization Model", ""),  # missing abstract
                ("A Survey of Summarization Evaluation", "Reviewing automatic and human evaluation."),
                ("Machine Translation Evaluation Metrics", "MT-specific metrics, not summarization."),  # hard neg
                ("Human Evaluation Protocols for Summarization", "Methodology for human judgment studies."),
            ),
        ),
    },
    "near_duplicate": {
        "machine_learning": (
            "vision transformer architectures",
            (
                ("An Image Is Worth 16x16 Words: Transformers for Image Recognition", "The foundational ViT paper."),
                ("ViT: Transformers for Image Recognition at Scale", "Scaling ViT to large datasets."),  # near-dup
                ("DeiT: Training Data-Efficient Image Transformers", "A distillation-based efficient ViT."),
                ("Convolutional Networks for Image Recognition", "CNN baselines, contrasting ViT."),  # hard neg
                ("A Survey of Vision Transformers", "Reviewing ViT variants."),
                ("Swin Transformer for Dense Prediction", "A hierarchical ViT for dense tasks."),
            ),
        ),
        "biomedical": (
            "single-cell RNA sequencing analysis",
            (
                ("Seurat: Integrated Analysis of Single-Cell Data", "A toolkit for scRNA-seq analysis."),
                ("Comprehensive Single-Cell Analysis with Seurat", "An application of Seurat to a large atlas."),  # near-dup
                ("Scanpy: Large-Scale Single-Cell Analysis", "An alternative Python toolkit."),
                ("Bulk RNA Sequencing Pipelines", "Bulk, not single-cell, methods."),  # hard neg
                ("A Review of Single-Cell Computational Methods", "Surveying scRNA-seq analysis tools."),
                ("Trajectory Inference for Single-Cell Data", "A specific scRNA-seq analysis task."),
            ),
        ),
    },
    "source_rank_conflict": {
        "nlp": (
            "named entity recognition systems",
            (
                ("BERT for Named Entity Recognition", "A strong NER system using BERT."),
                ("A High-Accuracy NER System for Biomedical Text", "A domain-specific NER system."),
                ("A Survey of Named Entity Recognition", "A review of NER methods."),
                ("Rule-Based Information Extraction", "A non-neural baseline for entity extraction."),  # hard neg
                ("A Preprint NER Benchmark", "A benchmark with lower source priority."),
                ("Multilingual NER with Cross-Lingual Transfer", "A multilingual NER approach."),
            ),
        ),
        "machine_learning": (
            "federated learning algorithms",
            (
                ("Communication-Efficient Learning of Deep Networks (FedAvg)", "The foundational federated learning algorithm."),
                ("Federated Optimization for Heterogeneous Networks", "An improved federated optimizer."),
                ("A Survey of Federated Learning", "Reviewing federated methods."),
                ("Centralized Training of Distributed Data", "Non-federated centralized training."),  # hard neg
                ("A Workshop Paper on Federated Systems", "A lower-priority workshop contribution."),
                ("Privacy-Preserving Distributed Learning", "A related privacy-focused method."),
            ),
        ),
    },
    "acronym_vs_expanded": {
        "biomedical": (
            "MAP kinase signaling pathway",
            (
                ("The MAPK/ERK Signaling Cascade", "A primary study of the MAP kinase pathway."),
                ("Mitogen-Activated Protein Kinase in Cell Proliferation", "The expanded form, same pathway."),
                ("MAP: Mean Arterial Pressure in Hemodynamics", "A different expansion of the MAP acronym."),  # acronym collision
                ("A Review of Kinase Signaling Pathways", "A review of kinase cascades."),
                ("Microbial Antigen Presentation", "Unrelated immunology sharing the MAP prefix."),  # hard neg
                ("JNK and p38 MAP Kinase Families", "Related branches of MAPK signaling."),
            ),
        ),
        "nlp": (
            "POS tagging with neural networks",
            (
                ("Neural Part-of-Speech Tagging", "A neural POS tagger."),
                ("BiLSTM-Based POS Tagging", "A specific neural POS architecture."),
                ("POS Systems in Retail Commerce", "Point-of-sale systems, unrelated to NLP."),  # acronym collision
                ("A Survey of Sequence Labeling", "Reviewing tagging and labeling methods."),
                ("Point-of-Sale Integration Patterns", "Software patterns for retail systems."),  # hard neg
                ("Character-Level POS Tagging for Morphologically Rich Languages", "A specialized POS tagger."),
            ),
        ),
    },
    "negated_findings": {
        "machine_learning": (
            "does data augmentation improve robustness",
            (
                ("Data Augmentation Does Not Improve Robustness to Distribution Shift", "A primary study reporting a negative result."),
                ("A Study Finding No Benefit from Heavy Augmentation", "Another negative-finding primary study."),
                ("A Survey of Data Augmentation Methods", "A review of augmentation techniques."),
                ("Data Augmentation Dramatically Improves Accuracy", "A conflicting positive result on a different axis."),  # hard neg (opposing finding)
                ("Why Data Augmentation Sometimes Fails", "An analysis of augmentation failures."),
                ("Empirical Augmentation Benchmarks", "Benchmarks of augmentation effects."),
            ),
        ),
        "biomedical": (
            "efficacy of a novel statin in elderly patients",
            (
                ("No Significant Benefit of Novel Statin in Elderly Patients", "A primary trial reporting a negative result."),
                ("A Trial Finding No Efficacy Advantage for the New Statin", "Another negative-finding trial."),
                ("A Review of Statin Efficacy Across Age Groups", "A review synthesizing statin trials."),
                ("Strong Efficacy of the Statin in Young Cohorts", "A positive result in a different population."),  # hard neg
                ("Safety Profile of the Novel Statin", "A safety-focused analysis, not efficacy."),
                ("Meta-Analysis of Statin Efficacy", "A synthesis of multiple statin trials."),
            ),
        ),
    },
    "exact_identifier": {
        "nlp": (
            "BERT",
            (
                ("BERT: Pre-training of Deep Bidirectional Transformers", "The canonical BERT paper."),
                ("Understanding BERT Pre-training for Language", "A follow-up analyzing BERT."),
                ("ALBERT: A Lite BERT", "A parameter-efficient BERT variant."),
                ("ELMo: Embeddings from Language Models", "A different model sharing the era."),  # hard neg
                ("A Survey of Pre-trained Language Models", "A review including BERT."),
                ("DistilBERT: A Distilled Version of BERT", "A compressed BERT variant."),
            ),
        ),
        "machine_learning": (
            "ResNet",
            (
                ("Deep Residual Learning for Image Recognition (ResNet)", "The canonical ResNet paper."),
                ("ResNet-V2: Identity Mappings in Deep Networks", "A follow-up ResNet architecture."),
                ("Wide Residual Networks", "A wider variant of ResNet."),
                ("VGG: Very Deep Convolutional Networks", "A contemporary non-ResNet architecture."),  # hard neg
                ("A Survey of Residual Networks", "A review of ResNet variants."),
                ("ResNeXt: Aggregated Residual Transformations", "An expanded ResNet variant."),
            ),
        ),
    },
    "neutral": {
        "biomedical": (
            "general review of immunotherapy approaches",
            (
                ("A Comprehensive Review of Cancer Immunotherapy", "A broad review of immunotherapy."),
                ("Recent Advances in Immune Checkpoint Inhibitors", "A focused review of a subfield."),
                ("Mechanisms of T-Cell Activation", "A mechanistic study relevant to immunotherapy."),
                ("A Historical Account of Vaccine Development", "Vaccine history, adjacent but distinct."),  # hard neg
                ("CAR-T Cell Therapy: A Review", "A review of a specific immunotherapy modality."),
                ("Biomarkers for Immunotherapy Response", "A review of response-prediction biomarkers."),
            ),
        ),
    },
}


# Additional content for (slice, domain) combinations needed by the balanced
# allocation but not in _NEW_CASE_CONTENT above. Same 6-candidate pattern.
_NEW_CASE_CONTENT_EXTRA: dict[str, dict[str, tuple[str, tuple[tuple[str, str], ...]]]] = {
    "semantic_paraphrase": {
        "machine_learning": (
            "transfer learning across visual domains",
            (
                ("Domain Adaptation for Visual Recognition", "Transferring learned features across visual domains."),
                ("Transferring Representations Across Image Domains", "Adapting pre-trained vision features to new domains."),  # paraphrase
                ("A Survey of Transfer Learning", "Reviewing cross-domain transfer methods."),
                ("Reinforcement Learning for Game Playing", "RL in games, unrelated to visual transfer."),  # hard neg
                ("Self-Supervised Pretraining for Vision", "Pretraining objectives for visual representations."),
                ("Adversarial Domain Adaptation", "A method aligning source and target distributions."),
            ),
        ),
    },
    "method_vs_application": {
        "biomedical": (
            "deep learning methods for medical image segmentation",
            (
                ("U-Net: Convolutional Networks for Biomedical Image Segmentation", "A CNN method for medical image segmentation."),
                ("nnU-Net: A Self-Configuring Method for Medical Segmentation", "An adaptive method for medical image segmentation."),
                ("A Survey of Medical Image Analysis", "Reviewing deep learning for medical imaging."),
                ("Statistical Atlases for Brain Mapping", "Non-learning atlas-based segmentation."),  # hard neg
                ("V-Net: Fully Convolutional 3D Medical Segmentation", "A 3D method for volumetric medical images."),
                ("Deep Learning for Radiology Report Generation", "A different medical-AI task, not segmentation."),  # hard neg
            ),
        ),
    },
    "review_vs_primary": {
        "nlp": (
            "empirical studies of in-context learning",
            (
                ("An Empirical Study of In-Context Learning", "A primary empirical study of LLM in-context learning."),
                ("What Makes In-Context Learning Work? An Empirical Investigation", "A primary study probing ICL mechanisms."),
                ("A Survey of Prompting and In-Context Learning", "A review of ICL methods."),
                ("Theoretical Analyses of Transformer Expressivity", "Theory, not empirical ICL evidence."),  # hard neg
                ("Scaling Laws for In-Context Learning", "A primary empirical scaling study."),
                ("A Position Paper on LLM Capabilities", "An opinion piece, not empirical."),  # hard neg
            ),
        ),
    },
    "missing_abstract": {
        "machine_learning": (
            "normalization techniques in deep learning",
            (
                ("Batch Normalization: Accelerating Deep Network Training", "We introduce batch normalization for stable training."),
                ("Layer Normalization for Transformer Architectures", "A normalization method for transformers."),
                ("Group Normalization for Vision Models", ""),  # missing abstract
                ("A Survey of Normalization Methods", "Reviewing normalization in deep learning."),
                ("Initialization Strategies for Neural Networks", "Weight initialization, not normalization."),  # hard neg
                ("Instance Normalization for Style Transfer", "A normalization variant for style tasks."),
            ),
        ),
    },
    "near_duplicate": {
        "nlp": (
            "pre-trained language model fine-tuning",
            (
                ("Universal Language Model Fine-tuning (ULMFiT)", "A fine-tuning method for language models."),
                ("Fine-tuning Pre-trained Language Models with ULMFiT", "An application of the ULMFiT method."),  # near-dup
                ("Adapters for Parameter-Efficient Fine-tuning", "An alternative fine-tuning approach."),
                ("Training Language Models from Scratch", "Pretraining-only, not fine-tuning."),  # hard neg
                ("A Survey of Fine-tuning Methods", "Reviewing PLM adaptation techniques."),
                ("Prompt Tuning for Language Models", "A prompt-based adaptation method."),
            ),
        ),
    },
    "source_rank_conflict": {
        "biomedical": (
            "protein language models",
            (
                ("ESM: Evolutionary-Scale Protein Language Models", "A protein LM from a high-priority source."),
                ("ProtTrans: Modeling Protein Sequences with Transformers", "A protein LM with strong empirical results."),
                ("A Survey of Protein Language Models", "Reviewing protein LMs."),
                ("DNA Language Models for Genomics", "DNA, not protein, language models."),  # hard neg
                ("A Preprint on Protein Embeddings", "A lower-priority preprint contribution."),
                ("MSA Transformer for Protein Structure", "A related MSA-based protein model."),
            ),
        ),
    },
    "acronym_vs_expanded": {
        "machine_learning": (
            "GAN generative adversarial networks",
            (
                ("Generative Adversarial Networks (GANs)", "The foundational GAN paper."),
                ("GANs for Image Generation", "An application of GANs to image synthesis."),
                ("GAN: Global Area Network Routing", "A networking paper sharing the GAN acronym."),  # acronym collision
                ("A Survey of Generative Models", "Reviewing GANs, VAEs, and diffusion models."),
                ("Gradient Augmented Newton Methods", "An optimizer sharing the GAN acronym."),  # hard neg
                ("StyleGAN: High-Quality Image Synthesis", "A high-profile GAN variant."),
            ),
        ),
    },
    "negated_findings": {
        "nlp": (
            "does chain-of-thought help on arithmetic",
            (
                ("Chain-of-Thought Does Not Improve Arithmetic in Small Models", "A primary study reporting a negative result."),
                ("A Study Finding No CoT Benefit for Simple Arithmetic", "Another negative-finding primary study."),
                ("A Survey of Chain-of-Thought Prompting", "A review of CoT methods."),
                ("Chain-of-Thought Dramatically Improves Math Reasoning", "A conflicting positive result on larger models."),  # hard neg
                ("Why CoT Fails on Certain Tasks", "An analysis of CoT failures."),
                ("Empirical CoT Benchmarks", "Benchmarks of CoT effects."),
            ),
        ),
    },
    "exact_identifier": {
        "biomedical": (
            "AlphaFold",
            (
                ("AlphaFold: Highly Accurate Protein Structure Prediction", "The canonical AlphaFold paper."),
                ("AlphaFold-Multimer for Complex Prediction", "A follow-up extending AlphaFold."),
                ("RoseTTAFold: Accurate Protein Structure Prediction", "A competing structure predictor."),
                ("ESMFold: Fast Structure Prediction", "A different structure predictor."),  # hard neg
                ("A Survey of Protein Structure Prediction", "A review including AlphaFold."),
                ("AlphaFold Database: Scaling to the Proteome", "A resource built on AlphaFold."),
            ),
        ),
    },
    "neutral": {
        "machine_learning": (
            "general review of reinforcement learning",
            (
                ("A Comprehensive Survey of Reinforcement Learning", "A broad review of RL."),
                ("Recent Advances in Deep Reinforcement Learning", "A focused review of deep RL."),
                ("Markov Decision Processes: A Primer", "A foundational RL formalism study."),
                ("Supervised Learning for Classification", "Supervised learning, not RL."),  # hard neg
                ("Offline Reinforcement Learning: A Review", "A review of a specific RL subfield."),
                ("Multi-Agent Reinforcement Learning", "A review of MARL."),
            ),
        ),
        "nlp": (
            "general review of word embeddings",
            (
                ("A Survey of Word Embedding Methods", "A broad review of word embeddings."),
                ("Recent Advances in Contextual Embeddings", "A focused review of contextual vectors."),
                ("Distributional Semantics: Foundational Analyses", "A foundational study relevant to embeddings."),
                ("Image Embeddings for Vision", "Vision embeddings, not word embeddings."),  # hard neg
                ("A Review of Sentence Embeddings", "A review of sentence-level representations."),
                ("Static vs Contextual Embeddings: A Review", "A comparative review."),
            ),
        ),
    },
}


def _resolved_content(slice_type: str, domain: str):
    """Look up case content, merging the extra table into the primary table."""
    if domain in _NEW_CASE_CONTENT.get(slice_type, {}):
        return _NEW_CASE_CONTENT[slice_type][domain]
    if domain in _NEW_CASE_CONTENT_EXTRA.get(slice_type, {}):
        return _NEW_CASE_CONTENT_EXTRA[slice_type][domain]
    raise KeyError(f"no content for slice={slice_type!r} domain={domain!r}")


def _build_fully_new_case(surface_abbr: str, slice_type: str, domain: str, split: str) -> V3CandidateCase:
    """Author one fully-new case from the content table."""
    content = _resolved_content(slice_type, domain)
    query, cand_texts = content
    case_id = f"v3_{surface_abbr}_{_SLICE_ABBR[slice_type]}_001"
    # ensure unique IDs even if the (surface,slice) repeats by appending domain abbr
    dom_abbr = {"machine_learning": "ml", "biomedical": "bio", "nlp": "nlp"}[domain]
    case_id = f"v3_{surface_abbr}_{_SLICE_ABBR[slice_type]}_{dom_abbr}"
    cands = []
    for i, (title, abstract) in enumerate(cand_texts):
        cid = f"{case_id}_{chr(97 + i)}"  # a, b, c, ...
        role = None
        nd_of = None
        if i == 0:
            role = "fully_new_relevant_seed"
        elif slice_type == "near_duplicate" and i == 1:
            role = "constructed_near_duplicate"
            nd_of = cands[0].candidate_id
        elif slice_type == "lexical_trap" and i == 2:
            role = "constructed_lexical_trap"
        cands.append(v3_candidate(
            candidate_id=cid, title=title, abstract=abstract,
            mining_role=role, near_duplicate_of=nd_of,
        ))
    anchor_id = cands[0].candidate_id
    return v3_case(
        case_id=case_id,
        domain=domain,
        surface=_SURFACE_FULL[surface_abbr],
        intent="general_research_relevance",
        query=query,
        candidates=tuple(cands),
        split=split,
        primary_slice=slice_type,
        lineage_type="fully_new",
        query_generation_anchor_candidate_id=anchor_id,
    )


def build_v3_corpus():
    """Build the full 88-case v3 candidate corpus."""
    # parent allowlist (frozen)
    import json
    audit = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json").read_text(encoding="utf-8"))
    parent_ids = sorted(audit["audited_case_ids"])
    v2_cases = {c.case_id: c for c in frozen_v2_cases() if c.case_id in set(parent_ids)}

    cases: list[V3CandidateCase] = []
    # 44 v2-lineage extended (in parent-allowlist order = canonical case order for lineage)
    for pid in parent_ids:
        cases.append(_build_v2_extended_case(v2_cases[pid]))
    # 44 fully-new (in allocation-table order = canonical case order for new cases)
    for (surf, slc, dom, split) in _FULLY_NEW_ALLOCATION:
        cases.append(_build_fully_new_case(surf, slc, dom, split))
    return tuple(cases)
