"""P1B.1: Retrieval ranking benchmark v2 cases.

33 retrieval cases = 11 slice types × 3 domains. Mirrors the discovery
benchmark structure but uses shorter, keyword-style queries characteristic
of the retrieval ranking surface (TwoStageRetriever path).

See benchmark_v2_discovery_cases.py module docstring for split policy and
benchmark_v2_schema.py for the slice vocabulary.
"""

from __future__ import annotations

from backend.ranking.benchmark_v2_builders import candidate, case, provenance
from backend.ranking.benchmark_v2_schema import (
    SLICE_ACRONYM_VS_EXPANDED,
    SLICE_EXACT_IDENTIFIER,
    SLICE_LEXICAL_TRAP,
    SLICE_METHOD_VS_APPLICATION,
    SLICE_MISSING_ABSTRACT,
    SLICE_NEAR_DUPLICATE,
    SLICE_NEGATED_FINDINGS,
    SLICE_NEUTRAL,
    SLICE_REVIEW_VS_PRIMARY,
    SLICE_SEMANTIC_PARAPHRASE,
    SLICE_SOURCE_RANK_CONFLICT,
)

# Deterministic split rotation; rotated differently from discovery so the
# two surfaces are not split-aligned slice-by-slice.
_SPLITS_BY_SLICE_DOMAIN = {
    SLICE_LEXICAL_TRAP: ("held_out", "calibration", "development"),
    SLICE_SEMANTIC_PARAPHRASE: ("calibration", "development", "held_out"),
    SLICE_METHOD_VS_APPLICATION: ("development", "held_out", "calibration"),
    SLICE_REVIEW_VS_PRIMARY: ("held_out", "development", "calibration"),
    SLICE_MISSING_ABSTRACT: ("calibration", "held_out", "development"),
    SLICE_NEAR_DUPLICATE: ("development", "calibration", "held_out"),
    SLICE_SOURCE_RANK_CONFLICT: ("held_out", "calibration", "development"),
    SLICE_ACRONYM_VS_EXPANDED: ("calibration", "development", "held_out"),
    SLICE_NEGATED_FINDINGS: ("development", "held_out", "calibration"),
    SLICE_EXACT_IDENTIFIER: ("held_out", "development", "calibration"),
    SLICE_NEUTRAL: ("calibration", "held_out", "development"),
}

_DOMAIN_ORDER = ("machine_learning", "biomedical", "nlp")


def _split_for(slice_type: str, domain: str) -> str:
    idx = _DOMAIN_ORDER.index(domain)
    return _SPLITS_BY_SLICE_DOMAIN[slice_type][idx]


# ════════════════════════════════════════════════════════════════════
# Slice: lexical_trap
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_LEXICAL_TRAP = [
    case(
        case_id="ml_ret_lt_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="attention mechanism long context",
        candidates=(
            candidate("mlr_lt_001_a", "Longformer: Long-Document Transformer",
             "Sparse local+global attention handles 4k+ token documents."),
            candidate("mlr_lt_001_b", "FlashAttention: Fast and Memory-Efficient Exact Attention",
             "IO-aware exact attention computes long-context attention faster."),
            candidate("mlr_lt_001_c", "Attention in Classroom Discourse Analysis",
             "Linguistic study of teacher attention in long classroom recordings."),  # trap
            candidate("mlr_lt_001_d", "Long-Context Transformers: A Survey",
             "Survey of methods extending Transformer context length."),
        ),
        judgments={
            "mlr_lt_001_a": provenance(3, rationale="directly long-context attention"),
            "mlr_lt_001_b": provenance(3, rationale="efficient long-context attention"),
            "mlr_lt_001_c": provenance(0, rationale="classroom discourse, not ML attention"),
            "mlr_lt_001_d": provenance(2, rationale="survey of long-context methods"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "machine_learning"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
    case(
        case_id="bio_ret_lt_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="cell cycle regulation tumor",
        candidates=(
            candidate("bior_lt_001_a", "Cyclin-CDK Regulation in Tumor Progression",
             "We review how cyclin-CDK complexes drive tumor cell-cycle entry."),
            candidate("bior_lt_001_b", "p53 and the Cell Cycle Checkpoint",
             "We examine p53-mediated G1/S arrest in tumors."),
            candidate("bior_lt_001_c", "Cell Cycle of Rechargeable Battery Materials",
             "Electrochemical cycling of lithium-ion cell materials."),  # trap
            candidate("bior_lt_001_d", "Targeting CDK4/6 in Breast Cancer",
             "We evaluate CDK4/6 inhibitors in ER+ breast tumors."),
        ),
        judgments={
            "bior_lt_001_a": provenance(3, rationale="directly cell-cycle regulation in tumors"),
            "bior_lt_001_b": provenance(3, rationale="canonical tumor cell-cycle checkpoint"),
            "bior_lt_001_c": provenance(0, rationale="battery cells, not biological cells"),
            "bior_lt_001_d": provenance(3, rationale="cell-cycle therapy in tumors"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "biomedical"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
    case(
        case_id="nlp_ret_lt_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="word embeddings semantic similarity",
        candidates=(
            candidate("nlpr_lt_001_a", "word2vec: Efficient Word Embeddings",
             "We learn dense word vectors capturing semantic similarity."),
            candidate("nlpr_lt_001_b", "GloVe: Global Vectors for Word Representation",
             "We train word embeddings from co-occurrence statistics."),
            candidate("nlpr_lt_001_c", "Embedding Sound in Wooden Frames",
             "Carpentry technique for embedding objects in wooden structures."),  # trap
            candidate("nlpr_lt_001_d", "BERT Embeddings for Semantic Similarity",
             "Contextual BERT vectors outperform static embeddings on similarity."),
        ),
        judgments={
            "nlpr_lt_001_a": provenance(3, rationale="canonical word-embedding semantic-similarity method"),
            "nlpr_lt_001_b": provenance(3, rationale="canonical word-embedding method"),
            "nlpr_lt_001_c": provenance(0, rationale="carpentry, not NLP embeddings"),
            "nlpr_lt_001_d": provenance(3, rationale="contextual embeddings for similarity"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "nlp"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: semantic_paraphrase
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_SEMANTIC_PARAPHRASE = [
    case(
        case_id="ml_ret_sp_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="method_relevance",
        query="speeding up inference on edge devices",
        candidates=(
            candidate("mlr_sp_001_a", "Quantization for Efficient Neural Inference",
             "INT8 quantization reduces model size and latency for edge deployment."),  # paraphrase
            candidate("mlr_sp_001_b", "Knowledge Distillation for Compact Models",
             "We transfer large-model knowledge into small student models."),
            candidate("mlr_sp_001_c", "Pruning Filters for Efficient ConvNets",
             "We remove redundant filters to accelerate inference."),
            candidate("mlr_sp_001_d", "Edge Computing Benchmark Suite",
             "We benchmark inference workloads on edge hardware."),
        ),
        judgments={
            "mlr_sp_001_a": provenance(3, rationale="directly speeds up inference for edge, paraphrased"),
            "mlr_sp_001_b": provenance(3, rationale="distillation produces compact edge-friendly models"),
            "mlr_sp_001_c": provenance(3, rationale="pruning accelerates inference"),
            "mlr_sp_001_d": provenance(2, rationale="benchmark, relevant but evaluative"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "machine_learning"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
    ),
    case(
        case_id="bio_ret_sp_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="non-invasive prenatal testing accuracy",
        candidates=(
            candidate("bior_sp_001_a", "Cell-Free DNA Screening for Fetal Aneuploidy",
             "We evaluate NIPT sensitivity and specificity across large cohorts."),  # paraphrase
            candidate("bior_sp_001_b", "False-Positive Rates in Non-Invasive Prenatal Screening",
             "We characterize sources of false positives in cfDNA NIPT."),
            candidate("bior_sp_001_c", "Genome-Wide NIPT for Subchromosomal Events",
             "We extend NIPT to detect microdeletions and microduplications."),
            candidate("bior_sp_001_d", "Amniocentesis vs NIPT: A Comparative Study",
             "We compare invasive and non-invasive prenatal testing."),
        ),
        judgments={
            "bior_sp_001_a": provenance(3, rationale="directly NIPT accuracy, paraphrased query"),
            "bior_sp_001_b": provenance(3, rationale="directly about NIPT accuracy/false positives"),
            "bior_sp_001_c": provenance(2, rationale="extends NIPT scope, adjacent"),
            "bior_sp_001_d": provenance(2, rationale="comparative, relevant but broader"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "biomedical"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
    ),
    case(
        case_id="nlp_ret_sp_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="detecting harmful content online",
        candidates=(
            candidate("nlpr_sp_001_a", "Toxic Comment Classification with Deep Learning",
             "We train classifiers to detect toxic comments at scale."),  # paraphrase
            candidate("nlpr_sp_001_b", "Hate Speech Detection in Social Media",
             "We address cross-lingual hate-speech detection."),
            candidate("nlpr_sp_001_c", "A Survey of Online Content Moderation",
             "We review automated moderation approaches."),
            candidate("nlpr_sp_001_d", "Detecting Misinformation with Stance Detection",
             "We detect misinformation via stance classification."),
        ),
        judgments={
            "nlpr_sp_001_a": provenance(3, rationale="directly harmful-content detection, paraphrased"),
            "nlpr_sp_001_b": provenance(3, rationale="directly harmful-content detection"),
            "nlpr_sp_001_c": provenance(2, rationale="survey, relevant but broad"),
            "nlpr_sp_001_d": provenance(2, rationale="misinformation detection, adjacent harmful content"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "nlp"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: method_vs_application
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_METHOD_VS_APPLICATION = [
    case(
        case_id="ml_ret_mv_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="method_relevance",
        query="contrastive loss formulation",
        candidates=(
            candidate("mlr_mv_001_a", "SimCLR: A Simple Contrastive Learning Framework",
             "We introduce a contrastive loss based on InfoNCE over augmented views."),  # method
            candidate("mlr_mv_001_b", "Contrastive Representations for Medical Image Retrieval",
             "We use contrastive pre-training for a clinical image retrieval application."),  # application
            candidate("mlr_mv_001_c", "MoCo: Momentum Contrast for Unsupervised Representation",
             "A dynamic-dictionary contrastive loss method."),  # method
            candidate("mlr_mv_001_d", "Evaluating Contrastive Loss Variants",
             "We benchmark InfoNCE, triplet, and sigmoid losses."),
        ),
        judgments={
            "mlr_mv_001_a": provenance(3, rationale="canonical contrastive loss method"),
            "mlr_mv_001_b": provenance(2, rationale="application of contrastive loss"),
            "mlr_mv_001_c": provenance(3, rationale="contrastive loss method"),
            "mlr_mv_001_d": provenance(2, rationale="evaluative study of contrastive losses"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "machine_learning"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
    case(
        case_id="bio_ret_mv_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="method_relevance",
        query="fold-recognition algorithms",
        candidates=(
            candidate("bior_mv_001_a", "HHsearch: Protein Homology Detection by HMM-HMM",
             "We propose an HMM-HMM method sensitive enough for remote fold recognition."),  # method
            candidate("bior_mv_001_b", "Fold-Recognition for Metagenomic Protein Function",
             "We apply fold-recognition to annotate metagenomic sequences."),  # application
            candidate("bior_mv_001_c", "DeepMind AlphaFold for Fold Recognition",
             "We use deep learning embeddings to recognize remote folds."),
            candidate("bior_mv_001_d", "Evaluating Fold-Recognition Servers (CASP)",
             "We benchmark fold-recognition methods in CASP."),
        ),
        judgments={
            "bior_mv_001_a": provenance(3, rationale="direct fold-recognition method"),
            "bior_mv_001_b": provenance(2, rationale="application of fold-recognition"),
            "bior_mv_001_c": provenance(2, rationale="DL-based fold-recognition method"),
            "bior_mv_001_d": provenance(2, rationale="evaluation of methods"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "biomedical"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
    case(
        case_id="nlp_ret_mv_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="method_relevance",
        query="dependency parsing algorithms",
        candidates=(
            candidate("nlpr_mv_001_a", "A Fast and Accurate Dependency Parser using Neural Networks",
             "We propose a neural transition-based dependency parser."),  # method
            candidate("nlpr_mv_001_b", "Dependency Parsing for Low-Resource Languages",
             "We deploy dependency parsing for under-served languages."),  # application
            candidate("nlpr_mv_001_c", "Biaffine Attention for Dependency Parsing",
             "We score arcs with biaffine attention."),  # method
            candidate("nlpr_mv_001_d", "Universal Dependencies: A Cross-Linguistic Benchmark",
             "We release dependency treebanks across many languages."),
        ),
        judgments={
            "nlpr_mv_001_a": provenance(3, rationale="direct dependency parsing method"),
            "nlpr_mv_001_b": provenance(2, rationale="application of dependency parsing"),
            "nlpr_mv_001_c": provenance(3, rationale="parsing method"),
            "nlpr_mv_001_d": provenance(1, rationale="treebank, not a parsing algorithm"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "nlp"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: review_vs_primary
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_REVIEW_VS_PRIMARY = [
    case(
        case_id="ml_ret_rv_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="federated learning communication efficiency results",
        candidates=(
            candidate("mlr_rv_001_a", "Communication-Efficient Federated Learning (FedAvg)",
             "We empirically show reduced communication rounds on image benchmarks."),  # primary
            candidate("mlr_rv_001_b", "Federated Learning: A Survey",
             "We review FL algorithms including communication-efficiency strategies."),  # review
            candidate("mlr_rv_001_c", "FedProx: Heterogeneous Federated Networks",
             "We add a proximal term and report convergence experiments."),  # primary
            candidate("mlr_rv_001_d", "Trends in Distributed Machine Learning",
             "Narrative review of distributed training paradigms."),  # review
        ),
        judgments={
            "mlr_rv_001_a": provenance(3, rationale="primary FL paper with communication-efficiency results"),
            "mlr_rv_001_b": provenance(2, rationale="review, synthesizes rather than reports"),
            "mlr_rv_001_c": provenance(3, rationale="primary FL method with empirical results"),
            "mlr_rv_001_d": provenance(1, rationale="broad narrative review"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "machine_learning"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
    case(
        case_id="bio_ret_rv_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="psilocybin depression clinical trial",
        candidates=(
            candidate("bior_rv_001_a", "Psilocybin Therapy for Treatment-Resistant Depression (JAMA Psychiatry)",
             "Randomized trial shows rapid antidepressant effects of psilocybin."),  # primary
            candidate("bior_rv_001_b", "Psychedelics in Psychiatry: A Narrative Review",
             "We synthesize evidence on psychedelic-assisted therapy."),  # review
            candidate("bior_rv_001_c", "Psilocybin for Cancer-Related Anxiety (J Psychopharmacol)",
             "Double-blind trial reports anxiety reductions."),  # primary
            candidate("bior_rv_001_d", "A Systematic Review of Serotonergic Psychedelics",
             "We aggregate trial-level evidence on serotonergic agents."),  # review
        ),
        judgments={
            "bior_rv_001_a": provenance(3, rationale="primary RCT directly answering the query"),
            "bior_rv_001_b": provenance(2, rationale="narrative review, not primary results"),
            "bior_rv_001_c": provenance(3, rationale="primary psilocybin RCT"),
            "bior_rv_001_d": provenance(2, rationale="systematic review, aggregates"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "biomedical"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
    case(
        case_id="nlp_ret_rv_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="BERT fine-tuning GLUE benchmark results",
        candidates=(
            candidate("nlpr_rv_001_a", "BERT: Pre-training of Deep Bidirectional Transformers",
             "We report GLUE gains from BERT fine-tuning."),  # primary
            candidate("nlpr_rv_001_b", "A Survey of Pre-Trained Language Models",
             "We review PLMs including BERT and successors."),  # review
            candidate("nlpr_rv_001_c", "What Does BERT Look at? (Attention Analysis)",
             "We analyze BERT attention heads empirically."),  # primary
            candidate("nlpr_rv_001_d", "Pre-Training Methods in NLP: A Review",
             "Synthesis of pre-training objectives and benchmarks."),  # review
        ),
        judgments={
            "nlpr_rv_001_a": provenance(3, rationale="primary BERT paper with GLUE results"),
            "nlpr_rv_001_b": provenance(2, rationale="survey mentioning BERT"),
            "nlpr_rv_001_c": provenance(2, rationale="primary but analytical, not GLUE-focused"),
            "nlpr_rv_001_d": provenance(1, rationale="broad pre-training review"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "nlp"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: missing_abstract
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_MISSING_ABSTRACT = [
    case(
        case_id="ml_ret_ma_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="reinforcement learning robotics",
        candidates=(
            candidate("mlr_ma_001_a", "Deep Reinforcement Learning for Robotic Manipulation",
             "We train robotic arms with deep RL for dexterous manipulation."),
            candidate("mlr_ma_001_b", "Sim-to-Real Transfer for Robotic Locomotion",
             ""),  # missing
            candidate("mlr_ma_001_c", "Asymmetric Self-Play for Robotic Skill Acquisition",
             "We use self-play to learn robotic manipulation skills."),
            candidate("mlr_ma_001_d", "Model-Predictive Control for Quadrupedal Robots",
             ""),  # missing
        ),
        judgments={
            "mlr_ma_001_a": provenance(3, rationale="directly RL for robotics"),
            "mlr_ma_001_b": provenance(2, confidence=0.6, rationale="relevant title, abstract missing"),
            "mlr_ma_001_c": provenance(3, rationale="RL/self-play for robotic skills"),
            "mlr_ma_001_d": provenance(2, confidence=0.55, rationale="robotics title, MPC not RL, abstract missing"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "machine_learning"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
    case(
        case_id="bio_ret_ma_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="circulating tumor DNA ctDNA",
        candidates=(
            candidate("bior_ma_001_a", "ctDNA as a Liquid Biopsy for Cancer Monitoring",
             "We use ctDNA to track tumor burden non-invasively."),
            candidate("bior_ma_001_b", "Minimal Residual Disease Detection with ctDNA",
             ""),  # missing
            candidate("bior_ma_001_c", "methylation-based ctDNA for Early Cancer Detection",
             "We detect cancer signals from methylation patterns in cfDNA."),
            candidate("bior_ma_001_d", " ctDNA Sequencing Errors and Corrections",
             ""),  # missing
        ),
        judgments={
            "bior_ma_001_a": provenance(3, rationale="directly ctDNA liquid biopsy"),
            "bior_ma_001_b": provenance(2, confidence=0.6, rationale="ctDNA title, abstract missing"),
            "bior_ma_001_c": provenance(3, rationale="ctDNA early-detection method"),
            "bior_ma_001_d": provenance(2, confidence=0.55, rationale="ctDNA sequencing title, abstract missing"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "biomedical"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
    case(
        case_id="nlp_ret_ma_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="dialogue state tracking",
        candidates=(
            candidate("nlpr_ma_001_a", "Trade: Transferable Dialogue State Generator",
             "We generate dialogue state via copy mechanism."),
            candidate("nlpr_ma_001_b", "Neural Belief Tracking for Multi-Domain Dialogue",
             ""),  # missing
            candidate("nlpr_ma_001_c", "SUMBT: Slot-Usage-Based Dialogue State Tracking",
             "We use BERT for slot-usage belief tracking."),
            candidate("nlpr_ma_001_d", "End-to-End Dialogue State Tracking with Pretraining",
             ""),  # missing
        ),
        judgments={
            "nlpr_ma_001_a": provenance(3, rationale="directly dialogue state tracking method"),
            "nlpr_ma_001_b": provenance(2, confidence=0.6, rationale="DST title, abstract missing"),
            "nlpr_ma_001_c": provenance(3, rationale="DST method"),
            "nlpr_ma_001_d": provenance(2, confidence=0.55, rationale="DST title, abstract missing"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "nlp"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: near_duplicate
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_NEAR_DUPLICATE = [
    case(
        case_id="ml_ret_nd_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="mixup data augmentation",
        candidates=(
            candidate("mlr_nd_001_a", "mixup: Beyond Empirical Risk Minimization",
             "We train on convex combinations of input pairs and labels."),
            candidate("mlr_nd_001_b", "MixUp Data Augmentation for Deep Networks",
             "We train on convex combinations of input pairs and labels."),  # near-dup of a
            candidate("mlr_nd_001_b2", near_duplicate_of="mlr_nd_001_b",
             title="mixup Training for Better Generalization",
             abstract="Convex combinations of input pairs and labels improve generalization."),
            candidate("mlr_nd_001_c", "CutMix: Regularization Strategy",
             "We cut and paste image patches for augmentation."),
            candidate("mlr_nd_001_d", "AutoAugment: Learning Augmentation Policies",
             "We learn augmentation policies from data."),
        ),
        judgments={
            "mlr_nd_001_a": provenance(3, rationale="canonical mixup paper"),
            "mlr_nd_001_b": provenance(2, rationale="near-duplicate of mixup"),
            "mlr_nd_001_b2": provenance(2, rationale="near-duplicate content"),
            "mlr_nd_001_c": provenance(3, rationale="distinct augmentation method"),
            "mlr_nd_001_d": provenance(2, rationale="augmentation method, distinct"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "machine_learning"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
    case(
        case_id="bio_ret_nd_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="paxlovid nirmatrelvir ritonavir covid",
        candidates=(
            candidate("bior_nd_001_a", "Oral Nirmatrelvir for High-Risk Covid-19 (EPIC-HR)",
             "We report that nirmatrelvir-ritonavir reduced Covid-19 hospitalization in high-risk adults."),
            candidate("bior_nd_001_b", "Paxlovid (Nirmatrelvir/Ritonavir) for Covid-19: Trial Results",
             "Nirmatrelvir-ritonavir reduced Covid-19 hospitalization in high-risk adults."),  # near-dup of a
            candidate("bior_nd_001_b2", near_duplicate_of="bior_nd_001_b",
             title="EPIC-HR: Nirmatrelvir-Ritonavir for Covid-19",
             abstract="High-risk adults receiving nirmatrelvir-ritonavir had lower Covid-19 hospitalization."),
            candidate("bior_nd_001_c", "Molnupiravir for Covid-19 (MOVe-OUT)",
             "We report molnupiravir efficacy in mild Covid-19."),
            candidate("bior_nd_001_d", "Remdesivir for Severe Covid-19",
             "Intravenous remdesivir shortened recovery time."),
        ),
        judgments={
            "bior_nd_001_a": provenance(3, rationale="canonical Paxlovid trial"),
            "bior_nd_001_b": provenance(2, rationale="near-duplicate of EPIC-HR"),
            "bior_nd_001_b2": provenance(2, rationale="near-duplicate content"),
            "bior_nd_001_c": provenance(2, rationale="distinct Covid antiviral, related"),
            "bior_nd_001_d": provenance(2, rationale="distinct Covid antiviral"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "biomedical"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
    case(
        case_id="nlp_ret_nd_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="t5 text-to-text transformer",
        candidates=(
            candidate("nlpr_nd_001_a", "Exploring the Limits of Transfer Learning with T5",
             "We cast all NLP tasks as text-to-text with a unified Transformer encoder-decoder."),
            candidate("nlpr_nd_001_b", "T5: The Text-to-Text Transformer",
             "We cast all NLP tasks as text-to-text with a unified Transformer."),  # near-dup of a
            candidate("nlpr_nd_001_b2", near_duplicate_of="nlpr_nd_001_b",
             title="Text-to-Text Transfer Transformer (T5)",
             abstract="Unified encoder-decoder Transformer casting all NLP tasks as text-to-text."),
            candidate("nlpr_nd_001_c", "FLAN: Instruction-Tuning for Generalization",
             "We instruction-tune over many tasks for zero-shot generalization."),
            candidate("nlpr_nd_001_d", "UnifiedQA: Retrieval-Free Question Answering",
             "We pretrain a QA model on multiple QA formats."),
        ),
        judgments={
            "nlpr_nd_001_a": provenance(3, rationale="canonical T5 paper"),
            "nlpr_nd_001_b": provenance(2, rationale="near-duplicate of T5"),
            "nlpr_nd_001_b2": provenance(2, rationale="near-duplicate content"),
            "nlpr_nd_001_c": provenance(2, rationale="instruction-tuning, distinct"),
            "nlpr_nd_001_d": provenance(2, rationale="QA pretraining, distinct"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "nlp"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: source_rank_conflict
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_SOURCE_RANK_CONFLICT = [
    case(
        case_id="ml_ret_sr_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="mixture of experts sparse models",
        candidates=(
            candidate("mlr_sr_001_a", "Mixtral of Experts (MoE)",
             "We release a sparse mixture-of-experts model with strong quality."),
            candidate("mlr_sr_001_b", "A Nature Editorial on Compute Carbon Footprint",
             "Editorial on energy use in AI, unrelated to MoE architectures."),  # high source rank, irrelevant
            candidate("mlr_sr_001_c", "Outrageously Large Neural Networks: The Sparsely-Gated MoE Layer",
             "We introduce sparsely-gated MoE layers."),
            candidate("mlr_sr_001_d", "Switch Transformers: Trillion-Parameter MoE",
             "We scale MoE Transformers via top-1 routing."),
        ),
        judgments={
            "mlr_sr_001_a": provenance(3, rationale="directly sparse mixture-of-experts"),
            "mlr_sr_001_b": provenance(0, rationale="editorial, source rank conflicts with relevance", confidence=0.85),
            "mlr_sr_001_c": provenance(3, rationale="canonical sparse MoE method"),
            "mlr_sr_001_d": provenance(3, rationale="sparse MoE Transformer"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "machine_learning"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
    case(
        case_id="bio_ret_sr_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="glycemic control type 2 diabetes",
        candidates=(
            candidate("bior_sr_001_a", "Continuous Glucose Monitoring in Type 2 Diabetes",
             "We report glycemic improvements with CGM in insulin-treated T2D."),
            candidate("bior_sr_001_b", "A Lancet Editorial on Global Diabetes Policy",
             "Editorial on diabetes policy, not glycemic-control evidence."),  # high source rank, irrelevant
            candidate("bior_sr_001_c", "Empagliflozin and Glycemic Outcomes (EMPA-REG)",
             "We report SGLT2 inhibitor effects on glycemia and outcomes."),
            candidate("bior_sr_001_d", "Intensive vs Standard Glycemic Control Meta-analysis",
             "We synthesize trials comparing glycemic targets."),
        ),
        judgments={
            "bior_sr_001_a": provenance(3, rationale="directly glycemic control in T2D"),
            "bior_sr_001_b": provenance(0, rationale="policy editorial, source rank conflicts with relevance", confidence=0.85),
            "bior_sr_001_c": provenance(3, rationale="glycemic-control drug trial"),
            "bior_sr_001_d": provenance(3, rationale="glycemic-control meta-analysis"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "biomedical"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
    case(
        case_id="nlp_ret_sr_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="open-domain question answering retriever",
        candidates=(
            candidate("nlpr_sr_001_a", "Dense Passage Retrieval for Open-Domain QA",
             "We learn dense retrievers for open-domain question answering."),
            candidate("nlpr_sr_001_b", "A Science Editorial on Open-Access Publishing",
             "Editorial on open-access policy, not open-domain QA."),  # high source rank, irrelevant
            candidate("nlpr_sr_001_c", "ColBERT: Efficient Passage-Side Late Interaction",
             "We score passages via late interaction of contextualized embeddings."),
            candidate("nlpr_sr_001_d", "FiD: Fusion-in-Decoder for Open-Domain QA",
             "We fuse retrieved passages in the decoder for ODQA."),
        ),
        judgments={
            "nlpr_sr_001_a": provenance(3, rationale="canonical dense retriever for ODQA"),
            "nlpr_sr_001_b": provenance(0, rationale="open-access editorial, source rank conflicts with relevance", confidence=0.85),
            "nlpr_sr_001_c": provenance(3, rationale="retrieval method for ODQA"),
            "nlpr_sr_001_d": provenance(3, rationale="reader for ODQA retrieval pipeline"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "nlp"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: acronym_vs_expanded
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_ACRONYM_VS_EXPANDED = [
    case(
        case_id="ml_ret_ac_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="LORA low-rank adaptation",
        candidates=(
            candidate("mlr_ac_001_a", "LoRA: Low-Rank Adaptation of Large Language Models",
             "We freeze base weights and train low-rank adapters."),
            candidate("mlr_ac_001_b", "QLoRA: Quantized LoRA for Efficient Fine-Tuning",
             "We quantize base weights and apply LoRA adapters."),
            candidate("mlr_ac_001_c", "Lora: A Long-Range Wireless Protocol Survey",
             "We survey LoRaWAN protocol characteristics."),  # acronym collision
            candidate("mlr_ac_001_d", "AdaLoRA: Adaptive Budget Allocation",
             "We adaptively distribute LoRA's rank budget."),
        ),
        judgments={
            "mlr_ac_001_a": provenance(3, rationale="canonical LoRA method"),
            "mlr_ac_001_b": provenance(3, rationale="QLoRA adapter method"),
            "mlr_ac_001_c": provenance(0, rationale="LoRa wireless protocol, acronym collision"),
            "mlr_ac_001_d": provenance(3, rationale="adaptive LoRA variant"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "machine_learning"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
    case(
        case_id="bio_ret_ac_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="PCSK9 inhibitors cholesterol",
        candidates=(
            candidate("bior_ac_001_a", "PCSK9 Monoclonal Antibodies for Hypercholesterolemia",
             "We review PCSK9 inhibitors for LDL-C lowering."),
            candidate("bior_ac_001_b", "Alirocumab and Cardiovascular Events (ODYSSEY)",
             "Phase 3 trial of a PCSK9 inhibitor."),
            candidate("bior_ac_001_c", "PCSK: A Parallel Computing Systems Kit",
             "A software toolkit for parallel computing."),  # acronym collision
            candidate("bior_ac_001_d", "Inclisiran: siRNA Targeting PCSK9",
             "We lower LDL-C via PCSK9-directed siRNA."),
        ),
        judgments={
            "bior_ac_001_a": provenance(3, rationale="directly PCSK9 inhibitors"),
            "bior_ac_001_b": provenance(3, rationale="PCSK9 trial"),
            "bior_ac_001_c": provenance(0, rationale="software toolkit, acronym collision"),
            "bior_ac_001_d": provenance(3, rationale="PCSK9-targeting therapy"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "biomedical"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
    case(
        case_id="nlp_ret_ac_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="BERT bidirectional encoder",
        candidates=(
            candidate("nlpr_ac_001_a", "BERT: Pre-training of Deep Bidirectional Transformers",
             "We pre-train a bidirectional Transformer encoder."),
            candidate("nlpr_ac_001_b", "DistilBERT: A Distilled Version of BERT",
             "We distill BERT into a smaller bidirectional encoder."),
            candidate("nlpr_ac_001_c", "Bert: A Biography of a Household Robot",
             "A biographical article about a robot named Bert."),  # acronym collision
            candidate("nlpr_ac_001_d", "ELECTRA: Pre-training as Discriminative Replacement",
             "A BERT-family encoder trained via replaced-token detection."),
        ),
        judgments={
            "nlpr_ac_001_a": provenance(3, rationale="canonical BERT bidirectional encoder"),
            "nlpr_ac_001_b": provenance(3, rationale="BERT-family bidirectional encoder"),
            "nlpr_ac_001_c": provenance(0, rationale="biography, acronym collision"),
            "nlpr_ac_001_d": provenance(2, rationale="BERT-family encoder, distinct method"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "nlp"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: negated_findings
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_NEGATED_FINDINGS = [
    case(
        case_id="ml_ret_nf_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="does pretraining help low-data",
        candidates=(
            candidate("mlr_nf_001_a", "Pretraining on Large Corpora Helps Low-Data Tasks",
             "We show that pretraining improves downstream accuracy on small datasets."),
            candidate("mlr_nf_001_b", "When Pretraining Hurts: Negative Transfer in Low-Data",
             "We identify cases where pretraining degrades low-data performance."),  # negated
            candidate("mlr_nf_001_c", "Domain Mismatch Reduces Pretraining Benefit",
             "Pretraining helps less when source and target domains differ."),  # boundary/negated
            candidate("mlr_nf_001_d", "Self-Supervised Pretraining for Low-Data Vision",
             "We study pretraining benefits on small vision benchmarks."),
        ),
        judgments={
            "mlr_nf_001_a": provenance(3, rationale="directly addresses pretraining-low-data question"),
            "mlr_nf_001_b": provenance(3, rationale="negated-result study, directly on-topic"),
            "mlr_nf_001_c": provenance(3, rationale="boundary-case evidence on the same question"),
            "mlr_nf_001_d": provenance(2, rationale="related pretraining study"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "machine_learning"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
    case(
        case_id="bio_ret_nf_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="vitamin d supplementation fracture prevention",
        candidates=(
            candidate("bior_nf_001_a", "Vitamin D Plus Calcium Reduces Fractures in Elderly",
             "We report reduced hip fractures with combined supplementation."),
            candidate("bior_nf_001_b", "Vitamin D Alone Does Not Prevent Fractures (VITAL)",
             "We find no fracture reduction with vitamin D alone."),  # negated
            candidate("bior_nf_001_c", "High-Dose Vitamin D No Better Than Standard for Fractures",
             "Annual high-dose vitamin D did not reduce fractures."),  # negated
            candidate("bior_nf_001_d", "Vitamin D Status and Bone Mineral Density",
             "We associate vitamin D levels with BMD."),
        ),
        judgments={
            "bior_nf_001_a": provenance(3, rationale="directly addresses the fracture question"),
            "bior_nf_001_b": provenance(3, rationale="negated-result trial, directly on-topic"),
            "bior_nf_001_c": provenance(3, rationale="negated-result trial"),
            "bior_nf_001_d": provenance(2, rationale="surrogate endpoint, adjacent"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "biomedical"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
    case(
        case_id="nlp_ret_nf_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="evidence_support",
        query="does scaling model size improve safety",
        candidates=(
            candidate("nlpr_nf_001_a", "Scaling Language Models Improves Helpfulness",
             "We report improved helpfulness with scale."),
            candidate("nlpr_nf_001_b", "Scaling Alone Does Not Improve Safety",
             "We find that larger models remain unsafe without explicit safety training."),  # negated
            candidate("nlpr_nf_001_c", "Inverse Scaling: When Bigger Is Worse",
             "We identify tasks where larger models perform worse, including some safety tasks."),  # negated
            candidate("nlpr_nf_001_d", "Safety Fine-Tuning at Scale",
             "We study the effect of safety fine-tuning on large models."),
        ),
        judgments={
            "nlpr_nf_001_a": provenance(2, rationale="related scaling study, helpfulness not safety"),
            "nlpr_nf_001_b": provenance(3, rationale="negated-result study, directly on-topic"),
            "nlpr_nf_001_c": provenance(3, rationale="negated inverse-scaling evidence"),
            "nlpr_nf_001_d": provenance(2, rationale="safety fine-tuning, adjacent"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "nlp"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: exact_identifier
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_EXACT_IDENTIFIER = [
    case(
        case_id="ml_ret_ei_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="literature_mapping",
        query="DDPM",
        candidates=(
            candidate("mlr_ei_001_a", "Denoising Diffusion Probabilistic Models (DDPM)",
             "We generate high-quality images via a denoising diffusion process."),
            candidate("mlr_ei_001_b", "DDPMs via Stochastic Differential Equations",
             "We cast DDPM sampling as probability-flow ODEs."),
            candidate("mlr_ei_001_c", "Improved DDPM: Better Sampling and Likelihood",
             "We improve DDPM sampling efficiency and likelihood estimation."),
            candidate("mlr_ei_001_d", "Guided Diffusion (GLIDE)",
             "We add classifier-free guidance to a diffusion model."),
        ),
        judgments={
            "mlr_ei_001_a": provenance(3, rationale="exact DDPM paper"),
            "mlr_ei_001_b": provenance(3, rationale="directly extends DDPM"),
            "mlr_ei_001_c": provenance(3, rationale="DDPM variant"),
            "mlr_ei_001_d": provenance(2, rationale="diffusion family, not DDPM specifically"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "machine_learning"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
    ),
    case(
        case_id="bio_ret_ei_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="literature_mapping",
        query="CRISPR-Cas9",
        candidates=(
            candidate("bior_ei_001_a", "A Programmable Dual-RNA-Guided DNA Endonuclease (Cas9)",
             "We show Cas9 can be programmed for targeted genome editing."),
            candidate("bior_ei_001_b", "CRISPR-Cas9 for Mammalian Genome Editing",
             "We apply CRISPR-Cas9 to edit human cells."),
            candidate("bior_ei_001_c", "High-Efficiency CRISPR-Cas9 in Human Cells",
             "We optimize CRISPR-Cas9 editing conditions."),
            candidate("bior_ei_001_d", "Off-Target Effects of CRISPR-Cas9",
             "We characterize CRISPR-Cas9 off-target cleavage."),
        ),
        judgments={
            "bior_ei_001_a": provenance(3, rationale="canonical CRISPR-Cas9 paper"),
            "bior_ei_001_b": provenance(3, rationale="CRISPR-Cas9 application"),
            "bior_ei_001_c": provenance(3, rationale="CRISPR-Cas9 optimization"),
            "bior_ei_001_d": provenance(3, rationale="CRISPR-Cas9 specificity"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "biomedical"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
    ),
    case(
        case_id="nlp_ret_ei_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="literature_mapping",
        query="Whisper",
        candidates=(
            candidate("nlpr_ei_001_a", "Whisper: Robust Speech Recognition via Large-Scale Weak Supervision",
             "We train a multilingual ASR model on 680k hours of weakly-supervised audio."),
            candidate("nlpr_ei_001_b", "Fine-Tuning Whisper for Low-Resource Languages",
             "We adapt Whisper to under-served languages."),
            candidate("nlpr_ei_001_c", "Distil-Whisper: Faster Streaming ASR",
             "We distill Whisper for real-time transcription."),
            candidate("nlpr_ei_001_d", "Whispering-Gallery Mode Optical Sensors",
             "We characterize optical whispering-gallery mode resonators."),  # collision
        ),
        judgments={
            "nlpr_ei_001_a": provenance(3, rationale="exact Whisper ASR paper"),
            "nlpr_ei_001_b": provenance(2, rationale="Whisper fine-tuning"),
            "nlpr_ei_001_c": provenance(2, rationale="Whisper distillation"),
            "nlpr_ei_001_d": provenance(0, rationale="optical sensors, not ASR Whisper"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "nlp"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: neutral
# ════════════════════════════════════════════════════════════════════

_RETRIEVAL_NEUTRAL = [
    case(
        case_id="ml_ret_nt_001",
        domain="machine_learning",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="graph convolutional networks",
        candidates=(
            candidate("mlr_nt_001_a", "Semi-Supervised Classification with GCNs",
             "We introduce graph convolutional networks for node classification."),
            candidate("mlr_nt_001_b", "GraphSAGE: Inductive Learning on Large Graphs",
             "We sample and aggregate neighborhoods inductively."),
            candidate("mlr_nt_001_c", "GAT: Graph Attention Networks",
             "We apply attention over graph neighborhoods."),
            candidate("mlr_nt_001_d", "GIN: How Powerful are GNNs?",
             "We characterize the representational power of GNNs."),
        ),
        judgments={
            "mlr_nt_001_a": provenance(3, rationale="canonical GCN paper"),
            "mlr_nt_001_b": provenance(3, rationale="canonical graph-neural method"),
            "mlr_nt_001_c": provenance(3, rationale="graph attention method"),
            "mlr_nt_001_d": provenance(2, rationale="GNN theory, relevant"),
        },
        split=_split_for(SLICE_NEUTRAL, "machine_learning"),
        primary_slice=SLICE_NEUTRAL,
    ),
    case(
        case_id="bio_ret_nt_001",
        domain="biomedical",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="organoid models drug screening",
        candidates=(
            candidate("bior_nt_001_a", "Patient-Derived Organoids for Drug Screening",
             "We use organoids to screen cancer drugs in vitro."),
            candidate("bior_nt_001_b", "Intestinal Organoids for Personalized Therapy",
             "We guide therapy choices using intestinal organoid responses."),
            candidate("bior_nt_001_c", "Brain Organoids for Neurodevelopmental Studies",
             "We model neurodevelopment using cerebral organoids."),
            candidate("bior_nt_001_d", "Organ-on-a-Chip: Beyond Organoids",
             "We compare microfluidic models to organoid systems."),
        ),
        judgments={
            "bior_nt_001_a": provenance(3, rationale="directly organoid drug screening"),
            "bior_nt_001_b": provenance(3, rationale="organoid-guided therapy"),
            "bior_nt_001_c": provenance(2, rationale="organoids for neurodevelopment, adjacent"),
            "bior_nt_001_d": provenance(2, rationale="related in-vitro model family"),
        },
        split=_split_for(SLICE_NEUTRAL, "biomedical"),
        primary_slice=SLICE_NEUTRAL,
    ),
    case(
        case_id="nlp_ret_nt_001",
        domain="nlp",
        surface="retrieval_ranking",
        intent="general_research_relevance",
        query="speech recognition acoustic model",
        candidates=(
            candidate("nlpr_nt_001_a", "Wav2Vec 2.0: Self-Supervised Speech Pretraining",
             "We pretrain speech representations for ASR."),
            candidate("nlpr_nt_001_b", "Conformer: Convolution-Augmented Transformer for ASR",
             "We combine convolutions and attention for acoustic modeling."),
            candidate("nlpr_nt_001_c", "Listen Attend and Spell (LAS)",
             "We introduce an attention-based end-to-end ASR model."),
            candidate("nlpr_nt_001_d", "CTC-Based Acoustic Modeling",
             "We use connectionist temporal classification for ASR."),
        ),
        judgments={
            "nlpr_nt_001_a": provenance(3, rationale="canonical ASR acoustic model"),
            "nlpr_nt_001_b": provenance(3, rationale="canonical ASR acoustic model"),
            "nlpr_nt_001_c": provenance(3, rationale="canonical end-to-end ASR"),
            "nlpr_nt_001_d": provenance(2, rationale="CTC acoustic modeling, foundational"),
        },
        split=_split_for(SLICE_NEUTRAL, "nlp"),
        primary_slice=SLICE_NEUTRAL,
    ),
]


