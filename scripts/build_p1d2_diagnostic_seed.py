"""P1D.2b seed builder v2 (seed-hardening patch).

Changes from v1:
  1. candidate_pool: every case declares a bounded scored retrieval universe.
     Pools include cross-case distractors so a system can't win by topic isolation.
  2. Exhaustive judgments: every candidate_pool unit is judged exactly once.
  3. Cases are AUTHORITATIVE; the parallel judgments JSONL is DERIVED from them
     (eliminates dual-authority risk; validator asserts equivalence).
  4. claim_dimensions for causal-claim families (evidence_retrieval, contradiction_retrieval).
  5. negative_failed_dimensions: machine-auditable risk labels per negative.
  6. diag_er_001 semantics fixed: discussion caveat is qualifying evidence, not a
     generic negative; a fully-supporting unit exists.
  7. Byte-stable determinism: json.dumps with sort_keys + separators for all outputs.

Outputs (all deterministic):
  docs/retrieval/p1d2_diagnostic_seed_sources.jsonl
  docs/retrieval/p1d2_diagnostic_seed_cases.jsonl       (authoritative)
  docs/retrieval/p1d2_diagnostic_seed_judgments.jsonl   (derived from cases)
  docs/retrieval/p1d2_diagnostic_seed_manifest.json

DRAFT; NOT frozen. Judgments authored_provisional, non-scoreable, non-sealable.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTDIR = REPO / "docs" / "retrieval"

SV_CASE = "p1d2_case_schema_v1"
SV_JUDG = "p1d2_judgment_schema_v1"
AUTHOR = "author_seed_agent"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dump_jsonl(records, path):
    # sort_keys for byte-stable determinism
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


# ── SOURCE CORPUS (same 20 docs as v1; materialized synthetic source text) ──

def doc(doc_id, title, abstract, body, *, lineage, domain, license_basis="synthetic_public_abstract_style"):
    full = f"Title: {title}\n\nAbstract: {abstract}\n\n{body}"
    return {"document_id": doc_id, "document_version": "v1", "title": title, "domain": domain,
            "full_text": full, "document_content_hash": sha256(full),
            "evidence_lineage_id": lineage, "source_access_or_license_basis": license_basis}


CORPUS = [
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
    doc("doc_metformin_rct_positive", "Metformin Reduces Colorectal Neoplasia in a Randomized Prevention Trial",
        "A randomized placebo-controlled trial demonstrates that metformin reduces colorectal adenoma recurrence in non-diabetic patients at high risk.",
        "Methods: We randomized 2354 non-diabetic patients with prior colorectal adenoma to metformin or placebo, double-blinded. Results: Metformin reduced the recurrence of colorectal adenoma at 3-year colonoscopy (RR 0.67, 95% CI 0.54-0.83; p=0.0003). Discussion: This randomized, placebo-controlled evidence supports a causal chemopreventive effect of metformin on colorectal neoplasia, consistent with the observational signal but free of indication confounding.",
        lineage="elin_metformin_rct", domain="biomedical"),
    doc("doc_empagliflozin", "Empagliflozin and Glycemic Outcomes (EMPA-REG)",
        "We report SGLT2 inhibitor effects on glycemia and cardiovascular outcomes in type 2 diabetes.",
        "Methods: Randomized 7020 patients to empagliflozin or placebo. Results: Empagliflozin reduced cardiovascular death (HR 0.62, 95% CI 0.49-0.77) and modestly reduced HbA1c. Discussion: SGLT2 inhibition confers cardiovascular benefit independent of glycemic improvement.",
        lineage="elin_sglt2_glpl1_cardiometabolic", domain="biomedical"),
    doc("doc_pcsk9_ldl", "PCSK9 Monoclonal Antibodies for Hypercholesterolemia",
        "We review PCSK9 inhibitors for LDL-C lowering in hypercholesterolemia.",
        "Methods: Systematic review of trials. Results: PCSK9 inhibitors reduce LDL-C by approximately 60%. Discussion: PCSK9 inhibition is a potent LDL-lowering strategy; cardiovascular outcome trials are ongoing to establish event reduction.",
        lineage="elin_pcsk9_lipid", domain="biomedical"),
    doc("doc_pcsk9_cv", "Alirocumab and Cardiovascular Events (ODYSSEY OUTCOMES)",
        "A phase 3 trial of the PCSK9 inhibitor alirocumab in patients after acute coronary syndrome.",
        "Methods: Randomized 18924 patients to alirocumab or placebo. Results: Alirocumab reduced the composite of cardiovascular death, myocardial infarction, or stroke (HR 0.85, 95% CI 0.78-0.93). Discussion: PCSK9 inhibition reduces cardiovascular events in high-risk patients already on statin therapy.",
        lineage="elin_pcsk9_lipid", domain="biomedical"),
    doc("doc_simclr", "SimCLR: A Simple Framework for Contrastive Learning",
        "We introduce a contrastive loss based on InfoNCE over augmented views for self-supervised representation learning.",
        "Methods: We maximize agreement between augmentations of the same image under a base encoder with a projection head. Results: SimCLR achieves state-of-the-art on ImageNet linear-eval. Discussion: The contrastive loss formulation is the core contribution; the encoder architecture is interchangeable.",
        lineage="elin_contrastive_method", domain="machine_learning"),
    doc("doc_simclr_medical_app", "Applying Contrastive Features to Medical Image Classification",
        "We fine-tune contrastive features for downstream medical imaging classification.",
        "Methods: We initialize from a contrastive encoder and fine-tune on chest radiograph labels. Results: Transfer improves AUC by 3 points over ImageNet pre-training. Discussion: Self-supervised features transfer well to medical imaging, but this work is an application of an existing method rather than a new contrastive loss.",
        lineage="elin_contrastive_application", domain="machine_learning"),
    doc("doc_zero", "Efficient Memory Management for Large Language Model Training",
        "ZeRO partitions optimizer states across devices to reduce the memory footprint of gigantic models.",
        "Methods: We partition optimizer states, gradients, and parameters across data-parallel workers. Results: ZeRO enables training models with over 100 billion parameters on 400 GPUs. Discussion: The technique addresses the memory bottleneck that limits training very large models, complementing pipeline and tensor parallelism.",
        lineage="elin_efficient_training", domain="machine_learning"),
    doc("doc_instructgpt", "Training Language Models to Follow Instructions with Human Feedback",
        "We fine-tune large models using reinforcement learning from human feedback to align outputs with user intent.",
        "Methods: Three-stage pipeline: supervised fine-tuning, reward model training, and PPO optimization on the reward model. Results: The resulting model produces more helpful and aligned responses than the base model. Discussion: RLHF is an effective method for aligning language models to follow human instructions.",
        lineage="elin_rlhf", domain="machine_learning"),
    doc("doc_adc_oncology", "Antibody-Drug Conjugates: Principles and Clinical Applications",
        "We review ADC design, linker chemistry, and clinical activity in oncology.",
        "Methods: Narrative review of approved and investigational ADCs. Results: ADCs like trastuzumab deruxtecan show activity in HER2-low breast cancer. Discussion: The antibody delivers a cytotoxic payload selectively to tumor cells expressing the target antigen; this is distinct from ADC circuits in electronics.",
        lineage="elin_adc_oncology", domain="biomedical"),
    doc("doc_adc_electronics", "Analog-to-Digital Converter Circuit Design",
        "We design low-power ADC circuits for sensor interfaces.",
        "Methods: Successive-approximation-register architecture in 28nm CMOS. Results: The converter achieves 12-bit resolution at 1 MS/s with 0.8 mW power. Discussion: This analog-to-digital converter (ADC) has no relation to antibody-drug conjugates; the shared acronym is coincidental.",
        lineage="elin_adc_electronics", domain="machine_learning", license_basis="synthetic_electronics_context"),
    doc("doc_psilocybin_jama", "Psilocybin Therapy for Treatment-Resistant Depression (JAMA Psychiatry)",
        "A randomized trial shows rapid antidepressant effects of psilocybin in treatment-resistant depression.",
        "Methods: We randomized 59 patients to psilocybin or escitalopram. Results: Psilocybin produced a rapid reduction in depression scores at week 6. Discussion: This randomized evidence supports a rapid antidepressant effect of psilocybin, though the comparator arm limits blinding.",
        lineage="elin_psilocybin_primary", domain="biomedical"),
    doc("doc_psilocybin_review", "Psychedelics in Psychiatry: A Narrative Review",
        "We synthesize evidence on psychedelic-assisted therapy.",
        "Methods: Narrative review across trials of serotonergic psychedelics. Results: The evidence base is growing but dominated by small, open-label studies. Discussion: While promising, the field requires larger randomized trials; this review aggregates rather than reports primary data.",
        lineage="elin_psilocybin_review", domain="biomedical"),
    doc("doc_transfer_nmt", "Improving Low-Resource Neural MT with Transfer Learning",
        "We pre-train on high-resource pairs and transfer to low-resource languages.",
        "Methods: We initialize a low-resource encoder-decoder from a high-resource model and fine-tune. Results: BLEU improves by 4.1 points on Swahili-English. Discussion: Transfer learning substantially narrows the performance gap for low-resource translation directions.",
        lineage="elin_low_resource_nmt", domain="nlp"),
    doc("doc_gcn_kipf", "Semi-Supervised Classification with Graph Convolutional Networks",
        "We introduce graph convolutional networks for node classification.",
        "Methods: A spectral graph convolution approximated by Chebyshev polynomials. Results: The GCN achieves state-of-the-art on citation networks. Discussion: The layer-wise propagation rule is the core architectural contribution.",
        lineage="elin_gnn_amsterdam", domain="machine_learning"),
    doc("doc_graphsage", "GraphSAGE: Inductive Learning on Large Graphs",
        "We sample and aggregate neighborhoods inductively for large-graph learning.",
        "Methods: Neighborhood sampling with learned aggregators. Results: GraphSAGE predicts unseen node embeddings. Discussion: Unlike transductive GCN, GraphSAGE generalizes to unseen nodes.",
        lineage="elin_gnn_amsterdam", domain="machine_learning"),
    doc("doc_gat", "Graph Attention Networks (GAT)",
        "We apply attention over graph neighborhoods for node classification.",
        "Methods: Masked self-attention layers compute node embeddings by attending over neighbors. Results: GAT matches or exceeds GCN on benchmark datasets. Discussion: Attention weights are learned and provide interpretability.",
        lineage="elin_gnn_stanford", domain="machine_learning"),
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


def locate(doc_id, needle):
    s = CORPUS_BY_ID[doc_id]["full_text"].index(needle)
    return (s, s + len(needle))


def mkpassage(doc_id, needle, section="results"):
    s, e = locate(doc_id, needle)
    d = CORPUS_BY_ID[doc_id]
    text = d["full_text"][s:e]
    return {
        "document_id": doc_id, "document_version": "v1", "section_id": section,
        "passage_id": f"{doc_id}_{s}_{e}", "passage_locator": f"chars {s}-{e}",
        "passage_text": text, "passage_text_hash": sha256(text),
        "document_content_hash": d["document_content_hash"],
        "source_access_or_license_basis": d["source_access_or_license_basis"],
        "evidence_lineage_id": d["evidence_lineage_id"],
    }


def P(doc_id, needle, section="results"):
    return mkpassage(doc_id, needle, section)


# ── PASSAGE REGISTRY ──
# keyed by short alias; each case references these
PASS = {}
# er1 — false support via association-as-causation. CAUSAL claim.
#   positive: a real positive RCT (causally adequate) -> fully supports the causal claim
#   false-support hard negative: observational association with supportive wording -> fails causal_vs_associational
#   qualifier: the observational paper's own confounding caveat -> qualifying evidence, fails study_design_requirement
#   distractor: empagliflozin (cross-case)
PASS["er1_rct_positive"] = P("doc_metformin_rct_positive", "Metformin reduced the recurrence of colorectal adenoma at 3-year colonoscopy (RR 0.67, 95% CI 0.54-0.83; p=0.0003)")
PASS["er1_obs_association"] = P("doc_metformin_meta", "pooled analysis showed a reduced incidence of colorectal and hepatocellular carcinoma in metformin users")
PASS["er1_design_caveat"] = P("doc_metformin_meta", "These observational findings are subject to confounding by indication", "discussion")
PASS["er1_empagliflozin_distractor"] = P("doc_empagliflozin", "Empagliflozin reduced cardiovascular death")
# er2 — same intervention wrong outcome
PASS["er2_cv"] = P("doc_empagliflozin", "Empagliflozin reduced cardiovascular death")
PASS["er2_glycemic"] = P("doc_empagliflozin", "modestly reduced HbA1c")
PASS["er2_pcsk9_distractor"] = P("doc_pcsk9_cv", "Alirocumab reduced the composite of cardiovascular death")  # cross-case distractor
# cr1 — metformin contradiction
PASS["cr1_null"] = P("doc_metformin_mice", "Cancer events did not differ between arms")
PASS["cr1_nonrepro"] = P("doc_metformin_repro", "metformin exposure was not associated with cancer incidence")
PASS["cr1_meta_positive"] = P("doc_metformin_meta", "pooled analysis showed a reduced incidence of colorectal and hepatocellular carcinoma in metformin users")
# cr2 — psilocybin qualifier
PASS["cr2_effect"] = P("doc_psilocybin_jama", "Psilocybin produced a rapid reduction in depression scores")
PASS["cr2_blinding_caveat"] = P("doc_psilocybin_jama", "the comparator arm limits blinding", "discussion")
PASS["cr2_review_distractor"] = P("doc_psilocybin_review", "the field requires larger randomized trials", "discussion")
# mps1 — GNN lineages
PASS["mps1a_kipf"] = P("doc_gcn_kipf", "The layer-wise propagation rule is the core architectural contribution", "discussion")
PASS["mps1b_graphsage"] = P("doc_graphsage", "GraphSAGE predicts unseen node embeddings")
PASS["mps1c_gat"] = P("doc_gat", "GAT matches or exceeds GCN on benchmark datasets")
# mps2 — scaling lineages
PASS["mps2_primary"] = P("doc_inverse_scaling", "performance degrades with scale")
PASS["mps2_survey"] = P("doc_dose_scaling_review", "performance generally improves with scale, but emphasizes that scaling alone is neither necessary nor sufficient for safety")
# pd1 — low-resource NMT
PASS["pd1_transfer"] = P("doc_transfer_nmt", "Transfer learning substantially narrows the performance gap for low-resource translation directions", "discussion")
PASS["pd1_gnn_distractor"] = P("doc_gat", "GAT matches or exceeds GCN on benchmark datasets")  # cross-case distractor
# mr1 — method vs application
PASS["mr1_method"] = P("doc_simclr", "maximize agreement between augmentations of the same image under a base encoder with a projection head", "methods")
PASS["mr1_application"] = P("doc_simclr_medical_app", "Transfer improves AUC by 3 points over ImageNet pre-training")
# rga1 — RLHF agenda
PASS["rga1_instructgpt"] = P("doc_instructgpt", "The resulting model produces more helpful and aligned responses than the base model")
PASS["rga1_scaling_distractor"] = P("doc_dose_scaling_review", "scaling alone is neither necessary nor sufficient for safety")

PASSAGES_BY_ID = {p["passage_id"]: p for p in PASS.values()}


def qfp(query):
    return sha256(" ".join(query.lower().split()))


def pool_fingerprint(unit_ids):
    return sha256(json.dumps(sorted(unit_ids), sort_keys=True))


def judgment(jid, case_id, passage, grade, *, topical=3, evidence=3, method=3, confidence=0.7):
    """Build a judgment object. passage is a full passage dict (with passage_text)."""
    return {
        "schema_version": SV_JUDG, "judgment_id": jid, "case_id": case_id,
        "unit_id": passage["passage_id"], "unit_type": "passage",
        "unit_text_hash": passage["passage_text_hash"],
        "research_utility_grade": grade, "topical_relevance": topical,
        "evidence_utility": evidence, "methodological_fit": method,
        "review_status": "authored_provisional", "decision_basis": "single_pass_provisional",
        "requires_external_dual_review": True, "eligible_for_scoring": False,
        "eligible_for_seal": False, "case_author_id": AUTHOR,
        "policy_outputs_visible_to_reviewers": False, "annotation_confidence": confidence,
    }


def build_case(case_id, task_family, domain, query, retrieved_unit, surface, risk_labels, hard_neg_types,
               pool_passage_keys, pos_keys, judgment_grades, claim_dims, neg_failed_dims,
               rationale, origin_provenance, scenario_id, leakage_group, document_family,
               contradiction_keys=None):
    """Build a case with exhaustive candidate pool + inline judgments."""
    # The pool = all passages this case exposes to the retriever, with judgments for each
    pool_passages = [PASS[k] for k in pool_passage_keys]
    pool_ids = [p["passage_id"] for p in pool_passages]

    pos_ids = [PASS[k]["passage_id"] for k in pos_keys]

    # build judgments for every pool unit
    inlined = []
    for p in pool_passages:
        jid = f"jdg_{case_id}_{p['passage_id']}"
        grade, kw = judgment_grades.get(p["passage_id"], (0, {}))
        inlined.append(judgment(jid, case_id, p, grade, **kw))

    c = {
        "schema_version": SV_CASE, "case_id": case_id, "benchmark_role": "diagnostic",
        "task_family": task_family, "research_domain": domain, "query_or_claim": query,
        "retrieved_unit": retrieved_unit,
        "source_document_ids": sorted({p["document_id"] for p in pool_passages}),
        "positive_passage_ids": pos_ids,
        "hard_topical_negatives": [PASS[k]["passage_id"] for k in (contradiction_keys or [])] or [pool_ids[-1]],
        "relevance_judgments": inlined, "risk_labels": risk_labels, "hard_negative_types": hard_neg_types,
        "annotation_rationale": rationale, "case_origin": "synthetic_realistic",
        "origin_provenance": origin_provenance, "deidentification_status": "not_applicable_synthetic",
        "case_author_id": AUTHOR, "review_status": "authored_provisional",
        "leakage_group_id": leakage_group, "document_family_id": document_family,
        "query_semantic_fingerprint": qfp(query),
        "positive_unit_fingerprint": PASS[pos_keys[0]]["passage_text_hash"],
        "synthetic_scenario_id": scenario_id,
        "passages": {p["passage_id"]: {k: v for k, v in p.items() if k != "passage_text"} for p in pool_passages},
        "candidate_pool": {
            "pool_id": f"pool_{case_id}", "retrieval_surface": surface,
            "candidate_unit_type": retrieved_unit.replace("paper_or_abstract", "paper"),
            "candidate_unit_ids": sorted(set(pool_ids)),
            "pool_fingerprint": pool_fingerprint(pool_ids),
            "unjudged_unit_policy": "exhaustive_no_unjudged",
        },
        "negative_failed_dimensions": neg_failed_dims,
    }
    if contradiction_keys:
        c["contradicting_or_qualifying_passages"] = [PASS[k]["passage_id"] for k in contradiction_keys]
    if claim_dims:
        c["claim_dimensions"] = claim_dims
    return c


# ── CASES (exhaustive pools; every pool unit judged) ──

CASES = [
    # diag_er_001 — false support via ASSOCIATION PRESENTED AS CAUSATION. CAUSAL claim.
    #   positive: a positive RCT (causally adequate) -> fully supports the causal claim (grade 3)
    #   false-support hard negative: observational association with supportive wording -> fails causal_vs_associational
    #   qualifier: the observational paper's confounding caveat -> qualifying evidence, fails study_design_requirement
    #   distractor: empagliflozin (cross-case, different drug/outcome)
    build_case(
        "diag_er_001", "evidence_retrieval", "biomedical",
        "Find passages showing metformin causally reduces cancer incidence.",
        "passage", "retrieval_ranking", ["false_support"], ["supportive_language_without_support"],
        pool_passage_keys=["er1_rct_positive", "er1_obs_association", "er1_design_caveat", "er1_empagliflozin_distractor"],
        pos_keys=["er1_rct_positive"],
        judgment_grades={
            PASS["er1_rct_positive"]["passage_id"]: (3, {}),
            PASS["er1_obs_association"]["passage_id"]: (1, {"evidence": 1}),
            PASS["er1_design_caveat"]["passage_id"]: (2, {"evidence": 2}),
            PASS["er1_empagliflozin_distractor"]["passage_id"]: (0, {}),
        },
        claim_dims={"population": "non-diabetic/high-risk adults", "intervention_or_exposure": "metformin",
                    "comparison": "placebo", "outcome": "cancer/neoplasia incidence",
                    "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim",
                    "study_design_requirement": "randomized controlled trial",
                    "qualifiers": "causal chemopreventive effect claimed"},
        neg_failed_dims=[
            {"unit_id": PASS["er1_obs_association"]["passage_id"], "failed_dimensions": ["causal_vs_associational", "study_design_requirement"]},
            {"unit_id": PASS["er1_design_caveat"]["passage_id"], "failed_dimensions": ["study_design_requirement"]},
            {"unit_id": PASS["er1_empagliflozin_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]},
        ],
        rationale="CAUSAL claim. The positive RCT (grade 3) fully supports it. The observational meta-analysis result (grade 1) uses supportive wording ('reduced incidence') but is associational only — this is the false-support trap: association presented as supporting a causal claim. The discussion caveat (grade 2) is qualifying evidence (warns of confounding), not a generic negative. Empagliflozin is a cross-case distractor.",
        origin_provenance="False-support via association-as-causation: observational supportive wording mistaken for causal support. Positive RCT + observational false-support + design qualifier + cross-case distractor.",
        scenario_id="ssn_false_support_causal_metformin_03", leakage_group="lg_metformin_oncology", document_family="df_metformin",
    ),

    # diag_er_002 — same intervention wrong outcome
    build_case(
        "diag_er_002", "evidence_retrieval", "biomedical",
        "Find passages showing empagliflozin improves cardiovascular outcomes.",
        "passage", "retrieval_ranking", ["false_support", "agenda_mismatch"], ["same_intervention_wrong_outcome"],
        pool_passage_keys=["er2_cv", "er2_glycemic", "er2_pcsk9_distractor"],
        pos_keys=["er2_cv"],
        judgment_grades={PASS["er2_cv"]["passage_id"]: (3, {}), PASS["er2_glycemic"]["passage_id"]: (1, {"evidence": 1}),
                         PASS["er2_pcsk9_distractor"]["passage_id"]: (1, {"evidence": 1})},
        claim_dims={"population": "type 2 diabetes patients", "intervention_or_exposure": "empagliflozin",
                    "comparison": "placebo", "outcome": "cardiovascular outcomes",
                    "direction_or_polarity": "improves", "causal_vs_associational": "causal_claim",
                    "study_design_requirement": "randomized trial", "qualifiers": "none"},
        neg_failed_dims=[
            {"unit_id": PASS["er2_glycemic"]["passage_id"], "failed_dimensions": ["outcome"]},
            {"unit_id": PASS["er2_pcsk9_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]},
        ],
        rationale="Glycemic result is same drug, wrong outcome. PCSK9 is cross-case distractor.",
        origin_provenance="Same-intervention-wrong-outcome within one trial + cross-case distractor.",
        scenario_id="ssn_wrong_outcome_empagliflozin_02", leakage_group="lg_sglt2_cardiometabolic", document_family="df_sglt2",
    ),

    # diag_cr_001 — metformin contradiction
    build_case(
        "diag_cr_001", "contradiction_retrieval", "biomedical",
        "Find passages that contradict the claim that metformin reduces cancer incidence.",
        "passage", "retrieval_ranking", ["missed_contradiction"], ["negated_or_qualified_result"],
        pool_passage_keys=["cr1_null", "cr1_nonrepro", "cr1_meta_positive"],
        pos_keys=["cr1_null"],
        contradiction_keys=["cr1_nonrepro"],
        judgment_grades={PASS["cr1_null"]["passage_id"]: (3, {}), PASS["cr1_nonrepro"]["passage_id"]: (3, {}),
                         PASS["cr1_meta_positive"]["passage_id"]: (1, {"evidence": 1})},
        claim_dims={"population": "adults", "intervention_or_exposure": "metformin",
                    "comparison": "placebo/no metformin", "outcome": "cancer incidence",
                    "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim",
                    "study_design_requirement": "randomized trial", "qualifiers": "none"},
        neg_failed_dims=[
            {"unit_id": PASS["cr1_meta_positive"]["passage_id"], "failed_dimensions": ["causal_vs_associational", "study_design_requirement"]},
        ],
        rationale="Null RCT + independent non-reproduction contradict the claim; meta-analysis positive is the context that must not drown them out.",
        origin_provenance="Two-source contradiction: direct null + independent non-reproduction.",
        scenario_id="ssn_contradiction_metformin_02", leakage_group="lg_metformin_oncology", document_family="df_metformin",
    ),

    # diag_cr_002 — psilocybin qualifier
    build_case(
        "diag_cr_002", "contradiction_retrieval", "biomedical",
        "Find passages that qualify or limit the antidepressant effect of psilocybin.",
        "passage", "retrieval_ranking", ["missed_contradiction"], ["negated_or_qualified_result"],
        pool_passage_keys=["cr2_effect", "cr2_blinding_caveat", "cr2_review_distractor"],
        pos_keys=["cr2_blinding_caveat"],
        contradiction_keys=["cr2_blinding_caveat"],
        judgment_grades={PASS["cr2_effect"]["passage_id"]: (2, {"evidence": 2}),
                         PASS["cr2_blinding_caveat"]["passage_id"]: (3, {}),
                         PASS["cr2_review_distractor"]["passage_id"]: (2, {"evidence": 2})},
        claim_dims={"population": "treatment-resistant depression patients", "intervention_or_exposure": "psilocybin",
                    "comparison": "escitalopram", "outcome": "depression score reduction",
                    "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim",
                    "study_design_requirement": "randomized trial", "qualifiers": "effect limited by blinding"},
        neg_failed_dims=[
            {"unit_id": PASS["cr2_review_distractor"]["passage_id"], "failed_dimensions": ["study_design_requirement"]},
        ],
        rationale="Blinding caveat is a genuine qualifier (methodological limit), not a direct negation. Review distractor is a secondary source.",
        origin_provenance="Genuine qualifier vs direct negation.",
        scenario_id="ssn_qualifier_psilocybin_02", leakage_group="lg_psilocybin", document_family="df_psilocybin",
    ),

    # diag_mps_001 — GNN lineages (Amsterdam x2 vs Stanford)
    build_case(
        "diag_mps_001", "multi_paper_synthesis", "machine_learning",
        "Retrieve diverse evidence on graph neural network propagation methods from distinct research lineages.",
        "paper_or_abstract", "discovery_ranking", ["redundancy", "missed_relevant_evidence"], ["multiple_papers_one_lineage"],
        pool_passage_keys=["mps1a_kipf", "mps1b_graphsage", "mps1c_gat"],
        pos_keys=["mps1a_kipf", "mps1c_gat"],
        judgment_grades={PASS["mps1a_kipf"]["passage_id"]: (3, {}), PASS["mps1b_graphsage"]["passage_id"]: (2, {}),
                         PASS["mps1c_gat"]["passage_id"]: (3, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps1b_graphsage"]["passage_id"], "failed_dimensions": ["evidence_lineage"]}],
        rationale="GCN + GraphSAGE share Amsterdam lineage; GAT is Stanford (independent). GraphSAGE is relevant but redundant for diversity.",
        origin_provenance="Same-lineage-vs-independent-lineage distinction.",
        scenario_id="ssn_lineage_diversity_gnn_02", leakage_group="lg_gnn_diversity", document_family="df_gnn",
    ),

    # diag_mps_002 — scaling lineages (survey vs primary)
    build_case(
        "diag_mps_002", "multi_paper_synthesis", "machine_learning",
        "Retrieve diverse primary evidence on how model scale affects safety-relevant capabilities.",
        "paper_or_abstract", "discovery_ranking", ["redundancy", "missed_contradiction"], ["multiple_papers_one_lineage", "review_vs_primary"],
        pool_passage_keys=["mps2_primary", "mps2_survey"],
        pos_keys=["mps2_primary"],
        judgment_grades={PASS["mps2_primary"]["passage_id"]: (3, {}), PASS["mps2_survey"]["passage_id"]: (2, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps2_survey"]["passage_id"], "failed_dimensions": ["evidence_lineage", "evidence_granularity"]}],
        rationale="Inverse-scaling is primary (distinct lineage); survey aggregates prior work. Synthesis must include the primary.",
        origin_provenance="Review-vs-primary and independent-lineage coverage.",
        scenario_id="ssn_lineage_diversity_scaling_02", leakage_group="lg_scaling", document_family="df_scaling",
    ),

    # diag_pd_001 — low-resource NMT paraphrase
    build_case(
        "diag_pd_001", "paper_discovery", "nlp",
        "Find papers on improving machine translation for low-resource languages.",
        "paper_or_abstract", "discovery_ranking", ["missed_relevant_evidence"], ["paraphrase_low_overlap"],
        pool_passage_keys=["pd1_transfer", "pd1_gnn_distractor"],
        pos_keys=["pd1_transfer"],
        judgment_grades={PASS["pd1_transfer"]["passage_id"]: (3, {"confidence": 0.75} if False else {}),
                         PASS["pd1_gnn_distractor"]["passage_id"]: (0, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["pd1_gnn_distractor"]["passage_id"], "failed_dimensions": ["meaning_or_domain"]}],
        rationale="Low-overlap paraphrase (transfer-learning framing). GAT is a cross-case distractor from a different domain.",
        origin_provenance="Low-overlap paraphrase at paper level + cross-case distractor.",
        scenario_id="ssn_paraphrase_lowmt_02", leakage_group="lg_low_resource_nmt", document_family="df_nmt",
    ),

    # diag_mr_001 — method vs application
    build_case(
        "diag_mr_001", "method_retrieval", "machine_learning",
        "Find the method paper defining the contrastive loss formulation.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["method_application_vs_definition"],
        pool_passage_keys=["mr1_method", "mr1_application"],
        pos_keys=["mr1_method"],
        judgment_grades={PASS["mr1_method"]["passage_id"]: (3, {}), PASS["mr1_application"]["passage_id"]: (2, {"method": 2})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mr1_application"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}],
        rationale="SimCLR defines the method; medical-imaging paper applies it.",
        origin_provenance="Method-vs-application discrimination.",
        scenario_id="ssn_method_vs_application_simclr_02", leakage_group="lg_contrastive", document_family="df_contrastive",
    ),

    # diag_rga_001 — RLHF agenda (safety vs helpfulness)
    build_case(
        "diag_rga_001", "research_gap_analysis", "machine_learning",
        "Find papers addressing how RLHF improves the SAFETY (not helpfulness) of large language models.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["same_intervention_wrong_outcome"],
        pool_passage_keys=["rga1_instructgpt", "rga1_scaling_distractor"],
        pos_keys=["rga1_instructgpt"],
        judgment_grades={PASS["rga1_instructgpt"]["passage_id"]: (2, {"evidence": 2}),
                         PASS["rga1_scaling_distractor"]["passage_id"]: (1, {"evidence": 1})},
        claim_dims=None,
        neg_failed_dims=[
            {"unit_id": PASS["rga1_instructgpt"]["passage_id"], "failed_dimensions": ["outcome"]},
            {"unit_id": PASS["rga1_scaling_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]},
        ],
        rationale="InstructGPT addresses helpfulness, not safety (agenda mismatch on outcome). Scaling survey mentions safety but is not RLHF.",
        origin_provenance="Agenda mismatch on safety-vs-helpfulness outcome axis.",
        scenario_id="ssn_agenda_safety_vs_helpfulness_02", leakage_group="lg_alignment_safety", document_family="df_rlhf",
    ),
]


def derive_judgments_from_cases():
    """Cases are authoritative; judgments JSONL is derived. Eliminates dual-authority."""
    out = []
    for c in CASES:
        for j in c["relevance_judgments"]:
            out.append(j)
    return out


def build():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    dump_jsonl(CORPUS, OUTDIR / "p1d2_diagnostic_seed_sources.jsonl")
    dump_jsonl(CASES, OUTDIR / "p1d2_diagnostic_seed_cases.jsonl")
    derived_judgments = derive_judgments_from_cases()
    dump_jsonl(derived_judgments, OUTDIR / "p1d2_diagnostic_seed_judgments.jsonl")

    families = {}
    for c in CASES:
        families[c["task_family"]] = families.get(c["task_family"], 0) + 1

    def fp(p):
        return sha256((OUTDIR / p).read_bytes().decode("utf-8"))

    manifest = {
        "manifest_version": "p1d2_diagnostic_seed_manifest_v2", "status": "draft",
        "created": "2026-07-22", "benchmark_role": "diagnostic",
        "case_count": len(CASES), "judgment_count": len(derived_judgments),
        "source_document_count": len(CORPUS), "task_family_counts": dict(sorted(families.items())),
        "schema_versions": {"case": SV_CASE, "judgment": SV_JUDG},
        "artifact_hashes": {
            "sources": fp("p1d2_diagnostic_seed_sources.jsonl"),
            "cases": fp("p1d2_diagnostic_seed_cases.jsonl"),
            "judgments": fp("p1d2_diagnostic_seed_judgments.jsonl"),
        },
        "review_status_note": "All judgments authored_provisional, single-pass, non-scoreable, non-sealable. Requires external dual review before scoring.",
        "authoring_blindness": {
            "candidate_retrieval_outputs_visible_to_author": False,
            "embedding_model_evaluated": False, "reranker_evaluated": False,
            "policy_specific_tuning": False,
        },
        "candidate_pool_design": "exhaustive per-case pools with cross-case distractors; every pool unit judged exactly once",
        "judgment_authority": "cases are authoritative; judgments JSONL derived from cases",
    }
    dump_json(manifest, OUTDIR / "p1d2_diagnostic_seed_manifest.json")
    print(f"Wrote {len(CORPUS)} sources, {len(CASES)} cases, {len(derived_judgments)} judgments.")
    print(f"Families: {dict(sorted(families.items()))}")


if __name__ == "__main__":
    build()
