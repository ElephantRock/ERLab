# Calibration Method Rankings under Graded Covariate Shift: A Controlled Single-Run Study of Sigmoid and Isotonic Post-Hoc Calibration for One-vs-Rest Logistic Regression on the Iris and Wine Quality Datasets

## Abstract

Post-hoc calibration is widely assumed to improve the probabilistic quality of classifiers, but whether such improvements survive covariate shift—and whether method rankings remain stable as shift severity grows—remains empirically underexamined in tightly controlled settings. This paper reports a controlled, single-run study of calibration-method rank stability under graded covariate shift on two tabular classification datasets, iris and wine_quality. A frozen backbone of independent one-vs-rest binary logistic regression classifiers, combined by softmax normalization of per-class logits, is evaluated uncalibrated and with two standard post-hoc calibration layers—Platt-style sigmoid scaling and isotonic regression (pool-adjacent-violators)—fitted only on the designated positive class, against a majority-class baseline, at four fixed shift severities (0.0, 0.25, 0.5, 0.75). Outcomes are top-1 accuracy, a ten-bin positive-class expected calibration error (ECE), and a ten-threshold area under the risk–coverage curve (AURC). Isotonic calibration attains the best ECE and AURC on iris at severity 0.0 (0.05 [RESULT-3]; 0.005185 [RESULT-2]), whereas sigmoid attains the best ECE on wine_quality (0.019094 [RESULT-43]); on wine_quality the uncalibrated model attains the best AURC (0.024025 [RESULT-45]) while sigmoid attains the worst (0.415709 [RESULT-42]); on iris, sigmoid calibration inflates AURC from 0.014729 [RESULT-8] to 0.188889 [RESULT-5]; and isotonic calibration depresses accuracy below the majority-class baseline on wine_quality at severities 0.0 and 0.25 (0.515625 [RESULT-38]; 0.530035 [RESULT-47], versus 0.534375 [RESULT-74]). Rankings were invariant to severity in this run, yet reversed across datasets and metrics. These findings caution that severity sweeps alone cannot certify a calibration method choice; metric-specific and dataset-specific validation is required.

## 1 Introduction

Confidence estimates are integral to the safe operation of deployed classifiers: they gate deferral, triage, and human oversight. A long line of work treats calibration error, proper scoring rules, and accuracy as interchangeable proxies for "trustworthy probabilities," yet exact finite counterexamples demonstrate that an improvement in one need not entail improvement in the others, and that a low calibration error or a low cross-entropy cannot be read as evidence of reliability in any broader sense [SOURCE-2]. Complementarily, accuracy itself is a noisy estimate whose uncertainty deserves quantification rather than treatment as ground truth [SOURCE-30], and operational forecasting studies show that aggregate error criteria can mis-rank systems on the reliability that matters for targeted alerting, because aggregate error conceals peak risk [SOURCE-5]. Together these results imply that the *ranking* of confidence-estimation methods may be an artifact of the metric and data used to evaluate them, rather than a stable property of the methods themselves.

Covariate shift sharpens this concern. When the marginal distribution of features changes between training and deployment, calibration layers fitted on held-out source data are applied out of domain, and it is natural to expect their benefit to erode with shift severity. What remains scarce is a tightly controlled empirical answer to a simpler question: *as covariate-shift severity increases, do calibration-method rankings stay stable, or do rank reversals occur—and if so, along which axes?*

This study answers that question with a deliberately minimal, fully frozen experimental contract (capability `tabular_calibration_selective_v1`). The backbone is a set of independent one-vs-rest binary logistic regression classifiers trained from first principles and combined by softmax normalization; the only manipulated factor above this backbone is the post-hoc calibration layer applied to the designated positive class (none, Platt-style sigmoid, or isotonic), evaluated against a majority-class baseline. Two tabular datasets were executed—iris and wine_quality, the latter with its binary target derived from quality (good = quality $\geq$ 6 versus bad = quality $< 6$)—at four fixed covariate-shift severities (0.0, 0.25, 0.5, 0.75), with three metrics recorded per configuration: top-1 accuracy, a ten-bin positive-class ECE, and a ten-threshold AURC for selective classification.

The contributions are deliberately bounded and are stated as properties of the executed analysis rather than as claims about calibration methods in general; every component used here—Platt-style sigmoid scaling, isotonic regression via pool-adjacent-violators, and one-vs-rest logistic regression—is a standard, decades-old technique, and the datasets are small and well-worn. First, the study provides a severity-sweep protocol in which model, loss, calibration fitting, and metric implementations are held constant, isolating the calibration layer as the only comparison axis. Second, it reports a complete rank-stability audit: within every dataset–metric pair, the observed ordering of the three conditions was identical at all four severities in this run; the reversals that occurred were across datasets and across metrics, not across severities. Third, it documents large metric-specific inversions: on iris at severity 0.0, isotonic gave the best ECE (0.05 [RESULT-3]) and sigmoid the worst (0.196669 [RESULT-6]), whereas on wine_quality sigmoid gave the best ECE (0.019094 [RESULT-43]) and the uncalibrated model the worst (0.448188 [RESULT-46]); sigmoid inflated iris AURC from 0.014729 [RESULT-8] uncalibrated to 0.188889 [RESULT-5], and isotonic calibration depressed accuracy below the majority-class baseline on wine_quality at low severity (0.515625 [RESULT-38] versus 0.534375 [RESULT-74]). Fourth, it derives practical guidance from these observed values: severity sweeps alone are insufficient for method selection; validation must be repeated on the deployment dataset under the deployment metric. Because each configuration was executed once, all findings are descriptive point estimates without significance testing, as elaborated in Sections 4 and 7.

## 2 Related Work

**Decoupling of accuracy, proper scores, and calibration.** The assumption that accuracy, strictly proper scoring rules, and calibration error move together underlies much applied reporting, but minimal counterexamples show the three families can be separated exactly even in finite samples, undermining the inference from low calibration error to trustworthy probabilities [SOURCE-2]. Complementarily, confidence-interval calibration for classification accuracy emphasizes that accuracy itself is a noisy estimate whose uncertainty might be quantified rather than treated as ground truth [SOURCE-30]. Studies of operational forecasting show that average-error criteria can fail to rank systems by the reliability that matters for targeted alerting, since aggregate error conceals peak risk [SOURCE-5]. The present study instantiates exactly this decoupling under shift: accuracy, positive-class ECE, and selective AURC produced mutually inconsistent orderings of the same three calibration conditions.

**Distribution shift and calibration.** Shift correction techniques such as importance weighting [SOURCE-3] are standard background for the shifted-evaluation regime studied here; they motivated the severity-sweep design but were not executed in this experiment. This study deliberately does not correct shift; it measures how uncorrected post-hoc calibration layers rank under shift, which is the regime most deployments occupy. Shift-aware recalibration and weighting baselines are treated strictly as future work in Section 8.

**Selective prediction and coverage.** Risk–coverage analysis before and after calibration is an established lens for whether recalibration improves selective utility [SOURCE-7], and recalibration within conformal prediction frameworks has been used to obtain class-wise coverage [SOURCE-18]. The AURC estimator used here differs from both lines of work in a way that matters for comparability: per the frozen contract, it is computed from ten fixed confidence thresholds and trapezoid integration of the resulting (coverage, risk) points, not from a full sample ordering.

**Estimator specifics.** The ECE variant used here also differs from the common top-class-confidence definition: it is computed with ten equal-width bins on the positive-class probability, reflecting the single-class focus of the calibration layer under study. No shift correction of the covariates or probabilities beyond the fitted positive-class map is performed; the covariates are taken as given, and only the output probabilities are transformed.

Relative to all of the above, the contribution of this study is not a new calibrator but a bounded, controlled rank-stability analysis: a fixed logistic backbone, a frozen metric suite, matched severities, and two executed datasets, reported as single-run point estimates.

## 3 Methodology

### 3.1 Problem definition

Let $\mathcal{D} = \{(x_i, y_i)\}_{i=1}^{n}$ be a tabular classification dataset with labels $y \in \{1,\dots,K\}$. Each binary one-vs-rest model is trained with an L2 penalty of $0.001$, and optimization uses full-batch gradient descent with learning rate $0.05$ for $1000$ epochs. Class probabilities are obtained by softmax normalization of the per-class logits,

$$
p_k(x) \;=\; \frac{\exp(z_k(x))}{\sum_{j=1}^{K}\exp(z_j(x))}.
$$

The designated positive class is $\kappa$, the last class in sorted label order. Post-hoc calibration is fitted only for $\kappa$. Let $\hat{q}(x)$ denote the calibrated positive-class probability produced by the fitted map. At application time the remaining probability mass is redistributed across the other classes proportionally to their uncalibrated probabilities:

$$
\hat{p}'_\kappa(x) = \hat{q}(x), \qquad
\hat{p}'_k(x) = \frac{\big(1-\hat{q}(x)\big)\, p_k(x)}{1 - p_\kappa(x)} \quad (k \neq \kappa).
$$

Selective risk and coverage are evaluated at ten fixed confidence thresholds $\tau_t = 0.1t$, $t=0,\dots,9$, with confidence $c(x)=\max_k \hat{p}'_k(x)$ and risk defined as incorrectness of the predicted class among accepted samples; AURC is the trapezoidal integral of the resulting ten (coverage, risk) points:

$$
\widehat{\mathrm{AURC}} \;=\; \sum_{t=0}^{8}\big(c(\tau_{t+1}) - c(\tau_t)\big)\,\frac{r(\tau_{t+1}) + r(\tau_t)}{2}.
$$

### 3.2 Executed protocol (frozen method contract)

The following executed protocol is reproduced verbatim from the frozen method contract of capability `tabular_calibration_selective_v1`:

- The base model is a set of independent one-vs-rest binary logistic regression classifiers. Each binary model is trained with full-batch gradient descent (learning rate 0.05, 1000 epochs, L2 penalty 0.001) implemented from first principles; no external machine-learning library is used. Per-class scores are combined into class probabilities by softmax normalization of the per-class logits.
- Post-hoc calibration is fitted only for the designated positive class (the last class in sorted label order). Sigmoid (Platt-style) parameters are selected by grid search over a fixed candidate set of (a, b) values minimizing binary cross-entropy on the calibration split; an isotonic map (pool-adjacent-violators) is fitted on the positive-class probability against the indicator y = positive class. At application time only the positive-class probability is calibrated; the remaining probability mass is redistributed across the other classes proportionally to their uncalibrated probabilities.
- Expected calibration error (ECE) is computed with 10 equal-width bins on the positive-class probability: within each bin it compares the mean positive-class probability against the empirical frequency of the positive class (y = positive class), and averages the absolute gaps weighted by bin size. It is not the standard top-class-confidence ECE.
- The area under the risk-coverage curve (AURC) is estimated by evaluating selective risk and coverage at ten fixed confidence thresholds (0.0 to 0.9 in steps of 0.1), using the maximum class probability as the confidence score and correctness of the predicted class as the risk basis, then trapezoid-integrating those ten (coverage, risk) points. It is not an integral over the full sample ordering.

### 3.3 Covariate-shift conditions

Evaluation is performed at four fixed covariate-shift severities, $s \in \{0.0,\,0.25,\,0.5,\,0.75\}$, where $s=0.0$ denotes the unshifted reference condition. The severity-to-perturbation mapping is fixed by the capability contract and held constant across both executed datasets, so that severity labels are comparable between iris and wine_quality within this study. Three calibration conditions (uncalibrated, sigmoid, isotonic) are evaluated at each severity on an identical backbone, alongside a majority-class baseline.

## 4 Experimental Design

**Datasets.** Two tabular classification datasets were executed as parts of a single empirical study: iris, the classical three-class tabular flower-measurement dataset, and wine_quality, a tabular dataset of physicochemical measurements whose target is the binary label derived from quality (good = quality $\geq$ 6, bad = quality $<$ 6). The executed split protocol is stratified by target, first 80% train / last 20% test, with a fixed shuffle and seed 42. Iris is class-balanced, with majority-class baseline accuracy 0.333333 [RESULT-37], whereas wine_quality is imbalanced toward one class, with baseline accuracy 0.534375 [RESULT-74]. No other datasets were executed, and no pooled statistics across datasets are reported.

**Conditions and factors.** The design crosses one between-condition factor—calibration layer (uncalibrated, sigmoid, isotonic)—with one severity factor $s \in \{0.0, 0.25, 0.5, 0.75\}$, fully crossed within each dataset (12 model–severity configurations per dataset). The majority-class baseline provides a lower anchor for accuracy. Because the backbone, optimization procedure, and calibration-split usage are identical across conditions, any metric difference between conditions at a given severity is attributable to the calibration layer and its interaction with the shifted evaluation partition.

**Metrics.** Three complementary metrics were recorded per configuration in `metrics.json` (experiment_result_id 1 for iris; experiment_result_id 2 for wine_quality): (i) top-1 accuracy (higher is better); (ii) positive-class ECE with ten equal-width bins (lower is better), which is deliberately *not* the standard top-class-confidence ECE; and (iii) AURC estimated from ten fixed confidence thresholds (lower is better), which is deliberately *not* an integral over the full sample ordering. These estimator specifics are part of the frozen contract and must be kept in mind when comparing against external numbers.

**Ablation structure.** The study embeds three ablations. First, a *calibration-layer ablation*: uncalibrated versus sigmoid versus isotonic on an identical backbone, isolating the effect of the post-hoc map. Second, a *severity dose–response ablation*: each metric as a function of $s$, testing whether degradation is monotone and whether orderings change. Third, a *baseline-anchored ablation*: each condition's accuracy against the majority-class baseline at each severity, testing whether any calibration layer is harmful enough to forfeit the model's advantage over the trivial predictor.

**Protocol notes.** Each configuration was executed once per dataset; no seed replications, confidence intervals, or significance tests are available in the recorded results. This is a material constraint on interpretation: the test partitions are small (tens of samples for iris at shifted severities, hundreds for wine_quality), and a ten-bin ECE on partitions of this size is a high-variance estimator whose value can move substantially under resampling. Large observed gaps are reported as observed; small ones (e.g., between adjacent wine_quality accuracies) should not be over-interpreted. No shift correction of any kind (e.g., importance weighting [SOURCE-3]) was applied; such methods are background motivation and future work, not executed components.

## 5 Expected Results (Hypotheses Stated Before Inspection of Outcomes)

The following hypotheses were formulated prior to inspecting the recorded outcomes and are labeled as such; none is an observed result. **H1 (monotone degradation):** all three conditions were expected to degrade monotonically in accuracy, ECE, and AURC as severity $s$ increases, on both datasets. **H2 (isotonic dominance):** because the pool-adjacent-violators map is more flexible than a two-parameter sigmoid, isotonic calibration was expected to attain lower ECE than sigmoid on both datasets, with the gap widening at higher severity as the sigmoid's parametric form misfits the shifted score distribution. **H3 (calibration–selectivity alignment):** post-hoc calibration was expected to leave AURC unchanged or improve it, on the reasoning that better-calibrated confidences order samples more faithfully for selective acceptance. **H4 (rank stability):** rankings were expected to be stable across severity within each dataset–metric pair, so that any severity sweep would suffice to certify a method choice. **H5 (baseline margin):** no calibration layer was expected to depress accuracy below the majority-class baseline. As Section 6 reports, H1, H2, H3, and H5 were violated in the executed runs in dataset-specific ways, while H4 held in the observed point estimates; the observed values, not these hypotheses, are the authoritative record.

## 6 Results

### 6.1 Iris: observed results

Table 1 reports all iris configurations (experiment_result_id 1). All values are single-run point estimates.

**Table 1.** Iris results by severity and calibration condition. ECE and AURC are lower-better.

| Severity | Condition | Accuracy | ECE$_+$ | AURC |
|---|---|---|---|---|
| 0.00 | isotonic | 0.933333 [RESULT-1] | 0.05 [RESULT-3] | 0.005185 [RESULT-2] |
| 0.00 | sigmoid | 0.933333 [RESULT-4] | 0.196669 [RESULT-6] | 0.188889 [RESULT-5] |
| 0.00 | uncalibrated | 0.933333 [RESULT-7] | 0.112177 [RESULT-9] | 0.014729 [RESULT-8] |
| 0.25 | isotonic | 0.923077 [RESULT-10] | 0.057692 [RESULT-12] | 0.006946 [RESULT-11] |
| 0.25 | sigmoid | 0.923077 [RESULT-13] | 0.202486 [RESULT-15] | 0.161243 [RESULT-14] |
| 0.25 | uncalibrated | 0.923077 [RESULT-16] | 0.116041 [RESULT-18] | 0.017893 [RESULT-17] |
| 0.50 | isotonic | 0.909091 [RESULT-19] | 0.068182 [RESULT-21] | 0.009787 [RESULT-20] |
| 0.50 | sigmoid | 0.909091 [RESULT-22] | 0.215127 [RESULT-24] | 0.123967 [RESULT-23] |
| 0.50 | uncalibrated | 0.909091 [RESULT-25] | 0.130412 [RESULT-27] | 0.024363 [RESULT-26] |
| 0.75 | isotonic | 0.909091 [RESULT-28] | 0.068182 [RESULT-30] | 0.009787 [RESULT-29] |
| 0.75 | sigmoid | 0.909091 [RESULT-31] | 0.215127 [RESULT-33] | 0.123967 [RESULT-32] |
| 0.75 | uncalibrated | 0.909091 [RESULT-34] | 0.130412 [RESULT-36] | 0.024363 [RESULT-35] |

Majority-class baseline accuracy: 0.333333 [RESULT-37]. Three observations follow. First, accuracy is identical across the three conditions at every severity (0.933333 [RESULT-1] for isotonic, 0.933333 [RESULT-4] for sigmoid, and 0.933333 [RESULT-7] for uncalibrated at $s=0.0$), so the calibration layers left the argmax predictions unchanged on iris. Second, the two calibration layers move ECE in opposite directions: isotonic improves calibration relative to the uncalibrated model (0.05 [RESULT-3] versus 0.112177 [RESULT-9] at $s=0.0$), with isotonic ECE rising from 0.05 [RESULT-3] to 0.057692 [RESULT-12] to 0.068182 [RESULT-21] as severity increases, while sigmoid degrades calibration relative to the uncalibrated model (0.196669 [RESULT-6] versus 0.112177 [RESULT-9] at $s=0.0$, roughly 1.75 times worse). Third, the same opposition appears, amplified, in AURC: sigmoid inflates AURC from 0.014729 [RESULT-8] uncalibrated to 0.188889 [RESULT-5] at $s=0.0$ (a more than twelvefold increase), whereas isotonic lowers it to 0.005185 [RESULT-2]. Finally, all iris metrics are exactly equal at $s=0.5$ and $s=0.75$ (accuracy 0.909091 [RESULT-19] equals 0.909091 [RESULT-28]; ECE 0.068182 [RESULT-21] equals 0.068182 [RESULT-30]; AURC 0.024363 [RESULT-26] equals 0.024363 [RESULT-35]), indicating that the two highest severity levels induced indistinguishable evaluation conditions on iris in this run—a severity saturation plateau.

### 6.2 Wine quality: observed results

Table 2 reports all wine_quality configurations (experiment_result_id 2).

**Table 2.** Wine quality results by severity and calibration condition. ECE and AURC are lower-better.

| Severity | Condition | Accuracy | ECE$_+$ | AURC |
|---|---|---|---|---|
| 0.00 | isotonic | 0.515625 [RESULT-38] | 0.354454 [RESULT-40] | 0.160671 [RESULT-39] |
| 0.00 | sigmoid | 0.615625 [RESULT-41] | 0.019094 [RESULT-43] | 0.415709 [RESULT-42] |
| 0.00 | uncalibrated | 0.54375 [RESULT-44] | 0.448188 [RESULT-46] | 0.024025 [RESULT-45] |
| 0.25 | isotonic | 0.530035 [RESULT-47] | 0.334098 [RESULT-49] | 0.158804 [RESULT-48] |
| 0.25 | sigmoid | 0.621908 [RESULT-50] | 0.005532 [RESULT-52] | 0.396727 [RESULT-51] |
| 0.25 | uncalibrated | 0.54417 [RESULT-53] | 0.449834 [RESULT-55] | 0.019301 [RESULT-54] |
| 0.50 | isotonic | 0.54878 [RESULT-56] | 0.325042 [RESULT-58] | 0.15147 [RESULT-57] |
| 0.50 | sigmoid | 0.638211 [RESULT-59] | 0.018625 [RESULT-61] | 0.367245 [RESULT-60] |
| 0.50 | uncalibrated | 0.565041 [RESULT-62] | 0.426696 [RESULT-64] | 0.017567 [RESULT-63] |
| 0.75 | isotonic | 0.566502 [RESULT-65] | 0.31533 [RESULT-67] | 0.135889 [RESULT-66] |
| 0.75 | sigmoid | 0.674877 [RESULT-68] | 0.055979 [RESULT-70] | 0.299455 [RESULT-69] |
| 0.75 | uncalibrated | 0.600985 [RESULT-71] | 0.38969 [RESULT-73] | 0.019442 [RESULT-72] |

Majority-class baseline accuracy: 0.534375 [RESULT-74]. Four observations follow. First, sigmoid attains the highest accuracy at every severity, and at $s=0.0$ the ordering is sigmoid $>$ uncalibrated $>$ isotonic (0.615625 [RESULT-41] $>$ 0.54375 [RESULT-44] $>$ 0.515625 [RESULT-38]). Second, isotonic calibration fell below the majority-class baseline at low severity (0.515625 [RESULT-38] at $s=0.0$ and 0.530035 [RESULT-47] at $s=0.25$, versus baseline 0.534375 [RESULT-74]); it exceeded the baseline only at $s=0.5$ (0.54878 [RESULT-56]) and $s=0.75$ (0.566502 [RESULT-65]). Third, sigmoid achieves a large ECE advantage over the uncalibrated model at $s=0.0$ (0.019094 [RESULT-43] versus 0.448188 [RESULT-46]). Fourth, the AURC ordering is fully inverted relative to ECE: the uncalibrated model has the best AURC (0.024025 [RESULT-45], stable across severities at 0.019301 [RESULT-54], 0.017567 [RESULT-63], and 0.019442 [RESULT-72]) while the best-calibrated model (sigmoid) has the worst (0.415709 [RESULT-42], more than seventeen times the uncalibrated value at $s=0.0$).

### 6.3 Rank stability across severity, and reversals across datasets and metrics

**Table 3.** Method orderings (best to worst), identical at all four severities within each cell.

| Metric | Iris | Wine quality |
|---|---|---|
| Accuracy | three-way tie | sigmoid $>$ uncalibrated $>$ isotonic |
| ECE$_+$ (lower better) | isotonic $<$ uncalibrated $<$ sigmoid | sigmoid $<$ isotonic $<$ uncalibrated |
| AURC (lower better) | isotonic $<$ uncalibrated $<$ sigmoid | uncalibrated $<$ isotonic $<$ sigmoid |

The central finding is structural: **within every dataset–metric pair, the method ranking was invariant to severity in this run.** No severity-induced rank reversal occurred anywhere in the study. The reversals that did occur are along the other two axes. Across datasets, the isotonic–sigmoid ordering on ECE flips (iris: 0.05 [RESULT-3] versus 0.196669 [RESULT-6]; wine_quality: 0.354454 [RESULT-40] versus 0.019094 [RESULT-43]), and the isotonic–uncalibrated ordering on AURC also flips (iris: 0.005185 [RESULT-2] versus 0.014729 [RESULT-8]; wine_quality: 0.160671 [RESULT-39] versus 0.024025 [RESULT-45]). Across metrics within a single dataset and severity, the uncalibrated model on wine_quality is simultaneously the *worst* on ECE (0.448188 [RESULT-46]) and the *best* on AURC (0.024025 [RESULT-45]), while sigmoid is the best on ECE (0.019094 [RESULT-43]) and the worst on AURC (0.415709 [RESULT-42])—a within-dataset, within-severity full inversion between calibration quality and selective utility, directly echoing exact counterexamples in which calibration error, proper scores, and accuracy come apart [SOURCE-2] and warnings that aggregate criteria can mis-rank systems on deployment-relevant risk [SOURCE-5].

### 6.4 Severity dose–response

The dose–response behavior is dataset-dependent and partly counterintuitive. On iris, degradation is monotone but mild and saturates: all metrics at $s=0.5$ and $s=0.75$ are identical (e.g., isotonic ECE 0.068182 [RESULT-21] at $s=0.5$ equals 0.068182 [RESULT-30] at $s=0.75$). On wine_quality, accuracy *improves* with severity for all conditions—sigmoid from 0.615625 [RESULT-41] to 0.674877 [RESULT-68], uncalibrated from 0.54375 [RESULT-44] to 0.600985 [RESULT-71], isotonic from 0.515625 [RESULT-38] to 0.566502 [RESULT-65]—and ECE also trends downward for isotonic (0.354454 [RESULT-40] to 0.31533 [RESULT-67]) and uncalibrated (0.448188 [RESULT-46] to 0.38969 [RESULT-73]), while sigmoid ECE rises modestly at the highest severity (0.005532 [RESULT-52] to 0.055979 [RESULT-70]). A plausible reading, offered as interpretation rather than an observed mechanism, is that the severity parameterization changed the class composition or difficulty of the evaluation partition in a way that benefited the argmax decisions of all conditions; the observed values themselves are the authoritative record.

### 6.5 Answer to the research question

Are calibration-method rankings stable as covariate-shift severity increases? Within this single executed run: yes, in every observed dataset–metric pair—the ordering of the three conditions was identical at all four severities. Do rank reversals occur? Yes, but along the dataset and metric axes, not the severity axis: isotonic versus sigmoid on ECE, isotonic versus uncalibrated on AURC, and the full ECE–AURC inversion on wine_quality. The practical implication is that a severity sweep on a single dataset with a single metric—even a flawless, monotone one—provides no guarantee that the resulting method ranking transfers to another dataset or another evaluation criterion.

## 7 Discussion

**Limitations.** Several constraints bound the generality of these findings, and the most important is statistical. Only two small tabular datasets were executed, each in a single run with no seed replications, so no confidence intervals or significance tests can be attached to the reported values; the six-decimal precision of the recorded metrics should not be read as six-decimal reliability. A ten-bin ECE on test partitions of this size is a high-variance estimator, and the exact stability of the orderings across severity (Table 3), while striking, is a property of this run rather than a statistically established regularity. Differences as large as those in Tables 1–2 (e.g., sigmoid AURC 0.415709 [RESULT-42] versus 0.024025 [RESULT-45] uncalibrated on wine_quality) are unlikely to be noise, but small ones—such as between adjacent wine_quality accuracies—could be. The backbone is a linear one-vs-rest logistic model; deep models with different confidence geometries may exhibit different rank behavior. The ECE and AURC estimators are nonstandard variants fixed by the contract, limiting comparability with external benchmarks. The exact equality of all iris metrics at severities 0.5 and 0.75 indicates severity saturation in this run, reducing the effective number of distinct severity points on that dataset. Finally, the improvement of all conditions with severity on wine_quality shows that the severity parameter is not a validated proxy for task difficulty; construct validity of the shift severity is an open issue. The contribution is accordingly bounded to the executed controlled comparison itself, given that all components are standard techniques.

**Broader impact.** The results carry a deployment-relevant message: post-hoc calibration layers are not safe defaults. In this run, the layer that produced the best calibration error on wine_quality (sigmoid, ECE 0.019094 [RESULT-43]) simultaneously produced the worst selective risk on that dataset (0.415709 [RESULT-42]) and severe calibration and selective degradation on another (iris ECE 0.196669 [RESULT-6]; iris AURC 0.188889 [RESULT-5]).

**Ethical considerations.** Miscalibrated confidence can translate directly into harm wherever probabilities inform decisions about people (e.g., triage, screening, or resource allocation). This study used public tabular datasets with no personal identifiers. The main ethical risk is misinterpretation: the numbers reported here are single-run values specific to the frozen protocol described in Section 3 and should not be quoted as general properties of sigmoid or isotonic calibration. Practitioners should validate calibration layers on their own data, under their deployment metric, before trusting them.

## 8 Conclusion

This paper reported a controlled single-run empirical study of calibration-method rank stability under graded covariate shift, executed on the iris and wine_quality tabular datasets with a frozen method contract: one-vs-rest logistic regression with softmax-combined logits, compared uncalibrated, with positive-class sigmoid calibration, and with positive-class isotonic calibration, against a majority-class baseline, at severities 0.0, 0.25, 0.5, and 0.75, measured by accuracy, positive-class ECE, and a ten-threshold AURC. In the executed runs of this method, the method ordering was identical across all four severities within every dataset–metric pair, while reversing sharply across datasets and across metrics: isotonic calibration dominated both ECE (0.05 [RESULT-3]) and AURC (0.005185 [RESULT-2]) on iris at $s=0.0$, whereas on wine_quality sigmoid dominated ECE (0.019094 [RESULT-43]), the uncalibrated model dominated AURC (0.024025 [RESULT-45]), and isotonic calibration fell below the majority-class baseline in accuracy at low severity (0.515625 [RESULT-38] and 0.530035 [RESULT-47] versus 0.534375 [RESULT-74]). The conclusion for practice is that severity sweeps alone cannot justify a calibration method choice; validation must be repeated on the deployment dataset under the deployment metric. Future work should extend the executed protocol with additional datasets and seeds, confidence intervals for all three estimators, top-class ECE and full-ordering AURC variants for external comparability, and shift-aware calibration baselines including importance weighting [SOURCE-3] and conformal coverage methods [SOURCE-18], all of which remain unexecuted relative to the present study.