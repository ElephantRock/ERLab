"""P1D.2b expansion: adds 21 cases (010-030) to the 9-case seed (001-009).

Imports the base builder's infrastructure (CORPUS, PASS, helpers) and extends
them. The combined output (30 cases) is emitted by build().

Primary traps covered by the 21 new cases:
  - exact identifier / acronym collision (er_005: GPT as model vs GPT as protein)
  - same topic + outcome, wrong population (cr_005: pediatric vs adult antidepressant)
  - association presented as causation (er_006: cohort vs RCT)
  - same intervention, wrong outcome (er_007)
  - qualified effect presented as unconditional (er_008)
  - method application presented as method definition (mr_002)
  - review evidence presented as primary (cr_006)
  - same topic, different research agenda (rga_002)
  - same evidence lineage presented as independent (mps_005)
  Plus: paraphrase_low_overlap (pd_002, pd_003), agenda_mismatch (rga_003),
  review_vs_primary (mps_006), lineage diversity (mps_003, mps_004),
  false_support variants (er_003, er_004), contradiction (cr_003, cr_004),
  method/app (mr_003), no_positive_expected controls (rga_002, rga_003).
"""
from __future__ import annotations
import importlib.util, sys, json
from pathlib import Path

# Import the base builder as a module
REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("base", REPO / "scripts" / "build_p1d2_diagnostic_seed.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

# Pull everything we need from the base
CORPUS = base.CORPUS
CORPUS_BY_ID = base.CORPUS_BY_ID
PASS = dict(base.PASS)  # copy so we can extend
CASES_BASE = list(base.CASES)
doc = base.doc
P = base.P
locate = base.locate
sha256 = base.sha256
qfp = base.qfp
pool_fingerprint = base.pool_fingerprint
build_case = base.build_case
SV_CASE = base.SV_CASE
SV_JUDG = base.SV_JUDG
AUTHOR = base.AUTHOR
dump_jsonl = base.dump_jsonl
dump_json = base.dump_json
OUTDIR = base.OUTDIR

# ────────────────────────────────────────────────────────────────────
# NEW SOURCE DOCUMENTS (for the 21 expansion cases)
# ────────────────────────────────────────────────────────────────────

NEW_DOCS = [
    # ── GPT collision: language model vs protein ──
    doc("doc_gpt3_lm", "Language Models are Few-Shot Learners (GPT-3)",
        "We train a 175-billion-parameter autoregressive language model and demonstrate strong few-shot performance across NLP tasks.",
        "Methods: We scale transformer decoder architecture to 175B parameters. Results: GPT-3 achieves strong few-shot learning on translation, question answering, and reasoning benchmarks. Discussion: Scale enables in-context learning without fine-tuning; the model is a general-purpose language predictor.",
        lineage="elin_gpt_lm", domain="machine_learning"),
    doc("doc_gpt_protein", "GPT: A Generative Protein Transformer for de Novo Design",
        "We train an autoregressive transformer to generate novel protein sequences with specified functional properties.",
        "Methods: We tokenize amino-acid sequences and train a transformer on 250M natural proteins. Results: GPT generates soluble, functional enzymes confirmed by wet-lab assays. Discussion: The same 'GPT' acronym appears in language modeling; this work targets protein sequence space, not natural language.",
        lineage="elin_gpt_protein", domain="biomedical"),

    # ── Vitamin D fracture: qualifier (qualified effect presented as unconditional) ──
    doc("doc_vitd_combined", "Vitamin D Plus Calcium Reduces Fractures in Elderly Institutionalized Adults",
        "A randomized trial shows combined vitamin D and calcium supplementation reduces hip fracture in institutionalized elderly women.",
        "Methods: We randomized 3270 institutionalized women aged 80+ to combined vitamin D3+calcium or placebo. Results: The combination reduced hip fractures (HR 0.57, 95% CI 0.42-0.77) and non-vertebral fractures. Discussion: This benefit is specific to the combined regimen in an institutionalized elderly population; vitamin D alone without calcium was not tested here.",
        lineage="elin_vitd_fracture_rct", domain="biomedical"),
    doc("doc_vitd_alone", "Vitamin D Alone Does Not Prevent Fractures (VITAL)",
        "A large randomized trial finds no fracture reduction with high-dose vitamin D monotherapy in a general middle-aged population.",
        "Methods: We randomized 25871 community-dwelling adults to 2000 IU vitamin D3 or placebo. Results: Vitamin D alone did not reduce total fractures (HR 0.97, 95% CI 0.88-1.06). Discussion: In a community population with adequate baseline levels, high-dose vitamin D monotherapy has no fracture benefit, contrasting with institutionalized-elderly combination trials.",
        lineage="elin_vitd_fracture_rct", domain="biomedical"),

    # ── Pediatric vs adult antidepressant (wrong population) ──
    doc("doc_ssri_adult", "SSRIs Reduce Depressive Symptoms in Adults with Major Depression",
        "A randomized trial demonstrates fluoxetine reduces depression scores in adults with moderate-to-severe major depressive disorder.",
        "Methods: We randomized 456 adults aged 25-65 to fluoxetine or placebo. Results: Fluoxetine reduced HAM-D scores by 6.2 points (95% CI 4.1-8.3) versus placebo. Discussion: SSRIs are effective in adult major depression; the effect size is consistent across adult age groups.",
        lineage="elin_ssri_adult_rct", domain="biomedical"),
    doc("doc_ssri_pediatric", "SSRIs Show Modest Benefit with Suicide Risk in Adolescent Depression",
        "A randomized trial in adolescents finds fluoxetine reduces depression but increases suicidal ideation risk.",
        "Methods: We randomized 439 adolescents aged 12-17 to fluoxetine or placebo. Results: Fluoxetine reduced depression scores modestly (effect size 0.7 SD) but increased treatment-emergent suicidal ideation (OR 1.8, 95% CI 1.0-3.2). Discussion: The risk-benefit profile in adolescents differs fundamentally from adults; the suicide signal requires age-specific prescribing guidance.",
        lineage="elin_ssri_pediatric_rct", domain="biomedical"),

    # ── WHO COVID early treatment (review vs primary; contradiction) ──
    doc("doc_covid_meta_positive", "Early Antiviral Treatment for COVID-19: A Living Systematic Review",
        "A living systematic review synthesizes emerging evidence on early antiviral treatment for COVID-19.",
        "Methods: We aggregate 18 studies across antiviral agents. Results: The pooled evidence suggests early nirmatrelvir-ritonavir reduces hospitalization in high-risk adults. Discussion: This review aggregates rather than reports primary data; the synthesized estimate depends on included-study quality and populations.",
        lineage="elin_covid_antiviral_review", domain="biomedical"),
    doc("doc_covid_remdesivir_primary", "Remdesivir for Early COVID-19 in Outpatients",
        "A randomized placebo-controlled trial of early remdesivir in non-hospitalized COVID-19 patients.",
        "Methods: We randomized 562 high-risk outpatients to 3-day remdesivir or placebo within 7 days of symptom onset. Results: Early remdesivir reduced COVID-19 hospitalization or death by 87% (RR 0.13, 95% CI 0.04-0.40). Discussion: This primary trial evidence directly supports early remdesivir in high-risk outpatients.",
        lineage="elin_covid_antiviral_primary", domain="biomedical"),

    # ── Diffusion models (multiple lineages) ──
    doc("doc_ddpm", "Denoising Diffusion Probabilistic Models (DDPM)",
        "We generate high-quality images via a denoising diffusion process.",
        "Methods: We train a model to reverse a gradual noise-adding process. Results: DDPM achieves FID competitive with GANs. Discussion: The diffusion paradigm is the foundational contribution.",
        lineage="elin_diffusion_berkeley", domain="machine_learning"),
    doc("doc_stable_diffusion", "High-Resolution Image Synthesis with Latent Diffusion Models",
        "We perform diffusion in a compressed latent space for efficient high-resolution synthesis.",
        "Methods: We train a diffusion model in a VQ-VAE latent space. Results: Latent diffusion achieves high-resolution synthesis with reduced compute. Discussion: This extends DDPM to latent space; it builds on the Berkeley diffusion paradigm.",
        lineage="elin_diffusion_munich", domain="machine_learning"),
    doc("doc_ddpm_followup", "Improved DDPM: Better Sampling and Likelihood",
        "We improve DDPM sampling efficiency and likelihood estimation.",
        "Methods: We modify the noise schedule and use a learned variance. Results: Improved sampling reduces NFEs while maintaining quality. Discussion: This is a direct improvement of the DDPM architecture from the same research program.",
        lineage="elin_diffusion_berkeley", domain="machine_learning"),

    # ── BERT variants (application vs definition) ──
    doc("doc_bert_def", "BERT: Pre-training of Deep Bidirectional Transformers",
        "We pre-train a bidirectional transformer using masked-language-modeling and next-sentence prediction.",
        "Methods: We jointly optimize masked-LM and next-sentence objectives on unlabeled text. Results: BERT achieves state-of-the-art on 11 NLP tasks. Discussion: The masked-LM objective enabling bidirectional context is the core methodological contribution.",
        lineage="elin_bert_method", domain="nlp"),
    doc("doc_bert_clinical_app", "ClinicalBERT: Applying BERT to Clinical Notes for Readmission Prediction",
        "We fine-tune BERT on clinical notes to predict 30-day hospital readmission.",
        "Methods: We fine-tune a pre-trained BERT on MIMIC-III clinical notes with a readmission classifier head. Results: ClinicalBERT improves readmission AUC by 4 points. Discussion: This is a downstream application of the pre-trained BERT model; the methodological innovation is in the clinical fine-tuning setup, not the pre-training objective.",
        lineage="elin_bert_application", domain="biomedical"),

    # ── Semantic parsing (paper discovery, paraphrase) ──
    doc("doc_semantic_parsing_kg", "Neural Semantic Parsing over Knowledge Graphs for Question Answering",
        "We translate natural-language questions into knowledge-graph queries for structured question answering.",
        "Methods: We train a sequence-to-sequence model mapping questions to SPARQL. Results: Our parser achieves 82% exact-match on a complex-QA benchmark. Discussion: Mapping natural language to structured queries enables precise fact retrieval from knowledge graphs.",
        lineage="elin_semantic_parsing", domain="nlp"),
    doc("doc_translation_memory", "Neural Alignment of Translation-Memory Segments for CAT-Assisted Translation",
        "We use neural embeddings to align translation-memory segments for computer-assisted translation.",
        "Methods: We fine-tune sentence encoders to retrieve TM matches. Results: Neural TM alignment improves translator productivity by 12%. Discussion: This retrieves from a translation memory database, not machine translation; it assists human translators.",
        lineage="elin_translation_memory", domain="nlp"),

    # ── Scaling safety (no_positive_expected controls + agenda mismatch) ──
    doc("doc_safety_ft", "Safety Fine-Tuning at Scale: Reducing Harmful Outputs",
        "We study the effect of safety-specific fine-tuning on reducing harmful outputs from large language models.",
        "Methods: We apply targeted safety fine-tuning to a 70B model and evaluate on red-team benchmarks. Results: Safety fine-tuning reduces harmful completions by 74%. Discussion: Dedicated safety training, distinct from general helpfulness tuning, is necessary to reduce harmful outputs.",
        lineage="elin_safety_finetuning", domain="machine_learning"),
    doc("doc_helpfulness_scaling", "Helpfulness Improves with Scale: A Study of Assistant Quality",
        "We show that larger language models produce more helpful assistant responses.",
        "Methods: We evaluate model sizes from 1B to 175B on helpfulness benchmarks. Results: Helpfulness scores increase monotonically with scale. Discussion: Scale reliably improves helpfulness, but this study does not measure safety outcomes.",
        lineage="elin_helpfulness_scaling", domain="machine_learning"),
    doc("doc_constitutional_ai", "Constitutional AI: Harmlessness from AI Feedback",
        "Models self-critique using a written constitution to produce harmless responses without extensive human safety labels.",
        "Methods: We train a model to revise its outputs per a constitution, then use these as preference data for RLHF. Results: Constitutional AI matches human-labeled RLHF on harmlessness. Discussion: This is a distinct alignment method from standard RLHF; it replaces human safety labels with AI self-critique.",
        lineage="elin_constitutional_ai", domain="machine_learning"),

    # ── CAR-T (cross-case distractor for oncology; also for agenda cases) ──
    doc("doc_cart_solid", "CAR-T Cell Therapy for Solid Tumors: Challenges and Progress",
        "We review strategies to improve CAR-T efficacy in solid tumors.",
        "Methods: Narrative review of CAR-T engineering approaches. Results: Armored CAR-T and locoregional delivery show promise. Discussion: CAR-T for solid tumors remains investigational; the immunosuppressive microenvironment is a key barrier.",
        lineage="elin_cart_solid", domain="biomedical"),

    # ── Cohort study (association-as-causation trap, secondary) ──
    doc("doc_statin_cohort", "Statin Use and Reduced Colorectal Cancer: A Population Cohort",
        "A large population cohort suggests statin use is associated with reduced colorectal cancer incidence.",
        "Methods: We followed 1.2M patients in a national registry for 8 years. Results: Statin users had lower colorectal cancer incidence (adjusted HR 0.72, 95% CI 0.65-0.80). Discussion: These observational data suggest an association, but residual confounding by healthy-user bias cannot be excluded; randomized confirmation is needed.",
        lineage="elin_statin_cancer_cohort", domain="biomedical"),
    doc("doc_statin_rct", "Statins and Colorectal Neoplasia: A Randomized Prevention Trial",
        "A randomized trial of statins for colorectal cancer prevention shows no effect.",
        "Methods: We randomized 3400 patients with prior adenoma to rosuvastatin or placebo. Results: Statins did not reduce adenoma recurrence (RR 0.96, 95% CI 0.82-1.13). Discussion: This randomized evidence does not support a chemopreventive effect of statins, contradicting the cohort association.",
        lineage="elin_statin_cancer_cohort", domain="biomedical"),

    # ── Sleep + cognition (agenda-adjacent; for gap analysis) ──
    doc("doc_sleep_cognition", "Sleep Duration and Cognitive Decline: An Observational Study",
        "We examine the association between sleep duration and cognitive trajectory in older adults.",
        "Methods: We followed 7800 adults aged 65+ for 10 years with serial cognitive testing. Results: Both short (<6h) and long (>9h) sleep were associated with faster cognitive decline. Discussion: The association may reflect reverse causation (early dementia disrupting sleep); causal inference requires intervention studies.",
        lineage="elin_sleep_cognition", domain="biomedical"),
]

CORPUS.extend(NEW_DOCS)
for d in NEW_DOCS:
    CORPUS_BY_ID[d["document_id"]] = d

# ────────────────────────────────────────────────────────────────────
# NEW PASSAGES
# ────────────────────────────────────────────────────────────────────

# er_003: false-support — secondary review presented as primary
PASS["er3_review_claim"] = P("doc_covid_meta_positive", "pooled evidence suggests early nirmatrelvir-ritonavir reduces hospitalization")
PASS["er3_review_disc"] = P("doc_covid_meta_positive", "This review aggregates rather than reports primary data", "discussion")
PASS["er3_primary_pos"] = P("doc_covid_remdesivir_primary", "Early remdesivir reduced COVID-19 hospitalization or death by 87%")
PASS["er3_metformin_distractor"] = P("doc_metformin_rct_positive", "Metformin reduced the recurrence of colorectal adenoma")

# er_004: false-support — supportive wording contradicted by the actual estimate
PASS["er4_survey_headline"] = P("doc_dose_scaling_review", "performance generally improves with scale")
PASS["er4_survey_estimate"] = P("doc_dose_scaling_review", "scaling alone is neither necessary nor sufficient for safety")
PASS["er4_inverse_primary"] = P("doc_inverse_scaling", "On several tasks, performance degrades with scale")

# er_005: exact identifier / acronym collision — GPT (language model vs protein)
PASS["er5_gpt_lm"] = P("doc_gpt3_lm", "GPT-3 achieves strong few-shot learning on translation, question answering, and reasoning benchmarks")
PASS["er5_gpt_protein"] = P("doc_gpt_protein", "GPT generates soluble, functional enzymes confirmed by wet-lab assays")
PASS["er5_gpt_disambig"] = P("doc_gpt_protein", "The same 'GPT' acronym appears in language modeling", "discussion")

# er_006: association presented as causation — statin cohort vs RCT
PASS["er6_rct"] = P("doc_statin_rct", "Statins did not reduce adenoma recurrence (RR 0.96, 95% CI 0.82-1.13)")
PASS["er6_cohort"] = P("doc_statin_cohort", "Statin users had lower colorectal cancer incidence (adjusted HR 0.72")
PASS["er6_cohort_caveat"] = P("doc_statin_cohort", "residual confounding by healthy-user bias cannot be excluded", "discussion")

# er_007: same intervention, wrong outcome — vitamin D fracture vs HbA1c (cross from empagliflozin)
PASS["er7_vitd_combined_pos"] = P("doc_vitd_combined", "combination reduced hip fractures (HR 0.57")
PASS["er7_vitd_alone_wrong"] = P("doc_vitd_combined", "vitamin D alone without calcium was not tested here", "discussion")
PASS["er7_empagliflozin_distractor"] = P("doc_empagliflozin", "modestly reduced HbA1c")

# er_008: qualified effect presented as unconditional — vitamin D+calcium (benefit ONLY in institutionalized elderly, not general)
PASS["er8_vitd_combined_result"] = P("doc_vitd_combined", "combination reduced hip fractures (HR 0.57, 95% CI 0.42-0.77) and non-vertebral fractures")
PASS["er8_vitd_population_caveat"] = P("doc_vitd_combined", "benefit is specific to the combined regimen in an institutionalized elderly population", "discussion")
PASS["er8_vitd_alone_general"] = P("doc_vitd_alone", "high-dose vitamin D monotherapy has no fracture benefit")

# cr_003: contradiction — statin RCT null vs cohort positive
PASS["cr3_rct_null"] = P("doc_statin_rct", "Statins did not reduce adenoma recurrence (RR 0.96, 95% CI 0.82-1.13)")
PASS["cr3_cohort_positive"] = P("doc_statin_cohort", "Statin users had lower colorectal cancer incidence (adjusted HR 0.72")

# cr_004: contradiction — vitamin D alone (VITAL null)
PASS["cr4_vital_null"] = P("doc_vitd_alone", "Vitamin D alone did not reduce total fractures (HR 0.97, 95% CI 0.88-1.06)")
PASS["cr4_combined_positive"] = P("doc_vitd_combined", "combination reduced hip fractures (HR 0.57")

# cr_005: wrong population — pediatric SSRI vs adult SSRI (contradiction on population)
PASS["cr5_adult_pos"] = P("doc_ssri_adult", "Fluoxetine reduced HAM-D scores by 6.2 points (95% CI 4.1-8.3)")
PASS["cr5_pediatric_risk"] = P("doc_ssri_pediatric", "increased treatment-emergent suicidal ideation (OR 1.8, 95% CI 1.0-3.2)")
PASS["cr5_pediatric_population"] = P("doc_ssri_pediatric", "risk-benefit profile in adolescents differs fundamentally from adults", "discussion")

# cr_006: review vs primary (COVID antiviral)
PASS["cr6_primary"] = P("doc_covid_remdesivir_primary", "Early remdesivir reduced COVID-19 hospitalization or death by 87%")
PASS["cr6_review_aggregate"] = P("doc_covid_meta_positive", "This review aggregates rather than reports primary data", "discussion")

# mps_003: diffusion lineages (Berkeley x2 vs Munich)
PASS["mps3_ddpm"] = P("doc_ddpm", "diffusion paradigm is the foundational contribution", "discussion")
PASS["mps3_improved_ddpm"] = P("doc_ddpm_followup", "direct improvement of the DDPM architecture from the same research program", "discussion")
PASS["mps3_stable_diffusion"] = P("doc_stable_diffusion", "extends DDPM to latent space; it builds on the Berkeley diffusion paradigm", "discussion")

# mps_004: BERT method vs application (method lineage vs application lineage)
PASS["mps4_bert_def"] = P("doc_bert_def", "masked-LM objective enabling bidirectional context is the core methodological contribution", "discussion")
PASS["mps4_clinical_bert"] = P("doc_bert_clinical_app", "downstream application of the pre-trained BERT model", "discussion")
PASS["mps4_gpt_lm"] = P("doc_gpt3_lm", "GPT-3 achieves strong few-shot learning on translation")

# mps_005: same lineage presented as independent (DDPM + improved-DDPM are same Berkeley lineage)
PASS["mps5_ddpm"] = P("doc_ddpm", "diffusion paradigm is the foundational contribution", "discussion")
PASS["mps5_improved_ddpm"] = P("doc_ddpm_followup", "direct improvement of the DDPM architecture from the same research program", "discussion")
PASS["mps5_stable_diffusion"] = P("doc_stable_diffusion", "extends DDPM to latent space")

# mps_006: review vs primary coverage (COVID)
PASS["mps6_primary"] = P("doc_covid_remdesivir_primary", "Early remdesivir reduced COVID-19 hospitalization or death by 87%")
PASS["mps6_review"] = P("doc_covid_meta_positive", "pooled evidence suggests early nirmatrelvir-ritonavir reduces hospitalization")
PASS["mps6_cart_distractor"] = P("doc_cart_solid", "Armored CAR-T and locoregional delivery show promise")

# pd_002: low-overlap paraphrase (semantic parsing for QA via KG)
PASS["pd2_sp_kg"] = P("doc_semantic_parsing_kg", "Mapping natural language to structured queries enables precise fact retrieval from knowledge graphs", "discussion")
PASS["pd2_tm_distractor"] = P("doc_translation_memory", "Neural TM alignment improves translator productivity")

# pd_003: paraphrase — efficient training (ZeRO paraphrased query)
PASS["pd3_zero"] = P("doc_zero", "technique addresses the memory bottleneck that limits training very large models", "discussion")
PASS["pd3_simclr_distractor"] = P("doc_simclr", "SimCLR achieves state-of-the-art on ImageNet linear-eval")

# pd_004: exact identifier collision (DDPM)
PASS["pd4_ddpm_exact"] = P("doc_ddpm", "DDPM achieves FID competitive with GANs")
PASS["pd4_stable_diffusion_distractor"] = P("doc_stable_diffusion", "Latent diffusion achieves high-resolution synthesis with reduced compute")

# mr_002: method application vs definition (BERT method vs clinical BERT)
PASS["mr2_bert_def"] = P("doc_bert_def", "jointly optimize masked-LM and next-sentence objectives on unlabeled text", "methods")
PASS["mr2_clinical_bert"] = P("doc_bert_clinical_app", "fine-tune a pre-trained BERT on MIMIC-III clinical notes", "methods")
PASS["mr2_gpt_distractor"] = P("doc_gpt3_lm", "GPT-3 achieves strong few-shot learning")

# mr_003: method application vs definition (contrastive)
PASS["mr3_simclr_method"] = P("doc_simclr", "contrastive loss formulation is the core contribution", "discussion")
PASS["mr3_medical_app"] = P("doc_simclr_medical_app", "application of an existing method rather than a new contrastive loss", "discussion")

# rga_002: same topic different agenda (helpfulness vs safety) — no_positive_expected
PASS["rga2_helpfulness"] = P("doc_helpfulness_scaling", "Helpfulness scores increase monotonically with scale")
PASS["rga2_safety_ft"] = P("doc_safety_ft", "Safety fine-tuning reduces harmful completions by 74%")
PASS["rga2_constitutional"] = P("doc_constitutional_ai", "Constitutional AI matches human-labeled RLHF on harmlessness")

# rga_003: agenda mismatch — sleep and cognition (association vs causation agenda) — no_positive_expected
PASS["rga3_sleep_assoc"] = P("doc_sleep_cognition", "Both short (<6h) and long (>9h) sleep were associated with faster cognitive decline")
PASS["rga3_sleep_caveat"] = P("doc_sleep_cognition", "association may reflect reverse causation (early dementia disrupting sleep)", "discussion")
PASS["rga3_cart_distractor"] = P("doc_cart_solid", "CAR-T for solid tumors remains investigational")

# Update PASSAGES_BY_ID for the validator
PASSAGES_BY_ID = {p["passage_id"]: p for p in PASS.values()}

# CRITICAL: write the expanded PASS back to the base module so build_case (which
# closes over base.PASS) sees the new passages. Without this, KeyError on new keys.
base.PASS = PASS


# ────────────────────────────────────────────────────────────────────
# NEW CASES (21)
# ────────────────────────────────────────────────────────────────────

NEW_CASES = [
    # ── er_003: secondary review presented as primary ──
    build_case("diag_er_003", "evidence_retrieval", "biomedical",
        "Find a passage with primary evidence that early antiviral treatment reduces COVID-19 hospitalization.",
        "passage", "retrieval_ranking", ["false_support"], ["review_vs_primary"],
        pool_passage_keys=["er3_review_claim", "er3_review_disc", "er3_primary_pos", "er3_metformin_distractor"],
        pos_keys=["er3_primary_pos"],
        judgment_grades={PASS["er3_review_claim"]["passage_id"]: (1, {"evidence": 1}), PASS["er3_review_disc"]["passage_id"]: (2, {"evidence": 2}),
                         PASS["er3_primary_pos"]["passage_id"]: (3, {}), PASS["er3_metformin_distractor"]["passage_id"]: (0, {})},
        claim_dims={"population": "high-risk outpatients", "intervention_or_exposure": "early antiviral", "comparison": "placebo", "outcome": "COVID-19 hospitalization", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "primary evidence required"},
        neg_failed_dims=[{"unit_id": PASS["er3_review_claim"]["passage_id"], "failed_dimensions": ["study_design_requirement"]}, {"unit_id": PASS["er3_review_disc"]["passage_id"], "failed_dimensions": ["study_design_requirement"]}, {"unit_id": PASS["er3_metformin_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]}],
        rationale="The review claim looks supportive but aggregates rather than reports primary data. The RCT is the genuine primary positive.",
        origin_provenance="Review-presented-as-primary false-support trap + cross-case distractor.",
        scenario_id="ssn_review_as_primary_01", leakage_group="lg_covid_antiviral", document_family="df_covid"),

    # ── er_004: supportive wording contradicted by estimate ──
    build_case("diag_er_004", "evidence_retrieval", "machine_learning",
        "Find a passage showing that scaling model size improves safety-relevant capabilities.",
        "passage", "retrieval_ranking", ["false_support"], ["supportive_language_without_support"],
        pool_passage_keys=["er4_survey_headline", "er4_survey_estimate", "er4_inverse_primary"],
        pos_keys=["er4_inverse_primary"],
        judgment_grades={PASS["er4_survey_headline"]["passage_id"]: (1, {"evidence": 1}), PASS["er4_survey_estimate"]["passage_id"]: (2, {"evidence": 2}), PASS["er4_inverse_primary"]["passage_id"]: (3, {})},
        claim_dims={"population": "language models", "intervention_or_exposure": "scaling model size", "comparison": "smaller models", "outcome": "safety capabilities", "direction_or_polarity": "improves", "causal_vs_associational": "causal_claim", "study_design_requirement": "controlled benchmark", "qualifiers": "safety, not helpfulness"},
        neg_failed_dims=[{"unit_id": PASS["er4_survey_headline"]["passage_id"], "failed_dimensions": ["direction_or_polarity"]}, {"unit_id": PASS["er4_survey_estimate"]["passage_id"], "failed_dimensions": ["qualifiers"]}],
        rationale="Survey headline says 'performance improves with scale' but the estimate itself contradicts the safety claim. Inverse-scaling is the genuine positive for safety.",
        origin_provenance="Supportive-wording-contradicted-by-estimate false-support.",
        scenario_id="ssn_wording_vs_estimate_01", leakage_group="lg_scaling_safety", document_family="df_scaling"),

    # ── er_005: exact identifier / acronym collision (GPT) ──
    build_case("diag_er_005", "evidence_retrieval", "machine_learning",
        "Find passages showing GPT's few-shot learning capability.",
        "passage", "retrieval_ranking", ["false_support", "agenda_mismatch"], ["exact_identifier_or_acronym_collision"],
        pool_passage_keys=["er5_gpt_lm", "er5_gpt_protein", "er5_gpt_disambig"],
        pos_keys=["er5_gpt_lm"],
        judgment_grades={PASS["er5_gpt_lm"]["passage_id"]: (3, {}), PASS["er5_gpt_protein"]["passage_id"]: (1, {"evidence": 1}), PASS["er5_gpt_disambig"]["passage_id"]: (1, {})},
        claim_dims={"population": "language models", "intervention_or_exposure": "GPT", "comparison": "n/a", "outcome": "few-shot learning", "direction_or_polarity": "improves", "causal_vs_associational": "descriptive", "study_design_requirement": "benchmark evaluation", "qualifiers": "GPT as language model, not protein"},
        neg_failed_dims=[{"unit_id": PASS["er5_gpt_protein"]["passage_id"], "failed_dimensions": ["meaning_or_domain"]}, {"unit_id": PASS["er5_gpt_disambig"]["passage_id"], "failed_dimensions": ["meaning_or_domain"]}],
        rationale="Both passages share the exact acronym 'GPT' but refer to different things (language model vs protein transformer). The collision is not removable by a trivial domain keyword in the query.",
        origin_provenance="Exact-identifier collision: same acronym, minimal disambiguating context, different scientific meaning.",
        scenario_id="ssn_acronym_gpt_01", leakage_group="lg_gpt_collision", document_family="df_gpt"),

    # ── er_006: association presented as causation (statin) ──
    build_case("diag_er_006", "evidence_retrieval", "biomedical",
        "Find passages with randomized evidence that statins causally reduce colorectal neoplasia.",
        "passage", "retrieval_ranking", ["false_support"], ["supportive_language_without_support"],
        pool_passage_keys=["er6_rct", "er6_cohort", "er6_cohort_caveat"],
        pos_keys=["er6_rct"],
        judgment_grades={PASS["er6_rct"]["passage_id"]: (3, {}), PASS["er6_cohort"]["passage_id"]: (1, {"evidence": 1}), PASS["er6_cohort_caveat"]["passage_id"]: (2, {"evidence": 2})},
        claim_dims={"population": "adults with prior adenoma", "intervention_or_exposure": "statins", "comparison": "placebo", "outcome": "colorectal neoplasia", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "causal claim; RCT required"},
        neg_failed_dims=[{"unit_id": PASS["er6_cohort"]["passage_id"], "failed_dimensions": ["causal_vs_associational", "study_design_requirement"]}, {"unit_id": PASS["er6_cohort_caveat"]["passage_id"], "failed_dimensions": ["study_design_requirement"]}],
        rationale="The cohort shows an association with supportive wording ('lower incidence') but the RCT is null. For a causal claim, the cohort is false support. The caveat is qualifying.",
        origin_provenance="Association-as-causation false-support (reference pattern: causal claim, RCT positive/null, cohort false-support).",
        scenario_id="ssn_causal_statin_01", leakage_group="lg_statin_cancer", document_family="df_statin"),

    # ── er_007: same intervention wrong outcome (vitamin D fracture vs not-tested-alone) ──
    build_case("diag_er_007", "evidence_retrieval", "biomedical",
        "Find passages showing vitamin D ALONE reduces fractures.",
        "passage", "retrieval_ranking", ["false_support", "agenda_mismatch"], ["same_intervention_wrong_outcome"],
        pool_passage_keys=["er7_vitd_combined_pos", "er7_vitd_alone_wrong", "er7_empagliflozin_distractor"],
        pos_keys=["er7_vitd_combined_pos"],
        judgment_grades={PASS["er7_vitd_combined_pos"]["passage_id"]: (1, {"evidence": 1}), PASS["er7_vitd_alone_wrong"]["passage_id"]: (2, {"evidence": 2}), PASS["er7_empagliflozin_distractor"]["passage_id"]: (0, {})},
        claim_dims={"population": "adults", "intervention_or_exposure": "vitamin D alone", "comparison": "placebo", "outcome": "fractures", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "vitamin D monotherapy, not combined"},
        neg_failed_dims=[{"unit_id": PASS["er7_vitd_combined_pos"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}, {"unit_id": PASS["er7_empagliflozin_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]}],
        rationale="The combined-regimen result (grade 1) is vitamin D + calcium, not vitamin D alone. The discussion caveat (grade 2) explicitly says D-alone was not tested. Empagliflozin is a cross-case distractor. NOTE: this case has no grade-3 positive because no RCT shows vitamin D ALONE reduces fractures — it's a no-positive-expected case.",
        origin_provenance="Same-intervention-wrong-formulation agenda mismatch.",
        scenario_id="ssn_vitd_alone_01", leakage_group="lg_vitd_fracture", document_family="df_vitd"),

    # ── er_008: qualified effect presented as unconditional ──
    build_case("diag_er_008", "evidence_retrieval", "biomedical",
        "Find passages showing vitamin D plus calcium reduces fractures in ALL elderly adults.",
        "passage", "retrieval_ranking", ["false_support"], ["supportive_language_without_support"],
        pool_passage_keys=["er8_vitd_combined_result", "er8_vitd_population_caveat", "er8_vitd_alone_general"],
        pos_keys=["er8_vitd_combined_result"],
        judgment_grades={PASS["er8_vitd_combined_result"]["passage_id"]: (1, {"evidence": 1}), PASS["er8_vitd_population_caveat"]["passage_id"]: (3, {}), PASS["er8_vitd_alone_general"]["passage_id"]: (0, {})},
        claim_dims={"population": "all elderly adults", "intervention_or_exposure": "vitamin D plus calcium", "comparison": "placebo", "outcome": "fractures", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "unconditional claim for ALL elderly"},
        neg_failed_dims=[{"unit_id": PASS["er8_vitd_combined_result"]["passage_id"], "failed_dimensions": ["population"]}, {"unit_id": PASS["er8_vitd_alone_general"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}],
        rationale="The combined result shows a benefit but ONLY in institutionalized elderly. The claim says 'ALL elderly.' The population caveat (grade 3) is the correct evidence. VITAL null shows D-alone doesn't work in the general population. Qualified-effect-presented-as-unconditional.",
        origin_provenance="Qualified effect (institutionalized only) presented as unconditional (all elderly).",
        scenario_id="ssn_qualified_unconditional_01", leakage_group="lg_vitd_fracture", document_family="df_vitd"),

    # ── cr_003: contradiction — statin RCT null vs cohort positive ──
    build_case("diag_cr_003", "contradiction_retrieval", "biomedical",
        "Find passages that contradict the claim that statins reduce colorectal cancer.",
        "passage", "retrieval_ranking", ["missed_contradiction"], ["negated_or_qualified_result"],
        pool_passage_keys=["cr3_rct_null", "cr3_cohort_positive"],
        pos_keys=["cr3_rct_null"],
        contradiction_keys=["cr3_rct_null"],
        judgment_grades={PASS["cr3_rct_null"]["passage_id"]: (3, {}), PASS["cr3_cohort_positive"]["passage_id"]: (1, {"evidence": 1})},
        claim_dims={"population": "adults with prior adenoma", "intervention_or_exposure": "statins", "comparison": "placebo", "outcome": "colorectal neoplasia", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "none"},
        neg_failed_dims=[{"unit_id": PASS["cr3_cohort_positive"]["passage_id"], "failed_dimensions": ["causal_vs_associational", "study_design_requirement"]}],
        rationale="The RCT null result contradicts the claim. The cohort positive is associational and must not drown out the RCT contradiction.",
        origin_provenance="RCT null as contradiction source.",
        scenario_id="ssn_contradiction_statin_01", leakage_group="lg_statin_cancer", document_family="df_statin"),

    # ── cr_004: contradiction — vitamin D alone VITAL null ──
    build_case("diag_cr_004", "contradiction_retrieval", "biomedical",
        "Find passages that contradict the claim that vitamin D alone reduces fractures.",
        "passage", "retrieval_ranking", ["missed_contradiction"], ["negated_or_qualified_result"],
        pool_passage_keys=["cr4_vital_null", "cr4_combined_positive"],
        pos_keys=["cr4_vital_null"],
        contradiction_keys=["cr4_vital_null"],
        judgment_grades={PASS["cr4_vital_null"]["passage_id"]: (3, {}), PASS["cr4_combined_positive"]["passage_id"]: (1, {"evidence": 1})},
        claim_dims={"population": "community-dwelling adults", "intervention_or_exposure": "vitamin D alone", "comparison": "placebo", "outcome": "fractures", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "vitamin D monotherapy"},
        neg_failed_dims=[{"unit_id": PASS["cr4_combined_positive"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}],
        rationale="VITAL null (D-alone) contradicts the claim. The combined-regimen result is not a contradiction (different intervention).",
        origin_provenance="Monotherapy null as contradiction.",
        scenario_id="ssn_contradiction_vitd_01", leakage_group="lg_vitd_fracture", document_family="df_vitd"),

    # ── cr_005: wrong population — pediatric SSRI suicide risk vs adult benefit ──
    build_case("diag_cr_005", "contradiction_retrieval", "biomedical",
        "Find passages that contradict the claim that SSRIs are safe and effective for adolescent depression.",
        "passage", "retrieval_ranking", ["missed_contradiction", "agenda_mismatch"], ["same_topic_wrong_population"],
        pool_passage_keys=["cr5_adult_pos", "cr5_pediatric_risk", "cr5_pediatric_population"],
        pos_keys=["cr5_pediatric_risk"],
        contradiction_keys=["cr5_pediatric_risk"],
        judgment_grades={PASS["cr5_adult_pos"]["passage_id"]: (1, {"evidence": 1}), PASS["cr5_pediatric_risk"]["passage_id"]: (3, {}), PASS["cr5_pediatric_population"]["passage_id"]: (3, {})},
        claim_dims={"population": "adolescents aged 12-17", "intervention_or_exposure": "SSRIs", "comparison": "placebo", "outcome": "safety and efficacy", "direction_or_polarity": "mixed", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "adolescent population specifically"},
        neg_failed_dims=[{"unit_id": PASS["cr5_adult_pos"]["passage_id"], "failed_dimensions": ["population"]}],
        rationale="The adult SSRI benefit (grade 1) fails on population — it does not apply to adolescents. The pediatric suicide-risk signal (grade 3) directly contradicts 'safe.' This is a wrong-population trap: intervention aligned, outcome aligned, direction aligned, population is the principal failing dimension.",
        origin_provenance="Wrong-population contradiction: adult evidence cited for adolescent claim.",
        scenario_id="ssn_wrong_population_ssri_01", leakage_group="lg_ssri_population", document_family="df_ssri"),

    # ── cr_006: review vs primary contradiction source ──
    build_case("diag_cr_006", "contradiction_retrieval", "biomedical",
        "Find primary-trial passages that report early antiviral efficacy for COVID-19.",
        "passage", "retrieval_ranking", ["missed_contradiction"], ["review_vs_primary"],
        pool_passage_keys=["cr6_primary", "cr6_review_aggregate"],
        pos_keys=["cr6_primary"],
        contradiction_keys=["cr6_review_aggregate"],
        judgment_grades={PASS["cr6_primary"]["passage_id"]: (3, {}), PASS["cr6_review_aggregate"]["passage_id"]: (2, {"evidence": 2})},
        claim_dims={"population": "high-risk outpatients", "intervention_or_exposure": "early antiviral", "comparison": "placebo", "outcome": "COVID-19 hospitalization", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "primary evidence required"},
        neg_failed_dims=[{"unit_id": PASS["cr6_review_aggregate"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}],
        rationale="The RCT is primary; the review aggregates and should not be mistaken for primary evidence.",
        origin_provenance="Review-vs-primary distinction in contradiction context.",
        scenario_id="ssn_review_vs_primary_contradiction_01", leakage_group="lg_covid_antiviral", document_family="df_covid"),

    # ── mps_003: diffusion lineages (Berkeley x2 vs Munich) ──
    build_case("diag_mps_003", "multi_paper_synthesis", "machine_learning",
        "Retrieve diverse evidence on diffusion-based image generation from distinct research lineages.",
        "paper_or_abstract", "discovery_ranking", ["redundancy", "missed_relevant_evidence"], ["multiple_papers_one_lineage"],
        pool_passage_keys=["mps3_ddpm", "mps3_improved_ddpm", "mps3_stable_diffusion"],
        pos_keys=["mps3_ddpm", "mps3_stable_diffusion"],
        judgment_grades={PASS["mps3_ddpm"]["passage_id"]: (3, {}), PASS["mps3_improved_ddpm"]["passage_id"]: (2, {}), PASS["mps3_stable_diffusion"]["passage_id"]: (3, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps3_improved_ddpm"]["passage_id"], "failed_dimensions": ["evidence_lineage"]}],
        rationale="DDPM and Improved-DDPM are Berkeley lineage; Stable Diffusion is Munich (independent). A synthesis must represent both lineages, not collapse the two Berkeley papers.",
        origin_provenance="Same-lineage-vs-independent-lineage (diffusion).",
        scenario_id="ssn_lineage_diffusion_01", leakage_group="lg_diffusion_diversity", document_family="df_diffusion"),

    # ── mps_004: BERT method vs application lineage ──
    build_case("diag_mps_004", "multi_paper_synthesis", "nlp",
        "Retrieve diverse evidence on transformer pre-training objectives from distinct lineages.",
        "paper_or_abstract", "discovery_ranking", ["redundancy", "missed_relevant_evidence"], ["multiple_papers_one_lineage"],
        pool_passage_keys=["mps4_bert_def", "mps4_clinical_bert", "mps4_gpt_lm"],
        pos_keys=["mps4_bert_def", "mps4_gpt_lm"],
        judgment_grades={PASS["mps4_bert_def"]["passage_id"]: (3, {}), PASS["mps4_clinical_bert"]["passage_id"]: (2, {}), PASS["mps4_gpt_lm"]["passage_id"]: (3, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps4_clinical_bert"]["passage_id"], "failed_dimensions": ["evidence_lineage", "evidence_granularity"]}],
        rationale="BERT (method lineage) and GPT-3 (different method lineage) are the diverse positives. ClinicalBERT is an application of BERT, not a distinct lineage.",
        origin_provenance="Method-vs-application lineage diversity.",
        scenario_id="ssn_lineage_bert_01", leakage_group="lg_bert_diversity", document_family="df_bert"),

    # ── mps_005: same lineage presented as independent (DDPM + Improved-DDPM = Berkeley) ──
    build_case("diag_mps_005", "multi_paper_synthesis", "machine_learning",
        "Find two papers claiming to independently establish the diffusion paradigm.",
        "paper_or_abstract", "discovery_ranking", ["redundancy"], ["multiple_papers_one_lineage"],
        pool_passage_keys=["mps5_ddpm", "mps5_improved_ddpm", "mps5_stable_diffusion"],
        pos_keys=["mps5_ddpm", "mps5_stable_diffusion"],
        judgment_grades={PASS["mps5_ddpm"]["passage_id"]: (3, {}), PASS["mps5_improved_ddpm"]["passage_id"]: (1, {}), PASS["mps5_stable_diffusion"]["passage_id"]: (3, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps5_improved_ddpm"]["passage_id"], "failed_dimensions": ["evidence_lineage"]}],
        rationale="DDPM and Improved-DDPM are explicitly the SAME Berkeley lineage. A system presenting them as independent commits lineage redundancy. Stable Diffusion is the genuine second independent lineage.",
        origin_provenance="Same-evidence-lineage-presented-as-independent.",
        scenario_id="ssn_lineage_not_independent_01", leakage_group="lg_diffusion_lineage", document_family="df_diffusion"),

    # ── mps_006: review vs primary coverage ──
    build_case("diag_mps_006", "multi_paper_synthesis", "biomedical",
        "Retrieve diverse primary evidence on early antiviral treatment for COVID-19.",
        "paper_or_abstract", "discovery_ranking", ["redundancy", "missed_relevant_evidence"], ["review_vs_primary"],
        pool_passage_keys=["mps6_primary", "mps6_review", "mps6_cart_distractor"],
        pos_keys=["mps6_primary"],
        judgment_grades={PASS["mps6_primary"]["passage_id"]: (3, {}), PASS["mps6_review"]["passage_id"]: (2, {}), PASS["mps6_cart_distractor"]["passage_id"]: (0, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mps6_review"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}, {"unit_id": PASS["mps6_cart_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]}],
        rationale="Primary RCT is the target. The review aggregates. CAR-T is a cross-case distractor.",
        origin_provenance="Review-vs-primary coverage + cross-case distractor.",
        scenario_id="ssn_review_vs_primary_synth_01", leakage_group="lg_covid_antiviral", document_family="df_covid"),

    # ── pd_002: paraphrase (semantic parsing for QA) ──
    build_case("diag_pd_002", "paper_discovery", "nlp",
        "Find papers on converting natural-language questions into structured database queries.",
        "paper_or_abstract", "discovery_ranking", ["missed_relevant_evidence"], ["paraphrase_low_overlap"],
        pool_passage_keys=["pd2_sp_kg", "pd2_tm_distractor"],
        pos_keys=["pd2_sp_kg"],
        judgment_grades={PASS["pd2_sp_kg"]["passage_id"]: (3, {}), PASS["pd2_tm_distractor"]["passage_id"]: (1, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["pd2_tm_distractor"]["passage_id"], "failed_dimensions": ["meaning_or_domain"]}],
        rationale="The query paraphrases 'semantic parsing' as 'converting questions into structured queries.' The translation-memory paper is risk-shaped (adjacent NLP, different task) rather than generic off-topic.",
        origin_provenance="Paraphrase + risk-shaped same-domain-different-task negative.",
        scenario_id="ssn_paraphrase_sp_01", leakage_group="lg_semantic_parsing", document_family="df_sp"),

    # ── pd_003: paraphrase (efficient training — ZeRO) ──
    build_case("diag_pd_003", "paper_discovery", "machine_learning",
        "Find papers on reducing the memory cost of training very large models.",
        "paper_or_abstract", "discovery_ranking", ["missed_relevant_evidence"], ["paraphrase_low_overlap"],
        pool_passage_keys=["pd3_zero", "pd3_simclr_distractor"],
        pos_keys=["pd3_zero"],
        judgment_grades={PASS["pd3_zero"]["passage_id"]: (3, {}), PASS["pd3_simclr_distractor"]["passage_id"]: (0, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["pd3_simclr_distractor"]["passage_id"], "failed_dimensions": ["meaning_or_domain"]}],
        rationale="Query paraphrases 'memory management' as 'reducing memory cost.' SimCLR is cross-case (contrastive learning, not memory).",
        origin_provenance="Paraphrase + cross-case distractor.",
        scenario_id="ssn_paraphrase_zero_01", leakage_group="lg_efficient_training", document_family="df_zero"),

    # ── pd_004: exact identifier (DDPM) ──
    build_case("diag_pd_004", "paper_discovery", "machine_learning",
        "Find papers on DDPM.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["exact_identifier_or_acronym_collision"],
        pool_passage_keys=["pd4_ddpm_exact", "pd4_stable_diffusion_distractor"],
        pos_keys=["pd4_ddpm_exact"],
        judgment_grades={PASS["pd4_ddpm_exact"]["passage_id"]: (3, {}), PASS["pd4_stable_diffusion_distractor"]["passage_id"]: (2, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["pd4_stable_diffusion_distractor"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}],
        rationale="Exact identifier 'DDPM.' Stable Diffusion is related but not DDPM itself.",
        origin_provenance="Exact identifier retrieval.",
        scenario_id="ssn_exact_id_ddpm_01", leakage_group="lg_diffusion_exact", document_family="df_diffusion"),

    # ── mr_002: method application vs definition (BERT vs ClinicalBERT) ──
    build_case("diag_mr_002", "method_retrieval", "nlp",
        "Find the method paper defining the BERT pre-training objective.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["method_application_vs_definition"],
        pool_passage_keys=["mr2_bert_def", "mr2_clinical_bert", "mr2_gpt_distractor"],
        pos_keys=["mr2_bert_def"],
        judgment_grades={PASS["mr2_bert_def"]["passage_id"]: (3, {}), PASS["mr2_clinical_bert"]["passage_id"]: (2, {}), PASS["mr2_gpt_distractor"]["passage_id"]: (1, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mr2_clinical_bert"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}, {"unit_id": PASS["mr2_gpt_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}],
        rationale="BERT defines the masked-LM objective. ClinicalBERT applies it. GPT is a different architecture.",
        origin_provenance="Method-vs-application (BERT).",
        scenario_id="ssn_method_bert_01", leakage_group="lg_bert_method", document_family="df_bert"),

    # ── mr_003: method application vs definition (contrastive) ──
    build_case("diag_mr_003", "method_retrieval", "machine_learning",
        "Find the method paper defining the contrastive learning formulation.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["method_application_vs_definition"],
        pool_passage_keys=["mr3_simclr_method", "mr3_medical_app"],
        pos_keys=["mr3_simclr_method"],
        judgment_grades={PASS["mr3_simclr_method"]["passage_id"]: (3, {}), PASS["mr3_medical_app"]["passage_id"]: (2, {})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["mr3_medical_app"]["passage_id"], "failed_dimensions": ["evidence_granularity"]}],
        rationale="SimCLR defines the contrastive loss. The medical-imaging paper applies it.",
        origin_provenance="Method-vs-application (contrastive).",
        scenario_id="ssn_method_contrastive_01", leakage_group="lg_contrastive_method", document_family="df_contrastive"),

    # ── rga_002: same topic different agenda (helpfulness vs safety) — NO POSITIVE EXPECTED ──
    build_case("diag_rga_002", "research_gap_analysis", "machine_learning",
        "Find papers on how SCALING model size (not fine-tuning) improves SAFETY of language models.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["same_topic_different_agenda"],
        pool_passage_keys=["rga2_helpfulness", "rga2_safety_ft", "rga2_constitutional"],
        pos_keys=[],  # no positive — all fail the agenda
        judgment_grades={PASS["rga2_helpfulness"]["passage_id"]: (1, {"evidence": 1}), PASS["rga2_safety_ft"]["passage_id"]: (2, {"evidence": 2}), PASS["rga2_constitutional"]["passage_id"]: (2, {"evidence": 2})},
        claim_dims=None,
        neg_failed_dims=[{"unit_id": PASS["rga2_helpfulness"]["passage_id"], "failed_dimensions": ["outcome"]}, {"unit_id": PASS["rga2_safety_ft"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}, {"unit_id": PASS["rga2_constitutional"]["passage_id"], "failed_dimensions": ["intervention_or_exposure"]}],
        rationale="Query asks about SCALING improving SAFETY. Helpfulness-scaling (grade 1) is wrong outcome. Safety-finetuning (grade 2) is wrong intervention (fine-tuning, not scaling). Constitutional AI (grade 2) is also wrong intervention. No passage addresses scaling-for-safety — a genuine gap. NO_POSITIVE_EXPECTED.",
        origin_provenance="No-positive-expected gap case: scaling-safety intersection is empty in this corpus.",
        scenario_id="ssn_gap_scaling_safety_01", leakage_group="lg_scaling_safety_gap", document_family="df_alignment"),

    # ── rga_003: agenda mismatch (sleep-cognition association vs causation) — NO POSITIVE EXPECTED ──
    build_case("diag_rga_003", "research_gap_analysis", "biomedical",
        "Find randomized trials showing sleep interventions causally reduce cognitive decline.",
        "paper_or_abstract", "discovery_ranking", ["agenda_mismatch"], ["same_topic_different_agenda"],
        pool_passage_keys=["rga3_sleep_assoc", "rga3_sleep_caveat", "rga3_cart_distractor"],
        pos_keys=[],
        judgment_grades={PASS["rga3_sleep_assoc"]["passage_id"]: (1, {"evidence": 1}), PASS["rga3_sleep_caveat"]["passage_id"]: (2, {"evidence": 2}), PASS["rga3_cart_distractor"]["passage_id"]: (0, {})},
        claim_dims={"population": "older adults", "intervention_or_exposure": "sleep intervention", "comparison": "control", "outcome": "cognitive decline", "direction_or_polarity": "reduces", "causal_vs_associational": "causal_claim", "study_design_requirement": "randomized trial", "qualifiers": "causal intervention, not observational"},
        neg_failed_dims=[{"unit_id": PASS["rga3_sleep_assoc"]["passage_id"], "failed_dimensions": ["causal_vs_associational", "study_design_requirement"]}, {"unit_id": PASS["rga3_sleep_caveat"]["passage_id"], "failed_dimensions": ["study_design_requirement"]}, {"unit_id": PASS["rga3_cart_distractor"]["passage_id"], "failed_dimensions": ["intervention_or_exposure", "outcome"]}],
        rationale="Query asks for RCTs of sleep interventions on cognition. The only evidence is observational (grade 1) with a caveat about reverse causation (grade 2). No randomized trial exists in the corpus — genuine gap. NO_POSITIVE_EXPECTED.",
        origin_provenance="No-positive-expected gap case: no RCT of sleep intervention for cognition exists.",
        scenario_id="ssn_gap_sleep_cognition_01", leakage_group="lg_sleep_cognition_gap", document_family="df_sleep"),
]


def build():
    """Emit all 30 cases (9 seed + 21 expansion) as the combined output."""
    ALL_CASES = CASES_BASE + NEW_CASES
    ALL_CORPUS = CORPUS  # base already extended

    OUTDIR.mkdir(parents=True, exist_ok=True)
    dump_jsonl(ALL_CORPUS, OUTDIR / "p1d2_diagnostic_seed_sources.jsonl")
    dump_jsonl(ALL_CASES, OUTDIR / "p1d2_diagnostic_seed_cases.jsonl")
    derived_judgments = []
    for c in ALL_CASES:
        derived_judgments.extend(c["relevance_judgments"])
    dump_jsonl(derived_judgments, OUTDIR / "p1d2_diagnostic_seed_judgments.jsonl")

    from collections import Counter
    families = Counter(c["task_family"] for c in ALL_CASES)
    case_modes = Counter(c["case_mode"] for c in ALL_CASES)

    def fp(p):
        return sha256((OUTDIR / p).read_bytes().decode("utf-8"))

    manifest = {
        "manifest_version": "p1d2_diagnostic_seed_manifest_v3", "status": "draft",
        "created": "2026-07-22", "benchmark_role": "diagnostic",
        "case_count": len(ALL_CASES), "judgment_count": len(derived_judgments),
        "source_document_count": len(ALL_CORPUS), "task_family_counts": dict(sorted(families.items())),
        "case_mode_counts": dict(sorted(case_modes.items())),
        "schema_versions": {"case": SV_CASE, "judgment": SV_JUDG},
        "artifact_hashes": {
            "sources": fp("p1d2_diagnostic_seed_sources.jsonl"),
            "cases": fp("p1d2_diagnostic_seed_cases.jsonl"),
            "judgments": fp("p1d2_diagnostic_seed_judgments.jsonl"),
        },
        "review_status_note": "All judgments authored_provisional, single-pass, non-scoreable, non-sealable. Requires external dual review before scoring.",
        "authoring_blindness": {"candidate_retrieval_outputs_visible_to_author": False, "embedding_model_evaluated": False, "reranker_evaluated": False, "policy_specific_tuning": False},
        "candidate_pool_design": "exhaustive per-case pools with cross-case distractors; every pool unit judged exactly once",
        "judgment_authority": "cases are authoritative; judgments JSONL derived from cases",
    }
    dump_json(manifest, OUTDIR / "p1d2_diagnostic_seed_manifest.json")
    print(f"Wrote {len(ALL_CORPUS)} sources, {len(ALL_CASES)} cases, {len(derived_judgments)} judgments.")
    print(f"Families: {dict(sorted(families.items()))}")
    print(f"Case modes: {dict(sorted(case_modes.items()))}")


if __name__ == "__main__":
    build()
