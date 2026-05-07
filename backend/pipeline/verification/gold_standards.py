"""Gold-standard gap lists for pipeline quality evaluation.

Domain-specific lists of known research gaps that a high-quality pipeline
should detect. Used by PipelineEvaluator to compute recall.
"""
from __future__ import annotations

GOLD_STANDARD_GAPS: dict[str, list[str]] = {
    "AI/NLP": [
        "hallucination detection and mitigation in large language models",
        "efficient fine-tuning methods for domain adaptation",
        "multilingual reasoning and cross-lingual transfer",
        "long-context understanding beyond transformer windows",
        "bias measurement and debiasing in generative models",
        "robustness to adversarial prompts and jailbreaking",
        "structured output generation with formal verification",
        "knowledge grounding and factual consistency",
    ],
    "AI/Reasoning": [
        "theoretical foundations for graph reasoning topology",
        "cost efficiency trade-offs in structured reasoning",
        "knowledge graph integration with LLM reasoning",
        "explainability of graph-based reasoning paths",
        "standardized evaluation benchmarks for neuro-symbolic",
        "cascading error mitigation in dual-process systems",
        "temporal reasoning over evolving knowledge",
        "cross-domain generalization of reasoning methods",
    ],
    "Biomedical": [
        "drug-drug interaction prediction from molecular structure",
        "clinical trial design optimization with causal inference",
        "patient trajectory modeling from longitudinal EHR data",
        "protein structure prediction for novel fold discovery",
        "medical image analysis with limited labeled data",
        "gene-disease association with multi-omics integration",
        "real-time adverse event detection from clinical notes",
        "personalized treatment recommendation from biomarkers",
    ],
    "Computer Science": [
        "energy-efficient training methods for large models",
        "formal verification of neural network behavior",
        "hardware-software co-design for inference acceleration",
        "distributed consensus in heterogeneous edge networks",
        "automated program repair from bug reports",
        "quantum-classical hybrid algorithm design",
        "privacy-preserving federated learning guarantees",
        "compiler optimization for emerging architectures",
    ],
}


def get_gold_gaps(domain: str) -> list[str]:
    """Get gold-standard gaps for a domain.

    Falls back to AI/NLP if domain not found.
    """
    # Try exact match first
    if domain in GOLD_STANDARD_GAPS:
        return GOLD_STANDARD_GAPS[domain]

    # Try prefix match (e.g., "AI/NLP" matches "AI/NLP")
    for key in GOLD_STANDARD_GAPS:
        if key.lower() in domain.lower() or domain.lower() in key.lower():
            return GOLD_STANDARD_GAPS[key]

    # Default fallback
    return GOLD_STANDARD_GAPS["AI/NLP"]
