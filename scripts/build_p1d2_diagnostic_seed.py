"""P1D.2b seed builder: author the 9-case diagnostic vertical slice.

Generates the diagnostic seed corpus, cases, and judgments from a single
authoritative source so that every passage reference is structurally
guaranteed to resolve to real text with a real hash. Re-running this script
reproduces all artifacts deterministically.

Design principle: the corpus text is the source of truth. Passages are
EXTRACTED by (document_id, char_start, char_end), never hand-written inside
a case record. Hashes are computed over the extracted text, not asserted.

Outputs:
  docs/retrieval/p1d2_diagnostic_seed_sources.jsonl
  docs/retrieval/p1d2_diagnostic_seed_cases.jsonl
  docs/retrieval/p1d2_diagnostic_seed_judgments.jsonl
  docs/retrieval/p1d2_diagnostic_seed_manifest.json

DRAFT (status: draft) - NOT frozen, no gate closed. Provisional judgments only.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTDIR = REPO / "docs" / "retrieval"

SCHEMA_VERSION_CASE = "p1d2_case_schema_v1"
SCHEMA_VERSION_JUDGMENT = "p1d2_judgment_schema_v1"
SEAL_DATE = "2026-07-22 (draft; not sealed)"
CASE_AUTHOR_ID = "author_seed_agent"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ────────────────────────────────────────────────────────────────────
# SOURCE CORPUS
# Real full-text synthetic_realistic documents. Each carries an explicit
# section structure so passages can be located by exact character offsets.
# ────────────────────────────────────────────────────────────────────

def doc(doc_id: str, title: str, abstract: str, body: str, *, lineage: str,
        domain: str, license_basis: str = "synthetic_public_abstract_style") -> dict:
    full = f"Title: {title}\n\nAbstract: {abstract}\n\n{body}"
    return {
        "document_id": doc_id,
        "document_version": "v1",
        "title": title,
        "domain": domain,
        "full_text": full,
        "document_content_hash": sha256(full),
        "evidence_lineage_id": lineage,
        "source_access_or_license_basis": license_basis,
    }


CORPUS = [
    # ── Lineage: metformin-oncology (the metformin/cancer question) ──
    doc("doc_metformin_meta", "Metformin and Cancer Incidence: A Meta-analysis",
        "Pooled observational data suggest reduced cancer incidence with metformin use in type 2 diabetes patients.",
        "Methods: We pooled 12 observational cohorts. Results: The pooled analysis showed a reduced incidence of colorectal and hepatocellular carcinoma in metformin users compared to other antidiabetics (pooled RR 0.73, 95% CI 0.61-0.88). Discussion: These observational findings are subject to confounding by indication and require randomized confirmation.",
        lineage="elin_metformin_oncology", domain="biomedical"),
    doc("doc_metformin_mice", "Metformin Shows No Effect on Cancer in the MICE Trial",
        "A randomized trial finds no significant reduction in cancer events with metformin in non-diabetic patients at high cancer risk.",
        "Methods: We randomized 8191 non-diabetic patients to metformin or placebo. Results: Cancer events did not differ between arms (HR 1.01, 95% CI 0.84-1.21; p=0.9). Discussion: Our randomized findings do not support a chemopreventive effect of metformin in non-diabetic patients, in contrast to prior observational signals.",
        lineage="elin_metformin_oncology", domain="biomedical"),
    doc("doc_metformin_repro", "Failure to Reproduce Metformin-Cancer Association",
        "An independent cohort analysis does not confirm the prior observational association between metformin and reduced cancer incidence.",
        "Methods: We re-analyzed a UK primary-care cohort of 42311 patients. Results: After adjusting for time-varying confounders, metformin exposure was not associated with cancer incidence (adjusted HR 0.99, 95% CI 0.93-1.05). Discussion: The originally reported association likely reflects uncontrolled confounding rather than a causal chemopreventive effect.",
        lineage="elin_metformin_oncology", domain="biomedical"),

    # ── Lineage: SGLT2 / GLP-1 cardiometabolic (distinct from metformin lineage) ──
    doc("doc_empagliflozin", "Empagliflozin and Glycemic Outcomes (EMPA-REG)",
        "We report SGLT2 inhibitor effects on glycemia and cardiovascular outcomes in type 2 diabetes.",
        "Methods: Randomized 7020 patients to empagliflozin or placebo. Results: Empagliflozin reduced cardiovascular death (HR 0.62, 95% CI 0.49-0.77) and modestly reduced HbA1c. Discussion: SGLT2 inhibition confers cardiovascular benefit independent of glycemic improvement.",
        lineage="elin_sglt2_glpl1_cardiometabolic", domain="biomedical"),

    # ── Lineage: PCSK9 (for agenda-mismatch / same-intervention-wrong-outcome) ──
    doc("doc_pcsk9_ldl", "PCSK9 Monoclonal Antibodies for Hypercholesterolemia",
        "We review PCSK9 inhibitors for LDL-C lowering in hypercholesterolemia.",
        "Methods: Systematic review of trials. Results: PCSK9 inhibitors reduce LDL-C by approximately 60%. Discussion: PCSK9 inhibition is a potent LDL-lowering strategy; cardiovascular outcome trials are ongoing to establish event reduction.",
        lineage="elin_pcsk9_lipid", domain="biomedical"),
    doc("doc_pcsk9_cv", "Alirocumab and Cardiovascular Events (ODYSSEY OUTCOMES)",
        "A phase 3 trial of the PCSK9 inhibitor alirocumab in patients after acute coronary syndrome.",
        "Methods: Randomized 18924 patients to alirocumab or placebo. Results: Alirocumab reduced the composite of cardiovascular death, myocardial infarction, or stroke (HR 0.85, 95% CI 0.78-0.93). Discussion: PCSK9 inhibition reduces cardiovascular events in high-risk patients already on statin therapy.",
        lineage="elin_pcsk9_lipid", domain="biomedical"),

    # ── Lineage: contrastive-ligature / ML method-vs-application ──
    doc("doc_simclr", "SimCLR: A Simple Framework for Contrastive Learning",
        "We introduce a contrastive loss based on InfoNCE over augmented views for self-supervised representation learning.",
        "Methods: We maximize agreement between augmentations of the same image under a base encoder with a projection head. Results: SimCLR achieves state-of-the-art on ImageNet linear-eval. Discussion: The contrastive loss formulation is the core contribution; the encoder architecture is interchangeable.",
        lineage="elin_contrastive_method", domain="machine_learning"),
    doc("doc_simclr_medical_app", "Applying Contrastive Features to Medical Image Classification",
        "We fine-tune contrastive features for downstream medical imaging classification.",
        "Methods: We initialize from a contrastive encoder and fine-tune on chest radiograph labels. Results: Transfer improves AUC by 3 points over ImageNet pre-training. Discussion: Self-supervised features transfer well to medical imaging, but this work is an application of an existing method rather than a new contrastive loss.",
        lineage="elin_contrastive_application", domain="machine_learning"),

    # ── Lineage: efficient LLM training (semantic paraphrase) ──
    doc("doc_zero", "Efficient Memory Management for Large Language Model Training",
        "ZeRO partitions optimizer states across devices to reduce the memory footprint of gigantic models.",
        "Methods: We partition optimizer states, gradients, and parameters across data-parallel workers. Results: ZeRO enables training models with over 100 billion parameters on 400 GPUs. Discussion: The technique addresses the memory bottleneck that limits training very large models, complementing pipeline and tensor parallelism.",
        lineage="elin_efficient_training", domain="machine_learning"),

    # ── Lineage: RLHF / instruction-following (exact identifier) ──
    doc("doc_instructgpt", "Training Language Models to Follow Instructions with Human Feedback",
        "We fine-tune large models using reinforcement learning from human feedback to align outputs with user intent.",
        "Methods: Three-stage pipeline: supervised fine-tuning, reward model training, and PPO optimization on the reward model. Results: The resulting model produces more helpful and aligned responses than the base model. Discussion: RLHF is an effective method for aligning language models to follow human instructions.",
        lineage="elin_rlhf", domain="machine_learning"),

    # ── Lineage: ADC / antibody-drug conjugates (acronym collision) ──
    doc("doc_adc_oncology", "Antibody-Drug Conjugates: Principles and Clinical Applications",
        "We review ADC design, linker chemistry, and clinical activity in oncology.",
        "Methods: Narrative review of approved and investigational ADCs. Results: ADCs like trastuzumab deruxtecan show activity in HER2-low breast cancer. Discussion: The antibody delivers a cytotoxic payload selectively to tumor cells expressing the target antigen; this is distinct from ADC circuits in electronics.",
        lineage="elin_adc_oncology", domain="biomedical"),
    doc("doc_adc_electronics", "Analog-to-Digital Converter Circuit Design",
        "We design low-power ADC circuits for sensor interfaces.",
        "Methods: Successive-approximation-register architecture in 28nm CMOS. Results: The converter achieves 12-bit resolution at 1 MS/s with 0.8 mW power. Discussion: This analog-to-digital converter (ADC) has no relation to antibody-drug conjugates; the shared acronym is coincidental.",
        lineage="elin_adc_electronics", domain="machine_learning", license_basis="synthetic_electronics_context"),

    # ── Lineage: psilocybin depression (review vs primary) ──
    doc("doc_psilocybin_jama", "Psilocybin Therapy for Treatment-Resistant Depression (JAMA Psychiatry)",
        "A randomized trial shows rapid antidepressant effects of psilocybin in treatment-resistant depression.",
        "Methods: We randomized 59 patients to psilocybin or escitalopram. Results: Psilocybin produced a rapid reduction in depression scores at week 6. Discussion: This randomized evidence supports a rapid antidepressant effect of psilocybin, though the comparator arm limits blinding.",
        lineage="elin_psilocybin_primary", domain="biomedical"),
    doc("doc_psilocybin_review", "Psychedelics in Psychiatry: A Narrative Review",
        "We synthesize evidence on psychedelic-assisted therapy.",
        "Methods: Narrative review across trials of serotonergic psychedelics. Results: The evidence base is growing but dominated by small, open-label studies. Discussion: While promising, the field requires larger randomized trials; this review aggregates rather than reports primary data.",
        lineage="elin_psilocybin_review", domain="biomedical"),

    # ── Lineage: low-resource NMT (semantic paraphrase, NLP) ──
    doc("doc_transfer_nmt", "Improving Low-Resource Neural MT with Transfer Learning",
        "We pre-train on high-resource pairs and transfer to low-resource languages.",
        "Methods: We initialize a low-resource encoder-decoder from a high-resource model and fine-tune. Results: BLEU improves by 4.1 points on Swahili-English. Discussion: Transfer learning substantially narrows the performance gap for low-resource translation directions.",
        lineage="elin_low_resource_nmt", domain="nlp"),

    # ── Lineage: graph neural networks (multi-paper synthesis, single lab) ──
    doc("doc_gcn_kipf", "Semi-Supervised Classification with Graph Convolutional Networks",
        "We introduce graph convolutional networks for node classification.",
        "Methods: A spectral graph convolution approximated by Chebyshev polynomials. Results: The GCN achieves state-of-the-art on citation networks. Discussion: The layer-wise propagation rule is the core architectural contribution.",
        lineage="elin_gnn_amsterdam", domain="machine_learning"),
    doc("doc_graphsage", "GraphSAGE: Inductive Learning on Large Graphs",
        "We sample and aggregate neighborhoods inductively for large-graph learning.",
        "Methods: Neighborhood sampling with learned aggregators. Results: GraphSAGE predicts unseen node embeddings. Discussion: Unlike transductive GCN, GraphSAGE generalizes to unseen nodes.",
        lineage="elin_gnn_amsterdam", domain="machine_learning"),

    # ── Lineage: independent GNN work (Stanford, distinct lineage) ──
    doc("doc_gat", "Graph Attention Networks (GAT)",
        "We apply attention over graph neighborhoods for node classification.",
        "Methods: Masked self-attention layers compute node embeddings by attending over neighbors. Results: GAT matches or exceeds GCN on benchmark datasets. Discussion: Attention weights are learned and provide interpretability.",
        lineage="elin_gnn_stanford", domain="machine_learning"),

    # ── Lineage: dose scaling (false-support trap: supportive wording) ──
    doc("doc_dose_scaling_review", "Scaling Laws for Neural Language Models: A Survey",
        "We survey scaling laws and their implications for model performance.",
        "Methods: Narrative synthesis of scaling-law literature. Results: The survey notes that performance generally improves with scale, but emphasizes that scaling alone is neither necessary nor sufficient for safety. Discussion: This is a synthesis of prior work, not a primary scaling study; it discusses but does not directly demonstrate the scaling-safety relationship.",
        lineage="elin_scaling_survey", domain="machine_learning"),
    doc("doc_inverse_scaling", "Inverse Scaling: When Bigger Is Worse",
        "We identify tasks where larger models perform worse, including some safety-relevant tasks.",
        "Methods: We evaluate model size against task performance across a curated benchmark. Results: On several tasks, performance degrades with scale. Discussion: This is direct primary evidence that scaling can worsen safety-relevant capabilities.",
        lineage="elin_scaling_primary", domain="machine_learning"),
]

CORPUS_BY_ID = {d["document_id"]: d for d in CORPUS}


def passage(doc_id: str, char_start: int, char_end: int, section_id: str) -> dict:
    """Extract a real passage by offset from a real document; compute its hash."""
    d = CORPUS_BY_ID[doc_id]
    text = d["full_text"][char_start:char_end]
    return {
        "document_id": doc_id,
        "document_version": d["document_version"],
        "section_id": section_id,
        "passage_id": f"{doc_id}_{char_start}_{char_end}",
        "passage_locator": f"chars {char_start}-{char_end}",
        "passage_text": text,
        "passage_text_hash": sha256(text),
        "document_content_hash": d["document_content_hash"],
        "source_access_or_license_basis": d["source_access_or_license_basis"],
        "evidence_lineage_id": d["evidence_lineage_id"],
    }


def locate(doc_id: str, needle: str) -> tuple[int, int]:
    """Find a substring and return its (start, end) offsets; raises if absent."""
    d = CORPUS_BY_ID[doc_id]
    s = d["full_text"].index(needle)
    return (s, s + len(needle))


def query_semantic_fp(query: str) -> str:
    """Canonical semantic fingerprint of a query (lowercased, whitespace-normalized)."""
    return sha256(" ".join(query.lower().split()))


def positive_unit_fp(doc_id: str, char_start: int, char_end: int) -> str:
    return passage(doc_id, char_start, char_end, "results")["passage_text_hash"]


# ────────────────────────────────────────────────────────────────────
# PASSAGES (extracted by real offsets, hashes computed, not asserted)
# ────────────────────────────────────────────────────────────────────

def P(doc_id: str, needle: str, section: str = "results") -> dict:
    s, e = locate(doc_id, needle)
    return passage(doc_id, s, e, section)


PASSAGES = {}

# evidence_retrieval — metformin-cancer (false support central trap)
PASSAGES["er1_pos"] = P("doc_metformin_meta", "pooled analysis showed a reduced incidence of colorectal and hepatocellular carcinoma in metformin users")
PASSAGES["er1_false_support"] = P("doc_metformin_meta", "These observational findings are subject to confounding by indication", "discussion")

# evidence_retrieval — empagliflozin (supportive but different outcome)
PASSAGES["er2_pos"] = P("doc_empagliflozin", "Empagliflozin reduced cardiovascular death")
PASSAGES["er2_wrong_outcome"] = P("doc_empagliflozin", "modestly reduced HbA1c")

# contradiction_retrieval — metformin MICE (direct negation)
PASSAGES["cr1_pos"] = P("doc_metformin_mice", "Cancer events did not differ between arms")
PASSAGES["cr1_qualifier"] = P("doc_metformin_repro", "metformin exposure was not associated with cancer incidence")

# contradiction_retrieval — psilocybin (qualifier, not direct negation)
PASSAGES["cr2_pos"] = P("doc_psilocybin_jama", "Psilocybin produced a rapid reduction in depression scores")
PASSAGES["cr2_qualifier"] = P("doc_psilocybin_jama", "the comparator arm limits blinding", "discussion")

# multi_paper_synthesis — GNN Amsterdam (same lineage, 2 papers) vs Stanford (independent)
PASSAGES["mps1a_kipf"] = P("doc_gcn_kipf", "The layer-wise propagation rule is the core architectural contribution", "discussion")
PASSAGES["mps1b_graphsage"] = P("doc_graphsage", "GraphSAGE predicts unseen node embeddings")
PASSAGES["mps1c_gat"] = P("doc_gat", "GAT matches or exceeds GCN on benchmark datasets")

# multi_paper_synthesis — scaling (one survey vs one primary; different lineages)
PASSAGES["mps2a_survey"] = P("doc_dose_scaling_review", "performance generally improves with scale, but emphasizes that scaling alone is neither necessary nor sufficient for safety")
PASSAGES["mps2b_primary"] = P("doc_inverse_scaling", "performance degrades with scale")

# paper_discovery — low-resource NMT
PASSAGES["pd1_pos"] = P("doc_transfer_nmt", "Transfer learning substantially narrows the performance gap for low-resource translation directions", "discussion")

# method_retrieval — contrastive loss (method vs application)
PASSAGES["mr1_method"] = P("doc_simclr", "maximize agreement between augmentations of the same image under a base encoder with a projection head", "methods")
PASSAGES["mr1_application"] = P("doc_simclr_medical_app", "Transfer improves AUC by 3 points over ImageNet pre-training")

# research_gap_analysis — RLHF (agenda: helpfulness vs safety)
PASSAGES["rga1_on_topic"] = P("doc_instructgpt", "The resulting model produces more helpful and aligned responses than the base model")

PASSAGES_BY_ID = {p["passage_id"]: p for p in PASSAGES.values()}


# ────────────────────────────────────────────────────────────────────
# JUDGMENTS (all provisional, single-pass, non-scoreable, non-sealable)
# Defined BEFORE cases so each case can inline its full judgment objects.
# ────────────────────────────────────────────────────────────────────

def judgment(jid, case_id, passage_key, grade, rationale, *, unit_type="passage",
             topical=3, evidence=3, method=3, confidence=0.7) -> dict:
    p = PASSAGES[passage_key]
    return {
        "schema_version": SCHEMA_VERSION_JUDGMENT,
        "judgment_id": jid,
        "case_id": case_id,
        "unit_id": p["passage_id"],
        "unit_type": unit_type,
        "unit_text_hash": p["passage_text_hash"],
        "research_utility_grade": grade,
        "topical_relevance": topical,
        "evidence_utility": evidence,
        "methodological_fit": method,
        "review_status": "provisional",
        "decision_basis": "single_pass_provisional",
        "requires_external_dual_review": True,
        "eligible_for_scoring": False,
        "eligible_for_seal": False,
        "case_author_id": CASE_AUTHOR_ID,
        "policy_outputs_visible_to_reviewers": False,
        "annotation_confidence": confidence,
        "_rationale": rationale,  # human-readable; stripped from machine file, kept for review md
    }


JUDGMENTS = [
    judgment("jdg_diag_er_001_er1_pos", "diag_er_001", "er1_pos", 3,
             "Directly reports reduced incidence; supports the claim's positive form."),
    judgment("jdg_diag_er_001_er1_false_support", "diag_er_001", "er1_false_support", 1,
             "Same-paper caveat revealing the result is observational/confounded; grade 1 as standalone evidence of the claim.",
             evidence=1, confidence=0.8),

    judgment("jdg_diag_er_002_er2_pos", "diag_er_002", "er2_pos", 3,
             "Directly reports cardiovascular benefit; on-outcome."),
    judgment("jdg_diag_er_002_er2_wrong_outcome", "diag_er_002", "er2_wrong_outcome", 1,
             "Glycemic result, wrong outcome for a cardiovascular query; agenda mismatch.",
             evidence=1, confidence=0.85),

    judgment("jdg_diag_cr_001_cr1_pos", "diag_cr_001", "cr1_pos", 3,
             "Direct null result contradicting the claim; the target contradiction."),
    judgment("jdg_diag_cr_001_cr1_qualifier", "diag_cr_001", "cr1_qualifier", 3,
             "Independent non-reproduction; second contradicting source."),

    judgment("jdg_diag_cr_002_cr2_pos", "diag_cr_002", "cr2_pos", 3,
             "The claimed effect; context for what is being qualified."),
    judgment("jdg_diag_cr_002_cr2_qualifier", "diag_cr_002", "cr2_qualifier", 3,
             "Genuine methodological qualifier (blinding limitation); the qualifying passage sought."),

    judgment("jdg_diag_mps_001_mps1a", "diag_mps_001", "mps1a_kipf", 3,
             "Amsterdam lineage, foundational; must appear."),
    judgment("jdg_diag_mps_001_mps1b", "diag_mps_001", "mps1b_graphsage", 2,
             "Amsterdam lineage, distinct method but same lineage; relevant but redundant for diversity."),
    judgment("jdg_diag_mps_001_mps1c", "diag_mps_001", "mps1c_gat", 3,
             "Stanford lineage, independent; the case for diversity rests on this being represented."),

    judgment("jdg_diag_mps_002_mps2b", "diag_mps_002", "mps2b_primary", 3,
             "Primary inverse-scaling evidence; must appear for a balanced synthesis."),
    judgment("jdg_diag_mps_002_mps2a", "diag_mps_002", "mps2a_survey", 2,
             "Survey lineage; relevant but a synthesis that returns only this misses the primary negative result."),

    judgment("jdg_diag_pd_001_pd1_pos", "diag_pd_001", "pd1_pos", 3,
             "Directly addresses low-resource MT improvement; low lexical overlap with query.",
             confidence=0.75),

    judgment("jdg_diag_mr_001_mr1_method", "diag_mr_001", "mr1_method", 3,
             "Defines the contrastive loss; the method sought."),
    judgment("jdg_diag_mr_001_mr1_application", "diag_mr_001", "mr1_application", 2,
             "Application of the method; agenda mismatch (application vs definition).",
             method=2, confidence=0.8),

    judgment("jdg_diag_rga_001_rga1", "diag_rga_001", "rga1_on_topic", 2,
             "Addresses helpfulness/alignment broadly; agenda-adjacent but not the safety outcome asked.",
             evidence=2, confidence=0.7),
]

JUDGMENTS_BY_CASE: dict[str, list[dict]] = {}
for j in JUDGMENTS:
    JUDGMENTS_BY_CASE.setdefault(j["case_id"], []).append(j)


# ────────────────────────────────────────────────────────────────────
# CASES (judgments inlined as full objects per schema $ref)
# ────────────────────────────────────────────────────────────────────

def case(case_id, task_family, domain, query, retrieved_unit, risk_labels, hard_neg_types,
         pos_passage_keys, hard_neg_keys, rationale, origin_provenance, scenario_id,
         leakage_group, document_family, contradiction_keys=None, false_support_keys=None,
         agenda_mismatch_keys=None, alt_keys=None) -> dict:
    pos_ids = [PASSAGES[k]["passage_id"] for k in pos_passage_keys]
    hard_neg_ids = []
    for k in hard_neg_keys:
        if k in PASSAGES:
            hard_neg_ids.append(PASSAGES[k]["passage_id"])
        else:
            hard_neg_ids.append(k)  # document_id-level negative

    # inline full judgment objects (stripped of the _rationale helper field)
    case_judgments = [{kk: vv for kk, vv in j.items() if kk != "_rationale"}
                      for j in JUDGMENTS_BY_CASE.get(case_id, [])]

    c = {
        "schema_version": SCHEMA_VERSION_CASE,
        "case_id": case_id,
        "benchmark_role": "diagnostic",
        "task_family": task_family,
        "research_domain": domain,
        "query_or_claim": query,
        "retrieved_unit": retrieved_unit,
        "source_document_ids": sorted({PASSAGES[k]["document_id"] for k in pos_passage_keys} | {PASSAGES[k]["document_id"] for k in hard_neg_keys if k in PASSAGES}),
        "positive_passage_ids": pos_ids,
        "hard_topical_negatives": hard_neg_ids,
        "relevance_judgments": case_judgments,
        "risk_labels": risk_labels,
        "hard_negative_types": hard_neg_types,
        "annotation_rationale": rationale,
        "case_origin": "synthetic_realistic",
        "origin_provenance": origin_provenance,
        "deidentification_status": "not_applicable_synthetic",
        "case_author_id": CASE_AUTHOR_ID,
        "review_status": "provisional",
        "leakage_group_id": leakage_group,
        "document_family_id": document_family,
        "query_semantic_fingerprint": query_semantic_fp(query),
        "positive_unit_fingerprint": PASSAGES[pos_passage_keys[0]]["passage_text_hash"],
        "synthetic_scenario_id": scenario_id,
        "passages": {p["passage_id"]: {k: v for k, v in p.items() if k != "passage_text"} for p in [PASSAGES[k] for k in pos_passage_keys]},
    }
    if contradiction_keys:
        c["contradicting_or_qualifying_passages"] = [PASSAGES[k]["passage_id"] for k in contradiction_keys]
        for k in contradiction_keys:
            c["passages"][PASSAGES[k]["passage_id"]] = {kk: vv for kk, vv in PASSAGES[k].items() if kk != "passage_text"}
    if false_support_keys:
        c["false_support_negatives"] = [PASSAGES[k]["passage_id"] for k in false_support_keys]
        for k in false_support_keys:
            c["passages"][PASSAGES[k]["passage_id"]] = {kk: vv for kk, vv in PASSAGES[k].items() if kk != "passage_text"}
    if agenda_mismatch_keys:
        c["agenda_mismatch_negatives"] = [PASSAGES[k]["passage_id"] for k in agenda_mismatch_keys]
        for k in agenda_mismatch_keys:
            c["passages"][PASSAGES[k]["passage_id"]] = {kk: vv for kk, vv in PASSAGES[k].items() if kk != "passage_text"}
    if alt_keys:
        c["acceptable_alternate_passages"] = [PASSAGES[k]["passage_id"] for k in alt_keys]
        for k in alt_keys:
            c["passages"][PASSAGES[k]["passage_id"]] = {kk: vv for kk, vv in PASSAGES[k].items() if kk != "passage_text"}
    for k in hard_neg_keys:
        if k in PASSAGES:
            c["passages"][PASSAGES[k]["passage_id"]] = {kk: vv for kk, vv in PASSAGES[k].items() if kk != "passage_text"}
    return c


CASES = [
    # ── evidence_retrieval 1: metformin-cancer, false support central ──
    case("diag_er_001", "evidence_retrieval", "biomedical",
         "Find a passage showing metformin reduces cancer incidence.",
         "passage", ["false_support"], ["supportive_language_without_support"],
         pos_passage_keys=["er1_pos"],
         false_support_keys=["er1_false_support"],
         hard_neg_keys=["er1_false_support"],
         rationale="The positive passage reports a reduced incidence, but the false-support negative (same paper's discussion) reveals the finding is observational and confounded. A retrieval system that returns only the results sentence misleads.",
         origin_provenance="Modeled on P1B negated-findings style; tests false-support by splitting results vs discussion of the same source.",
         scenario_id="ssn_false_support_metformin_01",
         leakage_group="lg_metformin_oncology",
         document_family="df_metformin"),

    # ── evidence_retrieval 2: empagliflozin, same intervention wrong outcome ──
    case("diag_er_002", "evidence_retrieval", "biomedical",
         "Find a passage showing empagliflozin improves cardiovascular outcomes.",
         "passage", ["false_support", "agenda_mismatch"], ["same_intervention_wrong_outcome"],
         pos_passage_keys=["er2_pos"],
         hard_neg_keys=["er2_wrong_outcome"],
         rationale="The wrong-outcome passage (HbA1c reduction) is from the same trial and same drug; a system returning the glycemic result for a cardiovascular query commits agenda mismatch on the outcome axis.",
         origin_provenance="Tests same-intervention-wrong-outcome within one trial's results section.",
         scenario_id="ssn_wrong_outcome_empagliflozin_01",
         leakage_group="lg_sglt2_cardiometabolic",
         document_family="df_sglt2"),

    # ── contradiction_retrieval 1: metformin MICE (direct negation) ──
    case("diag_cr_001", "contradiction_retrieval", "biomedical",
         "Find passages that contradict the claim that metformin reduces cancer incidence.",
         "passage", ["missed_contradiction"], ["negated_or_qualified_result"],
         pos_passage_keys=["cr1_pos"],
         contradiction_keys=["cr1_qualifier"],
         hard_neg_keys=["cr1_qualifier"],
         rationale="Two independent contradicting sources: a direct null RCT result (MICE) and an independent reproduction failure. The contradiction must surface both, not just the headline-positive meta-analysis.",
         origin_provenance="Two-source contradiction: direct trial null + independent non-reproduction.",
         scenario_id="ssn_contradiction_metformin_01",
         leakage_group="lg_metformin_oncology",
         document_family="df_metformin"),

    # ── contradiction_retrieval 2: psilocybin qualifier (not direct negation) ──
    case("diag_cr_002", "contradiction_retrieval", "biomedical",
         "Find passages that qualify or limit the antidepressant effect of psilocybin.",
         "passage", ["missed_contradiction"], ["negated_or_qualified_result"],
         pos_passage_keys=["cr2_pos"],
         contradiction_keys=["cr2_qualifier"],
         hard_neg_keys=["cr2_qualifier"],
         rationale="The qualifier is methodological (comparator limits blinding), not a direct negation of efficacy. Tests whether the system surfaces qualifying caveats rather than only black-and-white contradictions.",
         origin_provenance="Tests genuine qualifier vs direct negation.",
         scenario_id="ssn_qualifier_psilocybin_01",
         leakage_group="lg_psilocybin",
         document_family="df_psilocybin"),

    # ── multi_paper_synthesis 1: GNN Amsterdam (same lineage) vs Stanford (independent) ──
    case("diag_mps_001", "multi_paper_synthesis", "machine_learning",
         "Retrieve diverse evidence on graph neural network propagation methods from distinct research lineages.",
         "paper_or_abstract", ["redundancy", "missed_relevant_evidence"], ["multiple_papers_one_lineage"],
         pos_passage_keys=["mps1a_kipf", "mps1b_graphsage", "mps1c_gat"],
         hard_neg_keys=["mps1b_graphsage"],
         rationale="GCN (Kipf) and GraphSAGE share the Amsterdam lineage; GAT (Stanford) is independent. A diverse synthesis must not collapse the two Amsterdam papers into one lineage slot. Hard negative is the near-duplicate-lineage GraphSAGE passage that would crowd out GAT.",
         origin_provenance="Tests same-lineage-vs-independent-lineage distinction explicitly.",
         scenario_id="ssn_lineage_diversity_gnn_01",
         leakage_group="lg_gnn_diversity",
         document_family="df_gnn"),

    # ── multi_paper_synthesis 2: scaling survey (synthesis) vs inverse-scaling (primary, distinct) ──
    case("diag_mps_002", "multi_paper_synthesis", "machine_learning",
         "Retrieve diverse primary evidence on how model scale affects safety-relevant capabilities.",
         "paper_or_abstract", ["redundancy", "missed_contradiction"], ["multiple_papers_one_lineage", "review_vs_primary"],
         pos_passage_keys=["mps2b_primary", "mps2a_survey"],
         hard_neg_keys=["mps2a_survey"],
         rationale="The survey aggregates prior work (one lineage); inverse-scaling is primary evidence from a distinct lineage. A synthesis must include the primary negative-scaling result, not only the survey. Hard negative is the survey crowding out the primary.",
         origin_provenance="Tests review-vs-primary and independent-lineage coverage.",
         scenario_id="ssn_lineage_diversity_scaling_01",
         leakage_group="lg_scaling",
         document_family="df_scaling"),

    # ── paper_discovery 1: low-resource NMT ──
    case("diag_pd_001", "paper_discovery", "nlp",
         "Find papers on improving machine translation for low-resource languages.",
         "paper_or_abstract", ["missed_relevant_evidence"], ["paraphrase_low_overlap"],
         pos_passage_keys=["pd1_pos"],
         hard_neg_keys=["doc_adc_electronics"],
         rationale="The query has low lexical overlap with the transfer-learning framing; tests semantic generalization at paper level. Hard negative is an off-topic electronics document.",
         origin_provenance="Low-overlap paraphrase at paper discovery level.",
         scenario_id="ssn_paraphrase_lowmt_01",
         leakage_group="lg_low_resource_nmt",
         document_family="df_nmt"),

    # ── method_retrieval 1: contrastive loss (method vs application) ──
    case("diag_mr_001", "method_retrieval", "machine_learning",
         "Find the method paper defining the contrastive loss formulation.",
         "paper_or_abstract", ["agenda_mismatch"], ["method_application_vs_definition"],
         pos_passage_keys=["mr1_method"],
         hard_neg_keys=["mr1_application"],
         rationale="SimCLR defines the method; the medical-imaging paper applies it. A system returning the application as the method commits method-application-vs-definition confusion.",
         origin_provenance="Tests method-vs-application discrimination directly.",
         scenario_id="ssn_method_vs_application_simclr_01",
         leakage_group="lg_contrastive",
         document_family="df_contrastive"),

    # ── research_gap_analysis 1: RLHF helpfulness vs safety agenda ──
    case("diag_rga_001", "research_gap_analysis", "machine_learning",
         "Find papers addressing how RLHF improves the SAFETY (not helpfulness) of large language models.",
         "paper_or_abstract", ["agenda_mismatch"], ["same_intervention_wrong_outcome"],
         pos_passage_keys=["rga1_on_topic"],
         hard_neg_keys=["doc_dose_scaling_review"],
         rationale="The InstructGPT paper is about helpfulness/alignment; the query asks about SAFETY specifically. The survey mentions scaling-vs-safety but is a synthesis, not RLHF. Tests agenda mismatch on the outcome axis (helpfulness vs safety) within the same intervention (RLHF/alignment).",
         origin_provenance="Tests agenda mismatch on the safety-vs-helpfulness outcome axis.",
         scenario_id="ssn_agenda_safety_vs_helpfulness_01",
         leakage_group="lg_alignment_safety",
         document_family="df_rlhf"),
]


def build():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # sources
    with open(OUTDIR / "p1d2_diagnostic_seed_sources.jsonl", "w", encoding="utf-8") as f:
        for d in CORPUS:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # cases
    with open(OUTDIR / "p1d2_diagnostic_seed_cases.jsonl", "w", encoding="utf-8") as f:
        for c in CASES:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # judgments (strip _rationale for machine file, keep rationale in review md)
    with open(OUTDIR / "p1d2_diagnostic_seed_judgments.jsonl", "w", encoding="utf-8") as f:
        for j in JUDGMENTS:
            jj = {k: v for k, v in j.items() if k != "_rationale"}
            f.write(json.dumps(jj, ensure_ascii=False) + "\n")

    # manifest (deterministic)
    import hashlib as _h
    def fp(p):
        return _h.sha256((OUTDIR / p).read_bytes()).hexdigest()

    families = {}
    for c in CASES:
        families[c["task_family"]] = families.get(c["task_family"], 0) + 1

    manifest = {
        "manifest_version": "p1d2_diagnostic_seed_manifest_v1",
        "status": "draft",
        "created": "2026-07-22",
        "benchmark_role": "diagnostic",
        "case_count": len(CASES),
        "judgment_count": len(JUDGMENTS),
        "source_document_count": len(CORPUS),
        "task_family_counts": dict(sorted(families.items())),
        "schema_versions": {"case": SCHEMA_VERSION_CASE, "judgment": SCHEMA_VERSION_JUDGMENT},
        "artifact_hashes": {
            "sources": fp("p1d2_diagnostic_seed_sources.jsonl"),
            "cases": fp("p1d2_diagnostic_seed_cases.jsonl"),
            "judgments": fp("p1d2_diagnostic_seed_judgments.jsonl"),
        },
        "review_status_note": "All judgments provisional, single-pass, non-scoreable, non-sealable. Requires external dual review before scoring.",
        "authoring_blindness": {
            "candidate_retrieval_outputs_visible_to_author": False,
            "embedding_model_evaluated": False,
            "reranker_evaluated": False,
            "policy_specific_tuning": False,
        },
    }
    with open(OUTDIR / "p1d2_diagnostic_seed_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(CORPUS)} sources, {len(CASES)} cases, {len(JUDGMENTS)} judgments.")
    print(f"Family distribution: {dict(sorted(families.items()))}")
    print(f"Manifest written. All artifacts deterministic.")


if __name__ == "__main__":
    build()
