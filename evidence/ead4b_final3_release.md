# Post-Hoc Probability Calibration and Selective Classification under Covariate Shift: A Controlled Empirical Audit of Logistic Regression with Sigmoid and Isotonic Calibration on the Iris and Wine Quality Tabular Benchmarks

## Abstract

Reliable deployment of tabular classifiers requires that predicted probabilities remain trustworthy when the test distribution drifts from the training distribution. This paper reports a controlled empirical audit, executed as the capability `tabular_calibration_selective_v1`, of post-hoc probability calibration applied to a logistic regression base model on two tabular benchmarks: iris (three-class) and wine_quality (binarized target, good = quality $\geq$ 6). The executed method compares an uncalibrated logistic control against post-hoc sigmoid (Platt) and isotonic calibration, both fit once on held-out source-domain data and held fixed, against a majority-class baseline, across four fixed covariate-shift severity levels $\rho \in \{0.0, 0.25, 0.5, 0.75\}$; all 74 recorded metrics are reported verbatim. The observed record reveals a pronounced decoupling between calibration error and selective risk. On wine_quality, sigmoid calibration yields the best ECE at every severity, e.g., 0.005532 [RESULT-52], yet the worst AURC, e.g., 0.396727 [RESULT-51], whereas the uncalibrated control dominates AURC, e.g., 0.019301 [RESULT-54]. On iris, isotonic calibration dominates both axes, with AURC 0.005185 [RESULT-2] and ECE 0.05 [RESULT-3] at $\rho=0.0$, while sigmoid calibration is harmful on both. Severity effects are inconsistent across datasets: accuracy degrades monotonically on iris, from 0.933333 [RESULT-1] to 0.909091 [RESULT-28], but improves with severity on wine_quality, from 0.615625 [RESULT-41] to 0.674877 [RESULT-68] under sigmoid calibration. These findings caution against assuming that post-hoc calibration improves rejection-based reliability under covariate shift, and motivate auditing calibration error and selective risk separately when logistic tabular classifiers are deployed on drifting data.

## 1. Introduction

Supervised classifiers are typically trained and validated on data drawn from the same distribution that generates the test set, yet this assumption routinely fails in deployment. A common prescription for unreliable confidences is post-hoc probability calibration: a lightweight mapping, most famously Platt scaling (a sigmoid) or isotonic regression, is fit on held-out data and applied to the model's outputs. Calibration is usually justified and measured by calibration error metrics such as expected calibration error (ECE). Selective classification, however, depends not only on whether probabilities are calibrated in expectation but on whether the ranking of instances by confidence aligns with their correctness—a distinct property captured by risk–coverage analysis. Although this distinction is appreciated in the selective-prediction literature [SOURCE-13], [SOURCE-23], deployment practice frequently treats "calibrated" and "reliable for rejection" as interchangeable, and empirical records that document the two axes jointly under controlled shift are scarce.

This paper presents a controlled empirical audit, executed under the capability `tabular_calibration_selective_v1`, that isolates the interaction of three factors: (i) post-hoc calibration strategy (none, sigmoid, isotonic) applied to a logistic regression base model; (ii) covariate-shift severity, fixed at four levels $\rho \in \{0.0, 0.25, 0.5, 0.75\}$; and (iii) dataset identity, instantiated by two tabular benchmarks, iris and wine_quality. The executed task is classification: iris is a three-class problem, while wine_quality is executed with a binarized target (good = quality $\geq$ 6, bad = quality $<$ 6). All variants are compared against an uncalibrated logistic control and a majority-class baseline. The study records accuracy, ECE, and the area under the risk–coverage curve (AURC) for every combination, yielding 72 model-condition metrics plus 2 baseline accuracies, all of which are reported verbatim in Section 6.

The contributions of this work are deliberately bounded to the executed analysis, and their confirmatory character is stated explicitly. First, the paper supplies a complete, fully documented, single-execution empirical record (one fixed seed) of how the two canonical post-hoc calibrators behave on a logistic tabular classifier at fixed shift severities, against a majority-class reference point; no new calibration method is proposed. Second, the record demonstrates concretely, in exact per-cell values, that calibration error and selective risk can decouple sharply and that the direction of the decoupling is dataset-dependent; the decoupling phenomenon itself is consistent with prior selective-prediction findings [SOURCE-13], [SOURCE-2], [SOURCE-23], so this contribution is confirmatory and audit-oriented rather than novel in kind. Third, the record shows that severity effects are inconsistent across datasets, including an anomalous monotone accuracy improvement under shift on wine_quality that is flagged here as an unexplained validity threat requiring follow-up, not as a generalizable insight. Fourth, the paper distills the record into a concrete deployment-audit recommendation: measure ECE and AURC separately and always include a majority-class reference. Stronger comparators—temperature scaling, importance-weighted recalibration under shift, and additional base models—were not executed and are labeled throughout as future work.

## 2. Related Work

**Robust classification under covariate shift.** Covariate shift has been studied extensively from the model-adaptation perspective: robust classification under shift has been treated for active learning [SOURCE-6], for tree-structured models [SOURCE-7], and in applied domains including sleep staging [SOURCE-8], texture recognition [SOURCE-12], fault classification [SOURCE-9], and social media text under negative shift [SOURCE-5]. Label-free performance estimation under covariate shift [SOURCE-18] addresses the complementary problem of predicting accuracy when target labels are unavailable. The present audit differs from this literature in that it does not attempt to adapt the model to the shift; instead, it fixes a standard logistic classifier and quantifies what happens to calibrated uncertainty and selective risk when shift magnitude is varied under a controlled severity knob. In this respect it complements [SOURCE-18] by supplying ground-truth reference measurements at known severities.

**Calibration, uncertainty, and selective prediction.** Probability calibration via Platt scaling and isotonic regression is the canonical post-hoc remedy for over- or under-confident predictors. Reliability-aware selective prediction combines confidence assessment with abstention, and has been examined for deep language models [SOURCE-13], for conformal ensembling under distribution shift [SOURCE-2], and for cost-aware deferral in clinical triage [SOURCE-23]. On the tabular side, conformal prediction sets with importance weighting have been developed for regression under covariate shift with finite-sample guarantees [SOURCE-1], [SOURCE-3]. The audit reported here occupies a deliberately simpler position in this landscape: rather than proposing new conformal or Bayesian machinery, it measures whether the two most widely used post-hoc calibrators, applied once and left fixed, improve or degrade the risk–coverage behavior of a logistic tabular classifier as shift severity grows. Importance-weighted recalibration in the spirit of [SOURCE-1], [SOURCE-3] is a natural adaptive baseline for this setting, but it was not executed and is treated strictly as future work.

**Linear models and tabular practice.** Interpretable linear models remain central in applied tabular domains, and imbalanced clinical tabular data has been shown to expose robustness failures of standard pipelines [SOURCE-28]. The two datasets executed here instantiate two contrasting tabular regimes that follow directly from the observed baselines: a near-balanced three-class problem on iris with majority-class accuracy 0.333333 [RESULT-37], and a problem with pronounced majority-class dominance on wine_quality with majority-class accuracy 0.534375 [RESULT-74]. This contrast proves consequential for every finding in Section 6.

## 3. Methodology

### 3.1 Problem setting

Let $(x, y) \sim P$ with features $x \in \mathbb{R}^d$ and label $y \in \{1, \dots, K\}$. The model is trained on a source sample from $P_S(x, y) = p_S(y \mid x)\, p_S(x)$. Under covariate shift, evaluation instances are drawn from $p_T(x, y) = p_S(y \mid x)\, p_T(x)$ with $p_T(x) \neq p_S(x)$. The capability harness `tabular_calibration_selective_v1` realizes this via a severity parameter $\rho$ that scales the magnitude of the perturbation applied in constructing the shifted evaluation conditions, swept over the fixed grid $\rho \in \{0.0, 0.25, 0.5, 0.75\}$; $\rho = 0.0$ corresponds to the unshifted condition. The perturbation operator itself is fixed by the harness and held identical across datasets; its internal form is not exposed in the persisted record, so $\rho$ is treated throughout as a controlled ordinal severity knob rather than an interpretable distributional parameter (see Section 7). No importance weighting, shift-adaptive recalibration, or target-domain training is applied: the base model and any calibration mapping are fixed before evaluation and held identical across all severity levels. This design deliberately isolates the effect of shift on already-deployed post-hoc calibration.

### 3.2 Data protocol and base model

Each dataset is split by stratifying on the target, shuffling with a fixed seed of 42, and assigning the first 80% of records to training and the last 20% to test. The wine_quality target is binarized as good = quality $\geq$ 6, bad = quality $<$ 6; iris retains its three original classes. Post-hoc calibration maps are fit on held-out source-domain data disjoint from the training fit, reserved by the harness; the exact calibration sub-split size is not exposed in the persisted metrics record and is acknowledged as a documentation gap in Section 7. The entire study is a single execution per condition under the fixed seed—no repeated trials were run—so all values in Section 6 are descriptive of this one executed run.

The base model is a softmax logistic regression producing class probabilities

$$
\hat p_k(x) \;=\; \frac{\exp\!\big(w_k^\top x + b_k\big)}{\sum_{j=1}^{K} \exp\!\big(w_j^\top x + b_j\big)}, \qquad k = 1, \dots, K,
$$

fit by minimizing the negative log-likelihood (cross-entropy) on the training split,

$$
\min_{\{w_k, b_k\}} \; -\sum_{i=1}^{n} \sum_{k=1}^{K} \mathbf{1}[y_i = k] \, \log \hat p_k(x_i).
$$

The solver and regularization strength were the implementation library's defaults; they were fixed, not swept, and are not itemized in the persisted audit trail, which is recorded as a limitation in Section 7.

### 3.3 Post-hoc calibrators

Given the held-out calibration set $\{(x_j, y_j)\}_{j=1}^{m}$ disjoint from the training data, each calibrator learns a per-class mapping from the model's probability output $z = \hat p_k(x)$ to a recalibrated probability. **Sigmoid (Platt) calibration** fits, per class $k$, a logistic reparameterization

$$
\hat q_k(x) \;=\; \sigma\!\big(a_k\, \hat p_k(x) + b_k\big), \qquad \sigma(t) = \frac{1}{1 + e^{-t}},
$$

with parameters obtained by regularized maximum likelihood on the calibration set,

$$
(a_k^\star, b_k^\star) \;=\; \arg\min_{a, b} \; -\sum_{j=1}^{m} \Big[ t_{jk} \log \sigma\!\big(a z_{jk} + b\big) + \big(1 - t_{jk}\big) \log\!\big(1 - \sigma(a z_{jk} + b)\big) \Big],
$$

where $t_{jk} = \mathbf{1}[y_j = k]$ is the one-vs-rest indicator target for class $k$. **Isotonic calibration** instead fits a non-decreasing piecewise-constant function $g_k$ per class,

$$
g_k^\star \;=\; \arg\min_{g \in \mathcal{G}} \; \sum_{j=1}^{m} \big( g(z_{jk}) - t_{jk} \big)^2,
$$

where $\mathcal{G}$ is the class of non-decreasing step functions, and sets $\hat q_k(x) = g_k^\star(\hat p_k(x))$.

For both calibrators the per-class outputs are renormalized, $\tilde q_k(x) = \hat q_k(x) / \sum_j \hat q_j(x)$. Note that this renormalization, applied after a per-class monotone map, need not preserve the argmax ordering of the original probabilities; this is the formal mechanism by which calibration can alter point predictions, and it is observed empirically on wine_quality in Section 6.2. The point prediction is $\hat y(x) = \arg\max_k \tilde q_k(x)$, and the prediction confidence used for selective decisions is $c(x) = \max_k \tilde q_k(x)$.

### 3.4 Selective classification and metrics

A selective classifier accepts $x$ when $c(x) \geq \tau$ and otherwise abstains. For an evaluation set of size $N$, the empirical selective risk and coverage at threshold $\tau$ are

$$
\hat R(\tau) \;=\; \frac{\sum_{i=1}^{N} \mathbf{1}[c(x_i) \geq \tau]\; \mathbf{1}[\hat y(x_i) \neq y_i]}{\sum_{i=1}^{N} \mathbf{1}[c(x_i) \geq \tau]},
\qquad
\hat\phi(\tau) \;=\; \frac{1}{N} \sum_{i=1}^{N} \mathbf{1}[c(x_i) \geq \tau].
$$

Sorting instances by decreasing confidence $c_{\pi_1} \geq c_{\pi_2} \geq \dots \geq c_{\pi_N}$, the risk–coverage curve traces $\hat R$ against $\hat\phi$, and the area under the risk–coverage curve is

$$
\mathrm{AURC} \;=\; \frac{1}{N} \sum_{r=1}^{N} \hat R\!\left( r / N \right),
$$

the mean selective risk when the rejection budget is swept from full coverage to maximal abstention; lower AURC indicates that confidence better ranks incorrect predictions for rejection. **Expected calibration error** is computed by partitioning evaluation instances into $B$ equal-width bins by confidence,

$$
\mathrm{ECE} \;=\; \sum_{b=1}^{B} \frac{n_b}{N} \big| \mathrm{acc}(b) - \mathrm{conf}(b) \big|,
$$

where $\mathrm{acc}(b)$ and $\mathrm{conf}(b)$ are the binned accuracy and mean confidence; lower is better. The bin count $B$ is fixed by the harness. **Accuracy** is the unselective 0–1 accuracy of $\hat y$. Each metric is recorded for every (dataset, severity, variant) cell, together with a majority-class baseline accuracy per dataset.

## 4. Experimental Design

**Datasets.** Two tabular datasets were executed: iris and wine_quality. The two regimes differ sharply in class structure, as confirmed by the observed baselines: on iris the majority-class baseline accuracy is 0.333333 [RESULT-37], consistent with three approximately balanced classes, whereas on wine_quality the majority-class baseline accuracy is 0.534375 [RESULT-74], indicating strong majority-class dominance in the evaluation splits. Both datasets belong to the same executed study and are analyzed jointly but never pooled; no aggregate statistics are constructed across datasets.

**Factors and grid.** The design is a full factorial crossing of {variant: uncalibrated, sigmoid, isotonic} × {severity: 0.0, 0.25, 0.5, 0.75} × {dataset: iris, wine_quality}, yielding 24 measured cells with three metrics each, plus one majority-class baseline accuracy per dataset. The severity grid is fixed and identical across datasets so that cross-dataset comparisons of direction are meaningful even though absolute values are dataset-specific.

**Baselines and comparators.** Two references are executed. First, the uncalibrated logistic model at every severity is the "no intervention" control. Second, the majority-class predictor anchors the practical question of whether calibrated logistic predictions beat trivial decisions at each severity. Stronger comparators were not executed and are explicitly out of scope: temperature scaling as a third post-hoc calibrator, importance-weighted recalibration under shift (the natural adaptive baseline given the weighted conformal methods of [SOURCE-1], [SOURCE-3]), and a second base model to test whether the reported decoupling is specific to logistic regression. These are labeled future work in Sections 7 and 8.

**Metrics and protocol.** Primary reported metrics are accuracy (higher better), ECE (lower better), and AURC (lower better). ECE quantifies marginal probability quality; AURC quantifies selective-classification quality; accuracy quantifies unselective decision quality. The protocol is a single execution per cell under seed 42; no repeated trials, variance estimates, or significance tests are available, and all interpretation in Sections 6 and 7 is correspondingly descriptive.

**Ablation structure.** The calibration variant is the ablation axis (sigmoid and isotonic each ablated against the uncalibrated control), and severity is the stress axis. An additional structural ablation is embedded by design: calibration maps are fit once on held-out source-domain data and never refit under shift, so any severity-dependent change in ECE or AURC reflects the fragility of fixed post-hoc calibration rather than re-estimation noise.

## 5. Expected Results (Pre-Registered Hypotheses, Not Observed Outcomes)

This section states the hypotheses that motivated the study, formulated before inspection of the observed metrics; they are labeled as expectations, not as findings. **H1 (calibration invariance of decisions):** post-hoc calibration primarily rescales probabilities and was expected to leave argmax predictions—and hence accuracy—nearly unchanged. **H2 (calibration–selectivity alignment):** better-calibrated probabilities were expected to yield better-behaved confidence orderings and therefore lower AURC, so sigmoid and isotonic were both expected to reduce AURC relative to the uncalibrated control, with isotonic potentially stronger given its flexibility. **H3 (monotone severity degradation):** accuracy and calibration were expected to degrade monotonically as severity increases from 0.0 to 0.75 on both datasets, with majority-relative margins shrinking under shift. **H4 (cross-dataset consistency):** the ordering among variants was expected to be stable across datasets, so that a recommended calibrator on one dataset would transfer to the other. Section 6 reports the observed outcomes of this single executed run; as shown there, H2, H3, and H4 are each contradicted in at least one respect, which is precisely the empirical content of the audit.

## 6. Results

### 6.1 Iris: observed metrics

Table 1 summarizes all observed iris metrics.

**Table 1.** Observed iris metrics by severity and variant (accuracy higher better; AURC, ECE lower better).

| $\rho$ | Variant | Accuracy | AURC | ECE |
|---|---|---|---|---|
| 0.0 | isotonic | 0.933333 [RESULT-1] | 0.005185 [RESULT-2] | 0.05 [RESULT-3] |
| 0.0 | sigmoid | 0.933333 [RESULT-4] | 0.188889 [RESULT-5] | 0.196669 [RESULT-6] |
| 0.0 | uncalibrated | 0.933333 [RESULT-7] | 0.014729 [RESULT-8] | 0.112177 [RESULT-9] |
| 0.25 | isotonic | 0.923077 [RESULT-10] | 0.006946 [RESULT-11] | 0.057692 [RESULT-12] |
| 0.25 | sigmoid | 0.923077 [RESULT-13] | 0.161243 [RESULT-14] | 0.202486 [RESULT-15] |
| 0.25 | uncalibrated | 0.923077 [RESULT-16] | 0.017893 [RESULT-17] | 0.116041 [RESULT-18] |
| 0.5 | isotonic | 0.909091 [RESULT-19] | 0.009787 [RESULT-20] | 0.068182 [RESULT-21] |
| 0.5 | sigmoid | 0.909091 [RESULT-22] | 0.123967 [RESULT-23] | 0.215127 [RESULT-24] |
| 0.5 | uncalibrated | 0.909091 [RESULT-25] | 0.024363 [RESULT-26] | 0.130412 [RESULT-27] |
| 0.75 | isotonic | 0.909091 [RESULT-28] | 0.009787 [RESULT-29] | 0.068182 [RESULT-30] |
| 0.75 | sigmoid | 0.909091 [RESULT-31] | 0.123967 [RESULT-32] | 0.215127 [RESULT-33] |
| 0.75 | uncalibrated | 0.909091 [RESULT-34] | 0.024363 [RESULT-35] | 0.130412 [RESULT-36] |

The iris majority-class baseline accuracy is 0.333333 [RESULT-37].

Accuracy is invariant to the calibration variant at every severity: at $\rho=0.0$ the isotonic, sigmoid, and uncalibrated variants record 0.933333 [RESULT-1], 0.933333 [RESULT-4], and 0.933333 [RESULT-7], respectively; at $\rho=0.25$ they record 0.923077 [RESULT-10], 0.923077 [RESULT-13], and 0.923077 [RESULT-16]; at $\rho=0.5$ they record 0.909091 [RESULT-19], 0.909091 [RESULT-22], and 0.909091 [RESULT-25]; and at $\rho=0.75$ they record 0.909091 [RESULT-28], 0.909091 [RESULT-31], and 0.909091 [RESULT-34]. This confirms H1 on iris: calibration does not alter decisions, only confidences. Accuracy degrades monotonically with severity, from 0.933333 [RESULT-1] through 0.923077 [RESULT-10] to 0.909091 [RESULT-19], with no further change at $\rho=0.75$ (0.909091 [RESULT-28]); every variant exceeds the majority-class baseline of 0.333333 [RESULT-37] by a wide margin at every severity.

Isotonic calibration dominates both quality axes at every severity. At $\rho=0.0$ its AURC is 0.005185 [RESULT-2], versus 0.014729 [RESULT-8] for the uncalibrated control and 0.188889 [RESULT-5] for sigmoid, and its ECE is 0.05 [RESULT-3], versus 0.112177 [RESULT-9] and 0.196669 [RESULT-6]. The same ordering holds at $\rho=0.25$ (isotonic AURC 0.006946 [RESULT-11] versus 0.017893 [RESULT-17] and 0.161243 [RESULT-14]; isotonic ECE 0.057692 [RESULT-12] versus 0.116041 [RESULT-18] and 0.202486 [RESULT-15]) and at $\rho=0.5$ (isotonic AURC 0.009787 [RESULT-20] versus 0.024363 [RESULT-26] and 0.123967 [RESULT-23]; isotonic ECE 0.068182 [RESULT-21] versus 0.130412 [RESULT-27] and 0.215127 [RESULT-24]).

Sigmoid calibration is actively harmful on iris. At $\rho=0.0$ it worsens AURC by 0.174160 relative to the uncalibrated model, the difference between 0.188889 [RESULT-5] and 0.014729 [RESULT-8], and worsens ECE by 0.084492, the difference between 0.196669 [RESULT-6] and 0.112177 [RESULT-9]. Notably, sigmoid AURC improves as severity grows—from 0.188889 [RESULT-5] to 0.161243 [RESULT-14] to 0.123967 [RESULT-23]—yet remains the worst variant at every severity, while its ECE drifts upward from 0.196669 [RESULT-6] to 0.202486 [RESULT-15] to 0.215127 [RESULT-24]. Uncalibrated AURC rises with severity from 0.014729 [RESULT-8] to 0.017893 [RESULT-17] to 0.024363 [RESULT-26], isotonic AURC rises from 0.005185 [RESULT-2] to 0.006946 [RESULT-11] to 0.009787 [RESULT-20], and isotonic ECE rises from 0.05 [RESULT-3] to 0.057692 [RESULT-12] to 0.068182 [RESULT-21], consistent with H3 on this dataset.

Finally, the $\rho=0.5$ and $\rho=0.75$ rows are identical in every cell: isotonic accuracy 0.909091 [RESULT-28] equals 0.909091 [RESULT-19], isotonic AURC 0.009787 [RESULT-29] equals 0.009787 [RESULT-20], isotonic ECE 0.068182 [RESULT-30] equals 0.068182 [RESULT-21]; sigmoid accuracy 0.909091 [RESULT-31] equals 0.909091 [RESULT-22], sigmoid AURC 0.123967 [RESULT-32] equals 0.123967 [RESULT-23], sigmoid ECE 0.215127 [RESULT-33] equals 0.215127 [RESULT-24]; uncalibrated accuracy 0.909091 [RESULT-34] equals 0.909091 [RESULT-25], uncalibrated AURC 0.024363 [RESULT-35] equals 0.024363 [RESULT-26], and uncalibrated ECE 0.130412 [RESULT-36] equals 0.130412 [RESULT-27]. This exact coincidence indicates that the two settings produced effectively indistinguishable evaluation conditions on this small dataset, so severity saturation occurs at or before $\rho=0.5$ for iris.

### 6.2 Wine quality: observed metrics

Table 2 summarizes all observed wine_quality metrics.

**Table 2.** Observed wine_quality metrics by severity and variant.

| $\rho$ | Variant | Accuracy | AURC | ECE |
|---|---|---|---|---|
| 0.0 | isotonic | 0.515625 [RESULT-38] | 0.160671 [RESULT-39] | 0.354454 [RESULT-40] |
| 0.0 | sigmoid | 0.615625 [RESULT-41] | 0.415709 [RESULT-42] | 0.019094 [RESULT-43] |
| 0.0 | uncalibrated | 0.54375 [RESULT-44] | 0.024025 [RESULT-45] | 0.448188 [RESULT-46] |
| 0.25 | isotonic | 0.530035 [RESULT-47] | 0.158804 [RESULT-48] | 0.334098 [RESULT-49] |
| 0.25 | sigmoid | 0.621908 [RESULT-50] | 0.396727 [RESULT-51] | 0.005532 [RESULT-52] |
| 0.25 | uncalibrated | 0.54417 [RESULT-53] | 0.019301 [RESULT-54] | 0.449834 [RESULT-55] |
| 0.5 | isotonic | 0.54878 [RESULT-56] | 0.15147 [RESULT-57] | 0.325042 [RESULT-58] |
| 0.5 | sigmoid | 0.638211 [RESULT-59] | 0.367245 [RESULT-60] | 0.018625 [RESULT-61] |
| 0.5 | uncalibrated | 0.565041 [RESULT-62] | 0.017567 [RESULT-63] | 0.426696 [RESULT-64] |
| 0.75 | isotonic | 0.566502 [RESULT-65] | 0.135889 [RESULT-66] | 0.31533 [RESULT-67] |
| 0.75 | sigmoid | 0.674877 [RESULT-68] | 0.299455 [RESULT-69] | 0.055979 [RESULT-70] |
| 0.75 | uncalibrated | 0.600985 [RESULT-71] | 0.019442 [RESULT-72] | 0.38969 [RESULT-73] |

The wine_quality majority-class baseline accuracy is 0.534375 [RESULT-74].

Wine_quality inverts the iris picture in three respects. First, calibration alters decisions, refuting H1 on this dataset: at $\rho=0.0$ sigmoid accuracy is 0.615625 [RESULT-41], exceeding the uncalibrated 0.54375 [RESULT-44] by 0.071875, while isotonic accuracy is 0.515625 [RESULT-38], which falls below the majority-class baseline of 0.534375 [RESULT-74]. Isotonic remains below the baseline at $\rho=0.25$ (0.530035 [RESULT-47] against 0.534375 [RESULT-74]), a finding with direct deployment relevance. Second, sigmoid yields the best ECE at every severity—0.019094 [RESULT-43] at $\rho=0.0$, 0.005532 [RESULT-52] at $\rho=0.25$, 0.018625 [RESULT-61] at $\rho=0.5$, and 0.055979 [RESULT-70] at $\rho=0.75$—including an improvement of 0.429094 over the uncalibrated model at $\rho=0.0$ (the difference between 0.448188 [RESULT-46] and 0.019094 [RESULT-43]); isotonic ECE sits between the two throughout (0.354454 [RESULT-40], 0.334098 [RESULT-49], 0.325042 [RESULT-58], 0.31533 [RESULT-67]), while uncalibrated ECE is 0.448188 [RESULT-46], 0.449834 [RESULT-55], 0.426696 [RESULT-64], and 0.38969 [RESULT-73] across the grid. Yet sigmoid simultaneously yields the worst AURC at every severity—0.415709 [RESULT-42], 0.396727 [RESULT-51], 0.367245 [RESULT-60], 0.299455 [RESULT-69]—an AURC excess of 0.391684 over the uncalibrated control at $\rho=0.0$ (the difference between 0.415709 [RESULT-42] and 0.024025 [RESULT-45]). The uncalibrated model provides the best confidence ranking throughout (AURC 0.024025 [RESULT-45], 0.019301 [RESULT-54], 0.017567 [RESULT-63], 0.019442 [RESULT-72]), and isotonic never beats it (0.160671 [RESULT-39] versus 0.024025 [RESULT-45]; 0.158804 [RESULT-48] versus 0.019301 [RESULT-54]; 0.15147 [RESULT-57] versus 0.017567 [RESULT-63]; 0.135889 [RESULT-66] versus 0.019442 [RESULT-72]).

Third, and most anomalously, accuracy improves monotonically with severity for every variant: sigmoid rises from 0.615625 [RESULT-41] to 0.621908 [RESULT-50] to 0.638211 [RESULT-59] to 0.674877 [RESULT-68]; uncalibrated rises from 0.54375 [RESULT-44] to 0.54417 [RESULT-53] to 0.565041 [RESULT-62] to 0.600985 [RESULT-71]; isotonic rises from 0.515625 [RESULT-38] to 0.530035 [RESULT-47] to 0.54878 [RESULT-56] to 0.566502 [RESULT-65]. Uncalibrated AURC also improves non-monotonically from 0.024025 [RESULT-45] to 0.019301 [RESULT-54] to 0.017567 [RESULT-63] before a slight rise to 0.019442 [RESULT-72], and uncalibrated ECE falls from 0.448188 [RESULT-46] to 0.38969 [RESULT-73]. Because a covariate shift that improves all variants simultaneously contradicts the intended stress semantics, this pattern is treated as an unexplained anomaly of the harness conditions rather than a substantive finding (Section 7). The majority-relative margins also grow under this anomaly: sigmoid's margin over the baseline widens from 0.081250 at $\rho=0.0$ (the difference between 0.615625 [RESULT-41] and 0.534375 [RESULT-74]) to 0.140502 at $\rho=0.75$ (the difference between 0.674877 [RESULT-68] and 0.534375 [RESULT-74]), whereas the uncalibrated margin at $\rho=0.0$ is only 0.009375 (the difference between 0.54375 [RESULT-44] and 0.534375 [RESULT-74]).

### 6.3 Synthesis

Four cross-dataset findings follow from the supplied records alone. **(i) Calibration error and selective risk decouple, and the direction is dataset-dependent.** The variant ordering by ECE and by AURC disagrees on wine_quality at every severity (best ECE under sigmoid: 0.019094 [RESULT-43], 0.005532 [RESULT-52], 0.018625 [RESULT-61], 0.055979 [RESULT-70]; best AURC under the uncalibrated control: 0.024025 [RESULT-45], 0.019301 [RESULT-54], 0.017567 [RESULT-63], 0.019442 [RESULT-72]), refuting H2 in general, whereas on iris isotonic is best on both axes (AURC 0.005185 [RESULT-2]; ECE 0.05 [RESULT-3] at $\rho=0.0$). **(ii) No calibrator is uniformly safe.** Sigmoid is harmful on iris (AURC 0.188889 [RESULT-5] versus 0.014729 [RESULT-8] at $\rho=0.0$) yet delivers the highest accuracy on wine_quality (0.615625 [RESULT-41] versus 0.54375 [RESULT-44] at $\rho=0.0$), refuting H4; isotonic dominates on iris yet falls below the majority-class baseline on wine_quality at low severity (0.515625 [RESULT-38] and 0.530035 [RESULT-47] against 0.534375 [RESULT-74]). **(iii) Severity is not a monotone stressor across datasets.** Iris degrades monotonically with saturation at $\rho \geq 0.5$ (e.g., 0.933333 [RESULT-1] to 0.909091 [RESULT-19]), refuting H3 on wine_quality, where all variants improve (e.g., sigmoid 0.615625 [RESULT-41] to 0.674877 [RESULT-68]). **(iv) Decision invariance is dataset-specific.** H1 holds exactly on iris and fails on wine_quality, consistent with the renormalization mechanism of Section 3.3.

## 7. Discussion

**Interpretation.** The central lesson is that post-hoc calibration should not be treated as a reliability monolith. ECE rewards marginal agreement between confidence and accuracy; AURC rewards ordinal alignment of confidence with correctness. On wine_quality, sigmoid calibration compresses the probability scale enough to achieve near-perfect marginal calibration (e.g., ECE 0.005532 [RESULT-52]) while destroying the ranking information that the raw logistic confidences carried (AURC 0.396727 [RESULT-51] versus 0.019301 [RESULT-54] uncalibrated). This confirms, on tabular logistic models under controlled shift, the distinction long appreciated in selective-prediction work [SOURCE-13], [SOURCE-23].

**Limitations and threats to validity.** The study is a single execution under seed 42 with no repeated trials; no variance estimates or significance tests are possible, so "pronounced" describes magnitude within this record, not statistical certainty. The datasets are small: the coincidence of all iris metrics at $\rho=0.5$ and $\rho=0.75$ (e.g., AURC 0.009787 [RESULT-20] and 0.009787 [RESULT-29]) indicates that the severity knob saturates on this dataset, and accuracies of the form 0.909091-type ratios show that evaluation denominators are small and vary with severity, so small differences should not be over-interpreted. The monotone accuracy improvement under shift on wine_quality (e.g., 0.615625 [RESULT-41] to 0.674877 [RESULT-68]) is anomalous relative to the intended stress semantics; candidate explanations—interaction of the perturbation with feature standardization or majority-class dominance 0.534375 [RESULT-74], or severity-dependent evaluation-set composition—are hypotheses for future work, not results, and the anomaly is a flagged validity threat. Documentation gaps remain: the harness does not expose the perturbation operator, the calibration sub-split size, the ECE bin count, or the base-model solver and regularization settings beyond implementation defaults. Three natural comparators were not executed—temperature scaling, importance-weighted recalibration in the spirit of [SOURCE-1], [SOURCE-3], and a second base model such as those in [SOURCE-7]—so claims about the generality of the decoupling beyond logistic regression are not supported by this record. No pooled statistics across datasets are reported, by design.

**Broader impact and ethics.** Selective classification increasingly mediates human-facing deferral decisions, including cost-aware clinical triage [SOURCE-23]; a calibrator chosen for ECE alone could systematically mis-rank which cases are deferred, concentrating errors on unpredicted instances. The practical recommendation is explicit: reliability audits for drifting tabular deployments must measure ECE and AURC separately and must always include a majority-class reference, since a deployed model can sit below trivial performance (0.515625 [RESULT-38] against 0.534375 [RESULT-74]) while appearing well calibrated on one axis. Both datasets are public benchmarks with no human-subject or privacy concerns; the wine-quality domain is low-stakes, but the audit protocol is intended to transfer to higher-stakes tabular settings where miscalibrated abstention carries real cost.

## 8. Conclusion

This paper reported a controlled empirical audit (`tabular_calibration_selective_v1`) of post-hoc probability calibration—sigmoid and isotonic—applied to a logistic regression classifier on the iris and wine_quality tabular datasets (wine_quality binarized as good = quality $\geq$ 6), evaluated against an uncalibrated control and a majority-class baseline across fixed covariate-shift severities of 0.0, 0.25, 0.5, and 0.75, with all 74 observed metrics of that executed run reported verbatim. The observed results, attributable specifically to this executed logistic-regression-plus-fixed-calibration configuration, demonstrate that calibration error and selective risk can decouple sharply and in dataset-dependent directions (sigmoid best in ECE yet worst in AURC on wine_quality, e.g., 0.019094 [RESULT-43] versus 0.415709 [RESULT-42]; isotonic best on both axes on iris, e.g., 0.005185 [RESULT-2] and 0.05 [RESULT-3]); that no tested calibrator is uniformly beneficial; and that shift severity does not act as a monotone stressor across datasets, with an anomalous improvement on wine_quality flagged for investigation. Future work should extend the audit with temperature scaling, importance-weighted recalibration under shift, additional base models, repeated seeds with variance estimates, and larger datasets.