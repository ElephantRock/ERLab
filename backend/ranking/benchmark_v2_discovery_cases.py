"""P1B.1: Discovery ranking benchmark v2 cases.

33 discovery cases = 11 slice types × 3 domains (machine_learning,
biomedical, nlp). Slice types: the 10 required adversarial slices plus a
neutral baseline slice. See benchmark_v2_schema.py for the vocabulary.

Splits are assigned deterministically per (slice, domain) so that every
split contains a balanced mix of slices and domains:
- calibration:  used to freeze policy weights (NOT for final selection)
- development:  used for policy comparison and slice analysis
- held_out:     reported once, after policy selection, frozen before tuning

Provisional judgments are single-pass (initial synthetic author). The blind
adjudicator's second pass is added later via the adjudication package; the
adjudicator must NOT see these grades when re-annotating.

All titles/abstracts are synthetic but follow realistic phrasing so that
lexical and semantic ranking surfaces can be meaningfully distinguished.
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

# Split rotation: deterministic per slice so each split gets a balanced mix.
# Within a slice, domain order ml->bio->nlp maps to a rotating split assignment
# that differs per slice, ensuring no single split is dominated by one slice.
_SPLITS_BY_SLICE_DOMAIN = {
    # slice: (ml, bio, nlp)
    SLICE_LEXICAL_TRAP: ("calibration", "development", "held_out"),
    SLICE_SEMANTIC_PARAPHRASE: ("development", "held_out", "calibration"),
    SLICE_METHOD_VS_APPLICATION: ("held_out", "calibration", "development"),
    SLICE_REVIEW_VS_PRIMARY: ("calibration", "held_out", "development"),
    SLICE_MISSING_ABSTRACT: ("development", "calibration", "held_out"),
    SLICE_NEAR_DUPLICATE: ("held_out", "development", "calibration"),
    SLICE_SOURCE_RANK_CONFLICT: ("calibration", "development", "held_out"),
    SLICE_ACRONYM_VS_EXPANDED: ("development", "held_out", "calibration"),
    SLICE_NEGATED_FINDINGS: ("held_out", "calibration", "development"),
    SLICE_EXACT_IDENTIFIER: ("calibration", "development", "held_out"),
    SLICE_NEUTRAL: ("development", "held_out", "calibration"),
}

_DOMAIN_ORDER = ("machine_learning", "biomedical", "nlp")


def _split_for(slice_type: str, domain: str) -> str:
    idx = _DOMAIN_ORDER.index(domain)
    return _SPLITS_BY_SLICE_DOMAIN[slice_type][idx]


# ════════════════════════════════════════════════════════════════════
# Slice: lexical_trap — high term overlap, grade 0 (wrong meaning)
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_LEXICAL_TRAP = [
    # ── machine_learning ──
    case(
        case_id="ml_disc_lt_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="gradient descent optimization for neural networks",
        candidates=(
            candidate("ml_lt_001_a", "An Overview of Gradient Descent Optimization Algorithms",
             "We survey gradient-based methods including SGD, momentum, and Adam for training neural networks."),
            candidate("ml_lt_001_b", "Adam: A Method for Stochastic Optimization",
             "We propose Adam, an efficient stochastic gradient descent method for first-order gradient-based optimization."),
            candidate("ml_lt_001_c", "Optimizing Network Routing with Descent Algorithms",
             "We apply shortest-descent routing to optimize computer network traffic flow."),  # lexical trap
            candidate("ml_lt_001_d", "Neural Network Regularization via Dropout",
             "Dropout prevents overfitting in deep neural networks during gradient-based training."),
        ),
        judgments={
            "ml_lt_001_a": provenance(3, rationale="directly surveys gradient descent for neural networks"),
            "ml_lt_001_b": provenance(3, rationale="Adam is a canonical gradient descent optimizer for NNs"),
            "ml_lt_001_c": provenance(0, rationale="network routing, not neural networks; shared tokens only"),
            "ml_lt_001_d": provenance(2, rationale="relevant NN training topic but not optimization-focused"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "machine_learning"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
    # ── biomedical ──
    case(
        case_id="bio_disc_lt_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="drug resistance mechanisms in cancer therapy",
        candidates=(
            candidate("bio_lt_001_a", "Mechanisms of Drug Resistance in Cancer Chemotherapy",
             "We review acquired and intrinsic resistance mechanisms including efflux pumps and apoptosis evasion."),
            candidate("bio_lt_001_b", "Overcoming Tyrosine Kinase Inhibitor Resistance in Lung Cancer",
             "We characterize resistance mechanisms to TKI therapy in non-small-cell lung cancer."),
            candidate("bio_lt_001_c", "Resistance Welding of Drug-Eluting Cardiovascular Stents",
             "Manufacturing parameters for resistance-welded drug-coated stents."),  # lexical trap
            candidate("bio_lt_001_d", "Apoptosis Evasion in Tumor Cells",
             "We examine how cancer cells evade programmed cell death under therapy."),
        ),
        judgments={
            "bio_lt_001_a": provenance(3, rationale="direct review of drug resistance in cancer therapy"),
            "bio_lt_001_b": provenance(3, rationale="specific drug-resistance mechanism in cancer"),
            "bio_lt_001_c": provenance(0, rationale="manufacturing/welding; 'resistance' and 'drug' used differently"),
            "bio_lt_001_d": provenance(2, rationale="relevant resistance mechanism but broader scope"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "biomedical"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
    # ── nlp ──
    case(
        case_id="nlp_disc_lt_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="neural machine translation attention models",
        candidates=(
            candidate("nlp_lt_001_a", "Neural Machine Translation by Jointly Learning to Align and Translate",
             "We introduce attention-based encoder-decoder models for neural machine translation."),
            candidate("nlp_lt_001_b", "Attention Is All You Need",
             "The Transformer relies entirely on self-attention for sequence transduction."),
            candidate("nlp_lt_001_c", "A Neural Network Approach to Translation Memory Alignment",
             "We align translation-memory segments using neural embeddings for CAT tools."),  # lexical trap
            candidate("nlp_lt_001_d", "Evaluating Machine Translation with BLEU",
             "BLEU is a standard metric for evaluating machine translation quality."),
        ),
        judgments={
            "nlp_lt_001_a": provenance(3, rationale="canonical attention-based NMT paper"),
            "nlp_lt_001_b": provenance(3, rationale="Transformer attention model for translation"),
            "nlp_lt_001_c": provenance(0, rationale="translation-memory alignment, not MT attention models"),
            "nlp_lt_001_d": provenance(2, rationale="MT evaluation metric, adjacent but not an attention model"),
        },
        split=_split_for(SLICE_LEXICAL_TRAP, "nlp"),
        primary_slice=SLICE_LEXICAL_TRAP,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: semantic_paraphrase — low term overlap, high relevance
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_SEMANTIC_PARAPHRASE = [
    case(
        case_id="ml_disc_sp_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="efficiently training very large language models",
        candidates=(
            candidate("ml_sp_001_a", "Efficient Memory Management for Large Language Model Training",
             "ZeRO partitions optimizer states across devices to reduce the memory footprint of gigantic models."),  # paraphrase
            candidate("ml_sp_001_b", "Scaling Laws for Neural Language Models",
             "Model performance follows power laws in compute, data, and parameters."),
            candidate("ml_sp_001_c", "A Survey of Efficient Training Methods",
             "We review techniques for reducing the cost of training deep networks."),
            candidate("ml_sp_001_d", "MobileBERT: Distilling BERT for Mobile Devices",
             "We compress a large Transformer for on-device inference."),
        ),
        judgments={
            "ml_sp_001_a": provenance(3, rationale="directly addresses training very large models, paraphrased phrasing"),
            "ml_sp_001_b": provenance(3, rationale="directly about scaling large model training"),
            "ml_sp_001_c": provenance(2, rationale="survey of efficient training, relevant but broad"),
            "ml_sp_001_d": provenance(1, rationale="inference-side compression, not training at scale"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "machine_learning"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
    ),
    case(
        case_id="bio_disc_sp_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="reducing false positives in cancer screening",
        candidates=(
            candidate("bio_sp_001_a", "Improving Specificity of Mammography with AI-assisted Triage",
             "We lower unnecessary recall rates by triaging mammograms with a deep model."),  # paraphrase
            candidate("bio_sp_001_b", "Overdiagnosis in Prostate Cancer Screening: A Systematic Review",
             "We quantify harms of excessive prostate-specific antigen testing."),
            candidate("bio_sp_001_c", "Risk-based Stratification for Colorectal Screening",
             "Personalized screening intervals reduce unnecessary colonoscopies."),
            candidate("bio_sp_001_d", "Deep Learning for Chest Radiograph Triaging",
             "A model prioritizes radiographs likely to be abnormal."),
        ),
        judgments={
            "bio_sp_001_a": provenance(3, rationale="directly reduces false-positive recalls via AI triage, paraphrased"),
            "bio_sp_001_b": provenance(2, rationale="addresses overdiagnosis from screening, related framing"),
            "bio_sp_001_c": provenance(3, rationale="directly reduces unnecessary screening procedures"),
            "bio_sp_001_d": provenance(2, rationale="triaging tool, different modality but relevant concept"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "biomedical"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
    ),
    case(
        case_id="nlp_disc_sp_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="helping models follow human instructions",
        candidates=(
            candidate("nlp_sp_001_a", "Training Language Models to Follow Instructions with Human Feedback",
             "We fine-tune large models using RLHF to align outputs with user intent."),  # paraphrase
            candidate("nlp_sp_001_b", "Constitutional AI: Harmlessness from AI Feedback",
             "Models self-critique using a constitution to produce helpful, harmless responses."),
            candidate("nlp_sp_001_c", "InstructGPT and the Alignment Problem",
             "We study how instruction tuning changes model behavior."),
            candidate("nlp_sp_001_d", "A Lexicon of Human Instruction Verbs",
             "A linguistic survey of imperative verb usage in instruction manuals."),  # mild trap
        ),
        judgments={
            "nlp_sp_001_a": provenance(3, rationale="canonical instruction-following work, paraphrased query"),
            "nlp_sp_001_b": provenance(3, rationale="directly about helpful instruction-following"),
            "nlp_sp_001_c": provenance(2, rationale="adjacent discussion of instruction tuning"),
            "nlp_sp_001_d": provenance(0, rationale="linguistics of imperatives, not ML instruction-following"),
        },
        split=_split_for(SLICE_SEMANTIC_PARAPHRASE, "nlp"),
        primary_slice=SLICE_SEMANTIC_PARAPHRASE,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: method_vs_application — method paper vs application paper
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_METHOD_VS_APPLICATION = [
    case(
        case_id="ml_disc_mv_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="method_relevance",
        query="self-supervised representation learning methods",
        candidates=(
            candidate("ml_mv_001_a", "Masked Autoencoders Are Scalable Vision Learners",
             "We propose masked autoencoding as a self-supervised method for learning visual representations."),  # method
            candidate("ml_mv_001_b", "Applying Self-Supervised Features to Medical Image Classification",
             "We fine-tune self-supervised features for downstream medical imaging."),  # application
            candidate("ml_mv_001_c", "BYOL: Bootstrap Your Own Latent",
             "A new self-supervised learning objective without negative samples."),  # method
            candidate("ml_mv_001_d", "A Survey of Representation Learning",
             "Broad survey covering supervised and self-supervised approaches."),
        ),
        judgments={
            "ml_mv_001_a": provenance(3, rationale="directly a self-supervised method paper"),
            "ml_mv_001_b": provenance(2, rationale="application of self-supervised methods, downstream focus"),
            "ml_mv_001_c": provenance(3, rationale="canonical self-supervised method"),
            "ml_mv_001_d": provenance(1, rationale="broad survey, only partially about self-supervised methods"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "machine_learning"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
    case(
        case_id="bio_disc_mv_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="method_relevance",
        query="single-cell clustering algorithms",
        candidates=(
            candidate("bio_mv_001_a", "Leiden: Community Detection in Large Networks",
             "We propose a scalable community-detection algorithm applicable to single-cell graphs."),  # method
            candidate("bio_mv_001_b", "Clustering Pancreatic Islet Cells with Leiden",
             "We apply Leiden clustering to identify pancreatic cell subtypes."),  # application
            candidate("bio_mv_001_c", "Phenograph for High-Dimensional Cytometry",
             "A graph-based clustering method for single-cell data."),  # method
            candidate("bio_mv_001_d", "Benchmarking Single-Cell Clustering Tools",
             "Comparative evaluation of clustering methods."),
        ),
        judgments={
            "bio_mv_001_a": provenance(3, rationale="general clustering method used for single-cell"),
            "bio_mv_001_b": provenance(2, rationale="application of clustering to a specific tissue"),
            "bio_mv_001_c": provenance(3, rationale="clustering algorithm designed for single-cell"),
            "bio_mv_001_d": provenance(2, rationale="benchmark of methods, relevant but evaluative"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "biomedical"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
    case(
        case_id="nlp_disc_mv_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="method_relevance",
        query="coreference resolution algorithms",
        candidates=(
            candidate("nlp_mv_001_a", "End-to-end Neural Coreference Resolution",
             "We propose an end-to-end neural model for coreference resolution."),  # method
            candidate("nlp_mv_001_b", "Using Coreference Features for Reading Comprehension",
             "We feed coreference signals into a downstream QA system."),  # application
            candidate("nlp_mv_001_c", "SpanBERT: Improving Pre-training by Representing Spans",
             "Pre-training objective that helps coreference-related tasks."),  # method (indirect)
            candidate("nlp_mv_001_d", "Coreference in Low-Resource Languages",
             "We evaluate cross-lingual transfer for coreference."),
        ),
        judgments={
            "nlp_mv_001_a": provenance(3, rationale="direct coreference resolution method"),
            "nlp_mv_001_b": provenance(2, rationale="uses coreference as feature, application focus"),
            "nlp_mv_001_c": provenance(2, rationale="method that benefits coreference indirectly"),
            "nlp_mv_001_d": provenance(2, rationale="coreference study, applied/evaluative"),
        },
        split=_split_for(SLICE_METHOD_VS_APPLICATION, "nlp"),
        primary_slice=SLICE_METHOD_VS_APPLICATION,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: review_vs_primary — review paper vs primary study
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_REVIEW_VS_PRIMARY = [
    case(
        case_id="ml_disc_rv_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="evidence_support",
        query="graph contrastive learning empirical results",
        candidates=(
            candidate("ml_rv_001_a", "Graph Contrastive Learning with Adaptive Augmentation",
             "We run extensive experiments showing gains on node classification benchmarks."),  # primary
            candidate("ml_rv_001_b", "A Comprehensive Survey of Graph Contrastive Learning",
             "We survey graph contrastive methods and categorize their augmentations."),  # review
            candidate("ml_rv_001_c", "Empirical Evaluation of Graph Augmentation Strategies",
             "Ablation study comparing augmentation choices across datasets."),  # primary
            candidate("ml_rv_001_d", "Trends in Self-Supervised Graph Learning: A Review",
             "Narrative review of the self-supervised graph-learning landscape."),  # review
        ),
        judgments={
            "ml_rv_001_a": provenance(3, rationale="primary study with empirical results"),
            "ml_rv_001_b": provenance(2, rationale="review, relevant but synthesizes rather than reports results"),
            "ml_rv_001_c": provenance(3, rationale="primary empirical evaluation"),
            "ml_rv_001_d": provenance(1, rationale="broad review, tangential to contrastive specifics"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "machine_learning"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
    case(
        case_id="bio_disc_rv_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="clinical trial results for GLP-1 receptor agonists",
        candidates=(
            candidate("bio_rv_001_a", "Semaglutide and Cardiovascular Outcomes in Obesity (SELECT Trial)",
             "Randomized controlled trial reporting reduced MACE with semaglutide."),  # primary
            candidate("bio_rv_001_b", "GLP-1 Receptor Agonists: A Systematic Review and Meta-analysis",
             "We synthesize trial evidence on efficacy and safety of GLP-1 RAs."),  # review
            candidate("bio_rv_001_c", "Tirzepatide efficacy in type 2 diabetes (SURPASS-2)",
             "Phase 3 trial results for dual GIP/GLP-1 agonist."),  # primary
            candidate("bio_rv_001_d", "An Endocrinologist's Overview of Incretin Therapies",
             "Narrative clinical review of incretin-based drugs."),  # review
        ),
        judgments={
            "bio_rv_001_a": provenance(3, rationale="primary RCT with direct clinical-trial results"),
            "bio_rv_001_b": provenance(2, rationale="systematic review, aggregates rather than reports"),
            "bio_rv_001_c": provenance(3, rationale="primary phase-3 trial"),
            "bio_rv_001_d": provenance(1, rationale="narrative clinical overview, low empirical specificity"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "biomedical"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
    case(
        case_id="nlp_disc_rv_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="evidence_support",
        query="chain-of-thought prompting experimental gains",
        candidates=(
            candidate("nlp_rv_001_a", "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
             "We report accuracy gains on GSM8K and other math benchmarks via CoT."),  # primary
            candidate("nlp_rv_001_b", "A Survey of Prompting Methods for LLMs",
             "We categorize prompting techniques including CoT."),  # review
            candidate("nlp_rv_001_c", "Self-Consistency Improves Chain-of-Thought Reasoning",
             "Sampling multiple CoT rationales improves accuracy empirically."),  # primary
            candidate("nlp_rv_001_d", "Reasoning in LLMs: A Literature Synthesis",
             "Narrative review covering CoT and related techniques."),  # review
        ),
        judgments={
            "nlp_rv_001_a": provenance(3, rationale="primary CoT paper with experimental gains"),
            "nlp_rv_001_b": provenance(2, rationale="survey mentioning CoT among many methods"),
            "nlp_rv_001_c": provenance(3, rationale="primary study extending CoT empirically"),
            "nlp_rv_001_d": provenance(1, rationale="broad synthesis, not direct experimental evidence"),
        },
        split=_split_for(SLICE_REVIEW_VS_PRIMARY, "nlp"),
        primary_slice=SLICE_REVIEW_VS_PRIMARY,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: missing_abstract — candidates with no abstract text
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_MISSING_ABSTRACT = [
    case(
        case_id="ml_disc_ma_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="diffusion models for image generation",
        candidates=(
            candidate("ml_ma_001_a", "Denoising Diffusion Probabilistic Models",
             "We introduce DDPMs for high-quality image synthesis."),  # full abstract
            candidate("ml_ma_001_b", "Score-Based Generative Modeling Through SDEs",
             ""),  # missing abstract
            candidate("ml_ma_001_c", "High-Resolution Image Synthesis with Latent Diffusion Models",
             "LDMs perform diffusion in a compressed latent space for efficient high-res synthesis."),
            candidate("ml_ma_001_d", "Photorealistic Text-to-Image Diffusion Models (Imagen)",
             ""),  # missing abstract
        ),
        judgments={
            "ml_ma_001_a": provenance(3, rationale="canonical diffusion model for image generation"),
            "ml_ma_001_b": provenance(2, confidence=0.6, rationale="title indicates relevance but no abstract to verify scope"),
            "ml_ma_001_c": provenance(3, rationale="directly high-res image diffusion"),
            "ml_ma_001_d": provenance(2, confidence=0.6, rationale="title fits but abstract absent; relevance plausible not confirmed"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "machine_learning"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
    case(
        case_id="bio_disc_ma_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="lipid nanoparticle mRNA vaccine delivery",
        candidates=(
            candidate("bio_ma_001_a", "Lipid Nanoparticle Delivery of mRNA Vaccines",
             "We characterize LNP formulations for mRNA delivery and immunogenicity."),
            candidate("bio_ma_001_b", "Ionizable Lipids for mRNA Formulation",
             ""),  # missing abstract
            candidate("bio_ma_001_c", "Pfizer-BioNTech BNT162b2 Vaccine Immunogenicity",
             "We report phase-1 immunogenicity data for the BNT162b2 mRNA vaccine."),
            candidate("bio_ma_001_d", "mRNA Stability in LNP Formulations",
             ""),  # missing abstract
        ),
        judgments={
            "bio_ma_001_a": provenance(3, rationale="directly LNP delivery of mRNA vaccines"),
            "bio_ma_001_b": provenance(2, confidence=0.6, rationale="relevant-sounding title, abstract missing"),
            "bio_ma_001_c": provenance(2, rationale="mRNA vaccine study, delivery not the focus"),
            "bio_ma_001_d": provenance(2, confidence=0.6, rationale="LNP-related title, no abstract to confirm"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "biomedical"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
    case(
        case_id="nlp_disc_ma_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="low-resource machine translation",
        candidates=(
            candidate("nlp_ma_001_a", "Improving Low-Resource Neural MT with Transfer Learning",
             "We pre-train on high-resource pairs and transfer to low-resource languages."),
            candidate("nlp_ma_001_b", "Multilingual Pretraining for Low-Resource Translation",
             ""),  # missing abstract
            candidate("nlp_ma_001_c", "Back-Translation for Low-Resource NMT",
             "Synthetic parallel data from back-translation improves low-resource MT."),
            candidate("nlp_ma_001_d", "Evaluating NMT on Truly Low-Resource Languages",
             ""),  # missing abstract
        ),
        judgments={
            "nlp_ma_001_a": provenance(3, rationale="directly low-resource NMT method"),
            "nlp_ma_001_b": provenance(2, confidence=0.6, rationale="relevant title, abstract missing"),
            "nlp_ma_001_c": provenance(3, rationale="canonical low-resource NMT technique"),
            "nlp_ma_001_d": provenance(2, confidence=0.55, rationale="evaluation focus, abstract missing"),
        },
        split=_split_for(SLICE_MISSING_ABSTRACT, "nlp"),
        primary_slice=SLICE_MISSING_ABSTRACT,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: near_duplicate — near-duplicate candidates that must not dominate
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_NEAR_DUPLICATE = [
    case(
        case_id="ml_disc_nd_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="vision transformer for image classification",
        candidates=(
            candidate("ml_nd_001_a", "An Image is Worth 16x16 Words: Transformers for Image Recognition",
             "We apply a pure Transformer to image classification by splitting images into patches."),
            candidate("ml_nd_001_b", "Vision Transformer (ViT) for Image Classification Tasks",
             "We apply a Transformer to image classification by splitting images into patches, achieving strong results."),  # near-dup of a
            candidate("ml_nd_001_b2", near_duplicate_of="ml_nd_001_b",
             title="ViT: Transformers for Image Recognition at Scale",
             abstract="Splitting images into patches, our Transformer achieves strong image-classification results."),
            candidate("ml_nd_001_c", "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows",
             "A hierarchical Transformer with shifted-window attention for dense prediction."),
            candidate("ml_nd_001_d", "ResNet: Deep Residual Learning for Image Recognition",
             "We introduce residual connections enabling training of very deep CNNs."),
        ),
        judgments={
            "ml_nd_001_a": provenance(3, rationale="canonical ViT paper"),
            "ml_nd_001_b": provenance(2, rationale="near-duplicate of the ViT paper, lower canonical priority"),
            "ml_nd_001_b2": provenance(2, rationale="near-duplicate; same content, secondary source"),
            "ml_nd_001_c": provenance(3, rationale="distinct hierarchical ViT variant"),
            "ml_nd_001_d": provenance(1, rationale="CNN baseline, different architecture family"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "machine_learning"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
    case(
        case_id="bio_disc_nd_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="CRISPR diagnostics with Cas12",
        candidates=(
            candidate("bio_nd_001_a", "DETECTR: DNA Detection with CRISPR-Cas12a",
             "We use Cas12a collateral cleavage for attomolar DNA detection."),
            candidate("bio_nd_001_b", "Cas12a-Based DNA Endonuclease Detection (DETECTR)",
             "Using Cas12a collateral cleavage, we achieve attomolar DNA detection."),  # near-dup of a
            candidate("bio_nd_001_b2", near_duplicate_of="bio_nd_001_b",
             title="CRISPR-Cas12a for Nucleic Acid Detection",
             abstract="Attomolar-sensitive nucleic acid detection using Cas12a collateral cleavage activity."),
            candidate("bio_nd_001_c", "SHERLOCK: Nucleic Acid Detection with Cas13",
             "We use Cas13 for RNA detection via collateral cleavage."),
            candidate("bio_nd_001_d", "Cas14: Targeted Nucleic Acid Detection",
             "We characterize Cas14 for detection of ssDNA."),
        ),
        judgments={
            "bio_nd_001_a": provenance(3, rationale="canonical Cas12 DETECTR diagnostic"),
            "bio_nd_001_b": provenance(2, rationale="near-duplicate of DETECTR, secondary source"),
            "bio_nd_001_b2": provenance(2, rationale="near-duplicate content"),
            "bio_nd_001_c": provenance(3, rationale="distinct Cas13-based diagnostic, relevant"),
            "bio_nd_001_d": provenance(2, rationale="Cas14 diagnostic, adjacent but relevant"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "biomedical"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
    case(
        case_id="nlp_disc_nd_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="evidence_support",
        query="BERT pre-training for language understanding",
        candidates=(
            candidate("nlp_nd_001_a", "BERT: Pre-training of Deep Bidirectional Transformers",
             "We pre-train a bidirectional Transformer for language understanding tasks."),
            candidate("nlp_nd_001_b", "Bidirectional Encoder Representations from Transformers (BERT)",
             "We pre-train a bidirectional Transformer for language understanding."),  # near-dup of a
            candidate("nlp_nd_001_b2", near_duplicate_of="nlp_nd_001_b",
             title="Understanding BERT Pre-training for Language",
             abstract="A bidirectional Transformer is pre-trained for language understanding tasks."),
            candidate("nlp_nd_001_c", "RoBERTa: A Robustly Optimized BERT Pretraining Approach",
             "Improved training recipe for BERT with more data and longer training."),
            candidate("nlp_nd_001_d", "ALBERT: A Lite BERT",
             "Parameter-reduced BERT variant sharing parameters across layers."),
        ),
        judgments={
            "nlp_nd_001_a": provenance(3, rationale="canonical BERT paper"),
            "nlp_nd_001_b": provenance(2, rationale="near-duplicate of BERT, secondary"),
            "nlp_nd_001_b2": provenance(2, rationale="near-duplicate content"),
            "nlp_nd_001_c": provenance(3, rationale="distinct improved BERT variant"),
            "nlp_nd_001_d": provenance(2, rationale="lite BERT variant, relevant"),
        },
        split=_split_for(SLICE_NEAR_DUPLICATE, "nlp"),
        primary_slice=SLICE_NEAR_DUPLICATE,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: source_rank_conflict — high source priority but low relevance
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_SOURCE_RANK_CONFLICT = [
    case(
        case_id="ml_disc_sr_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="state space models for long sequences",
        candidates=(
            candidate("ml_sr_001_a", "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
             "Selective state-space layers enable efficient long-sequence modeling."),
            candidate("ml_sr_001_b", "A Non-Relevant Nature Perspective on AI Funding",
             "An editorial on AI research funding policy."),  # high source rank, irrelevant
            candidate("ml_sr_001_c", "Structured State Spaces for Sequence Modeling (S4)",
             "We introduce structured state-space sequence models."),
            candidate("ml_sr_001_d", "Recurrent Memory Transformers for Long Context",
             "Augmenting Transformers with recurrent memory for long sequences."),
        ),
        judgments={
            "ml_sr_001_a": provenance(3, rationale="directly state-space models for long sequences"),
            "ml_sr_001_b": provenance(0, rationale="editorial/funding topic; high source rank conflicts with relevance", confidence=0.85),
            "ml_sr_001_c": provenance(3, rationale="foundational SSM paper"),
            "ml_sr_001_d": provenance(2, rationale="long-sequence method, adjacent family"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "machine_learning"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
    case(
        case_id="bio_disc_sr_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="CAR-T cell therapy for solid tumors",
        candidates=(
            candidate("bio_sr_001_a", "Overcoming Challenges in CAR-T Therapy for Solid Tumors",
             "We review strategies to improve CAR-T efficacy in solid tumors."),
            candidate("bio_sr_001_b", "A NEJM Perspective on Telemedicine Adoption",
             "Editorial on telemedicine policy, unrelated to CAR-T."),  # high source rank, irrelevant
            candidate("bio_sr_001_c", "Locoregional CAR-T Delivery in Glioblastoma",
             "We deliver CAR-T locally to treat solid brain tumors."),
            candidate("bio_sr_001_d", "Armored CAR-T with Cytokine Secretion",
             "We secrete cytokines from CAR-T to improve solid-tumor activity."),
        ),
        judgments={
            "bio_sr_001_a": provenance(3, rationale="directly CAR-T for solid tumors"),
            "bio_sr_001_b": provenance(0, rationale="telemedicine editorial; source rank conflicts with relevance", confidence=0.85),
            "bio_sr_001_c": provenance(3, rationale="CAR-T clinical study in solid tumor"),
            "bio_sr_001_d": provenance(3, rationale="directly CAR-T engineering for solid tumors"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "biomedical"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
    case(
        case_id="nlp_disc_sr_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="evidence_support",
        query="retrieval-augmented generation evaluation benchmarks",
        candidates=(
            candidate("nlp_sr_001_a", "ARES: Automated RAG Evaluation System",
             "We propose an automated evaluation framework for RAG pipelines."),
            candidate("nlp_sr_001_b", "A Science Perspective on Peer-Review Bias",
             "Editorial on journal peer-review practices."),  # high source rank, irrelevant
            candidate("nlp_sr_001_c", "RGB: A Benchmark for RAG Capabilities",
             "We release a benchmark targeting factual and reasoning facets of RAG."),
            candidate("nlp_sr_001_d", "RAGAS: RAG Assessment Framework",
             "We define faithfulness and relevance metrics for RAG."),
        ),
        judgments={
            "nlp_sr_001_a": provenance(3, rationale="directly RAG evaluation system"),
            "nlp_sr_001_b": provenance(0, rationale="peer-review editorial; source rank conflicts with relevance", confidence=0.85),
            "nlp_sr_001_c": provenance(3, rationale="RAG evaluation benchmark"),
            "nlp_sr_001_d": provenance(3, rationale="RAG assessment metrics"),
        },
        split=_split_for(SLICE_SOURCE_RANK_CONFLICT, "nlp"),
        primary_slice=SLICE_SOURCE_RANK_CONFLICT,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: acronym_vs_expanded — acronym vs expanded term in query
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_ACRONYM_VS_EXPANDED = [
    case(
        case_id="ml_disc_ac_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="RLHF alignment of large language models",
        candidates=(
            candidate("ml_ac_001_a", "Training a Helpful and Harmless Assistant with RLHF",
             "We align large language models using reinforcement learning from human feedback."),
            candidate("ml_ac_001_b", "Direct Preference Optimization as an Alternative to RLHF",
             "DPO removes the reward model from the RLHF pipeline."),
            candidate("ml_ac_001_c", "A Glossary of Reinforcement Learning Terms",
             "We define RL terminology for pedagogical purposes."),  # lexical overlap only
            candidate("ml_ac_001_d", "Constitutional AI: Alignment via Self-Correction",
             "We align models using a written constitution rather than RLHF."),
        ),
        judgments={
            "ml_ac_001_a": provenance(3, rationale="canonical RLHF alignment paper"),
            "ml_ac_001_b": provenance(3, rationale="directly about RLHF alternatives"),
            "ml_ac_001_c": provenance(0, rationale="RL glossary, not alignment"),
            "ml_ac_001_d": provenance(2, rationale="alignment method, distinct from RLHF"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "machine_learning"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
    case(
        case_id="bio_disc_ac_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="ADC antibody-drug conjugates in oncology",
        candidates=(
            candidate("bio_ac_001_a", "Antibody-Drug Conjugates: Principles and Clinical Applications",
             "We review ADC design, linker chemistry, and clinical activity in oncology."),
            candidate("bio_ac_001_b", "Trastuzumab Deruxtecan in HER2-Low Breast Cancer",
             "Phase 3 trial of an ADC in HER2-low tumors."),
            candidate("bio_ac_001_c", "Analog-to-Digital Converter Circuit Design",
             "We design low-power ADC circuits for sensor interfaces."),  # acronym collision, different expansion
            candidate("bio_ac_001_d", "Site-Specific Conjugation for Next-Generation ADCs",
             "We improve ADC homogeneity via site-specific conjugation."),
        ),
        judgments={
            "bio_ac_001_a": provenance(3, rationale="directly antibody-drug conjugates in oncology"),
            "bio_ac_001_b": provenance(3, rationale="clinical ADC study in oncology"),
            "bio_ac_001_c": provenance(0, rationale="electronics ADC (analog-to-digital converter), acronym collision"),
            "bio_ac_001_d": provenance(3, rationale="ADC engineering for oncology"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "biomedical"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
    case(
        case_id="nlp_disc_ac_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="NER named entity recognition methods",
        candidates=(
            candidate("nlp_ac_001_a", "A Neural Architecture for Named Entity Recognition",
             "We propose a BiLSTM-CRF model for NER."),
            candidate("nlp_ac_001_b", "BERT for Named Entity Recognition",
             "We fine-tune BERT for NER across multiple languages."),
            candidate("nlp_ac_001_c", "Near-Earth Resource Mapping from Satellite Imagery",
             "We map near-Earth resources using remote sensing."),  # acronym collision
            candidate("nlp_ac_001_d", "Span-Based Named Entity Recognition",
             "We cast NER as a span-boundary prediction task."),
        ),
        judgments={
            "nlp_ac_001_a": provenance(3, rationale="canonical neural NER method"),
            "nlp_ac_001_b": provenance(3, rationale="NER with BERT, directly relevant"),
            "nlp_ac_001_c": provenance(0, rationale="remote-sensing acronym collision, not NER"),
            "nlp_ac_001_d": provenance(3, rationale="span-based NER method"),
        },
        split=_split_for(SLICE_ACRONYM_VS_EXPANDED, "nlp"),
        primary_slice=SLICE_ACRONYM_VS_EXPANDED,
        secondary_slices=(SLICE_LEXICAL_TRAP,),
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: negated_findings — contradicting/negated results
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_NEGATED_FINDINGS = [
    case(
        case_id="ml_disc_nf_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="evidence_support",
        query="does scaling data improve model performance",
        candidates=(
            candidate("ml_nf_001_a", "Scaling Laws for Neural Language Models",
             "Performance improves predictably with more data, compute, and parameters."),
            candidate("ml_nf_001_b", "When More Data Hurts: Data Quality Trade-offs",
             "We show that naively scaling noisy data degrades model performance."),  # contradicting
            candidate("ml_nf_001_c", "Data Scaling for Vision Transformers",
             "ViTs benefit from large-scale data more than CNNs."),
            candidate("ml_nf_001_d", "Are Scaling Laws Universal? Negative Results",
             "We present settings where standard scaling laws do not hold."),  # negated
        ),
        judgments={
            "ml_nf_001_a": provenance(3, rationale="canonical data-scaling evidence"),
            "ml_nf_001_b": provenance(2, rationale="contradicting boundary case, still about data scaling"),
            "ml_nf_001_c": provenance(2, rationale="domain-specific scaling evidence"),
            "ml_nf_001_d": provenance(2, rationale="negated-findings study, directly relevant to the question"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "machine_learning"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
    case(
        case_id="bio_disc_nf_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="evidence_support",
        query="does metformin reduce cancer incidence",
        candidates=(
            candidate("bio_nf_001_a", "Metformin and Cancer Incidence: A Meta-analysis",
             "Pooled observational data suggest reduced cancer incidence with metformin."),
            candidate("bio_nf_001_b", "Metformin Shows No Effect on Cancer in the MICE Trial",
             "Randomized trial finds no significant reduction in cancer events with metformin."),  # negated
            candidate("bio_nf_001_c", "Metformin Mechanisms in Tumor Metabolism",
             "Preclinical evidence for AMPK-mediated anti-tumor effects."),
            candidate("bio_nf_001_d", "Failure to Reproduce Metformin-Cancer Association",
             "Independent cohort analysis does not confirm prior observational findings."),  # negated
        ),
        judgments={
            "bio_nf_001_a": provenance(3, rationale="meta-analysis directly answering the question"),
            "bio_nf_001_b": provenance(3, rationale="directly relevant RCT, reports null/negated result"),
            "bio_nf_001_c": provenance(2, rationale="mechanism, not incidence evidence"),
            "bio_nf_001_d": provenance(3, rationale="negated-findings replication study, directly on-topic"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "biomedical"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
    case(
        case_id="nlp_disc_nf_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="evidence_support",
        query="does chain-of-thought help on reasoning benchmarks",
        candidates=(
            candidate("nlp_nf_001_a", "Chain-of-Thought Prompting Elicits Reasoning in LLMs",
             "CoT prompting improves accuracy on GSM8K and other reasoning benchmarks."),
            candidate("nlp_nf_001_b", "Chain-of-Thought Fails on Narrow Reasoning Tasks",
             "We find no benefit of CoT on constrained logical-reasoning benchmarks."),  # negated
            candidate("nlp_nf_001_c", "Self-Consistency Improves Chain-of-Thought",
             "Sampling multiple rationales boosts CoT reliability."),
            candidate("nlp_nf_001_d", "When Does Chain-of-Thought Not Help? A Study",
             "We characterize tasks where CoT provides no measurable gain."),  # negated
        ),
        judgments={
            "nlp_nf_001_a": provenance(3, rationale="canonical CoT evidence"),
            "nlp_nf_001_b": provenance(3, rationale="negated-result study, directly on-topic"),
            "nlp_nf_001_c": provenance(2, rationale="extends CoT, adjacent"),
            "nlp_nf_001_d": provenance(3, rationale="directly studies when CoT fails"),
        },
        split=_split_for(SLICE_NEGATED_FINDINGS, "nlp"),
        primary_slice=SLICE_NEGATED_FINDINGS,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: exact_identifier — query contains an exact named entity/paper
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_EXACT_IDENTIFIER = [
    case(
        case_id="ml_disc_ei_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="literature_mapping",
        query="ResNet",
        candidates=(
            candidate("ml_ei_001_a", "Deep Residual Learning for Image Recognition (ResNet)",
             "We introduce residual connections enabling training of very deep networks."),
            candidate("ml_ei_001_b", "Identity Mappings in Deep Residual Networks",
             "We analyze identity mappings that improve ResNet training."),
            candidate("ml_ei_001_c", "ResNeXt: Aggregated Residual Transformations",
             "We extend ResNet with grouped convolutions."),
            candidate("ml_ei_001_d", "Wide Residual Networks",
             "We widen ResNet to improve accuracy per parameter."),
        ),
        judgments={
            "ml_ei_001_a": provenance(3, rationale="exact ResNet paper"),
            "ml_ei_001_b": provenance(2, rationale="analyzes ResNet identity mappings"),
            "ml_ei_001_c": provenance(2, rationale="ResNet variant"),
            "ml_ei_001_d": provenance(2, rationale="ResNet variant"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "machine_learning"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
    ),
    case(
        case_id="bio_disc_ei_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="literature_mapping",
        query="AlphaFold",
        candidates=(
            candidate("bio_ei_001_a", "AlphaFold: Highly Accurate Protein Structure Prediction",
             "AlphaFold predicts protein structures with atomic accuracy."),
            candidate("bio_ei_001_b", "AlphaFold-Multimer: Complex Prediction",
             "We extend AlphaFold to predict multi-chain complexes."),
            candidate("bio_ei_001_c", "Highly Accurate Protein Structure Prediction with AlphaFold",
             "AlphaFold demonstrates near-experimental accuracy in CASP14."),  # near-dup-ish but distinct enough
            candidate("bio_ei_001_d", "ESMFold: Fast Protein Structure Prediction",
             "A language-model-based structure predictor, distinct from AlphaFold."),
        ),
        judgments={
            "bio_ei_001_a": provenance(3, rationale="exact AlphaFold paper"),
            "bio_ei_001_b": provenance(3, rationale="AlphaFold extension by same lineage"),
            "bio_ei_001_c": provenance(2, rationale="re-coverage of AlphaFold, secondary source"),
            "bio_ei_001_d": provenance(1, rationale="different system, not AlphaFold"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "biomedical"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
    ),
    case(
        case_id="nlp_disc_ei_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="literature_mapping",
        query="GPT-3",
        candidates=(
            candidate("nlp_ei_001_a", "Language Models are Few-Shot Learners (GPT-3)",
             "GPT-3 demonstrates strong few-shot performance across NLP tasks."),
            candidate("nlp_ei_001_b", "GPT-4 Technical Report",
             "We report GPT-4 capabilities and evaluation results."),
            candidate("nlp_ei_001_c", "Evaluating GPT-3 on Mathematical Word Problems",
             "We benchmark GPT-3 on grade-school math problems."),
            candidate("nlp_ei_001_d", "What Does GPT-3 Know About the World?",
             "We probe GPT-3 for factual and commonsense knowledge."),
        ),
        judgments={
            "nlp_ei_001_a": provenance(3, rationale="exact GPT-3 paper"),
            "nlp_ei_001_b": provenance(2, rationale="successor model report, GPT-4"),
            "nlp_ei_001_c": provenance(2, rationale="evaluates GPT-3 on a specific task"),
            "nlp_ei_001_d": provenance(2, rationale="probes GPT-3 knowledge"),
        },
        split=_split_for(SLICE_EXACT_IDENTIFIER, "nlp"),
        primary_slice=SLICE_EXACT_IDENTIFIER,
    ),
]


# ════════════════════════════════════════════════════════════════════
# Slice: neutral — non-adversarial baseline cases
# ════════════════════════════════════════════════════════════════════

_DISCOVERY_NEUTRAL = [
    case(
        case_id="ml_disc_nt_001",
        domain="machine_learning",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="image segmentation with transformers",
        candidates=(
            candidate("ml_nt_001_a", "Segment Anything (SAM)",
             "We introduce a foundation model for promptable image segmentation."),
            candidate("ml_nt_001_b", "Mask2Former for Universal Image Segmentation",
             "A masked-transformer architecture unifying segmentation tasks."),
            candidate("ml_nt_001_c", "U-Net for Biomedical Image Segmentation",
             "A CNN architecture widely used for biomedical segmentation."),
            candidate("ml_nt_001_d", "Panoptic Segmentation with DETR",
             "We cast panoptic segmentation as a set-prediction problem."),
        ),
        judgments={
            "ml_nt_001_a": provenance(3, rationale="directly transformer-based segmentation foundation model"),
            "ml_nt_001_b": provenance(3, rationale="transformer segmentation architecture"),
            "ml_nt_001_c": provenance(2, rationale="CNN segmentation, adjacent family"),
            "ml_nt_001_d": provenance(3, rationale="transformer panoptic segmentation"),
        },
        split=_split_for(SLICE_NEUTRAL, "machine_learning"),
        primary_slice=SLICE_NEUTRAL,
    ),
    case(
        case_id="bio_disc_nt_001",
        domain="biomedical",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="spatial transcriptomics methods",
        candidates=(
            candidate("bio_nt_001_a", "10x Visium Spatial Transcriptomics",
             "We profile gene expression across tissue sections at near-cellular resolution."),
            candidate("bio_nt_001_b", "Slide-seq: Scalable Spatial Transcriptomics",
             "We deposit RNA onto bead arrays for spatial barcoding."),
            candidate("bio_nt_001_c", "Stereo-seq at Cellular Resolution",
             "Large-field spatial transcriptomics at sub-cellular resolution."),
            candidate("bio_nt_001_d", "Cell2location: Spatial Single-Cell Resolution",
             "We deconvolve cell types from spatial transcriptomics data."),
        ),
        judgments={
            "bio_nt_001_a": provenance(3, rationale="canonical spatial transcriptomics platform"),
            "bio_nt_001_b": provenance(3, rationale="spatial transcriptomics method"),
            "bio_nt_001_c": provenance(3, rationale="spatial transcriptomics at sub-cellular resolution"),
            "bio_nt_001_d": provenance(2, rationale="analysis method on top of spatial data"),
        },
        split=_split_for(SLICE_NEUTRAL, "biomedical"),
        primary_slice=SLICE_NEUTRAL,
    ),
    case(
        case_id="nlp_disc_nt_001",
        domain="nlp",
        surface="discovery_ranking",
        intent="general_research_relevance",
        query="semantic parsing for question answering",
        candidates=(
            candidate("nlp_nt_001_a", "Spider: A Large Human-Labeled Dataset for Semantic Parsing",
             "We release a benchmark for complex, cross-database semantic parsing."),
            candidate("nlp_nt_001_b", "Grammar-Constrained Semantic Parsing with Transformers",
             "We decode into grammatical logical forms for question answering."),
            candidate("nlp_nt_001_c", "Neural Semantic Parsing over Knowledge Graphs",
             "We translate natural-language questions into KG queries."),
            candidate("nlp_nt_001_d", "Weakly Supervised Semantic Parsing",
             "We train semantic parsers from denotations rather than logical forms."),
        ),
        judgments={
            "nlp_nt_001_a": provenance(2, rationale="benchmark for semantic parsing, relevant"),
            "nlp_nt_001_b": provenance(3, rationale="semantic parsing method for QA"),
            "nlp_nt_001_c": provenance(3, rationale="semantic parsing over KG for QA"),
            "nlp_nt_001_d": provenance(2, rationale="semantic parsing training, adjacent"),
        },
        split=_split_for(SLICE_NEUTRAL, "nlp"),
        primary_slice=SLICE_NEUTRAL,
    ),
]



