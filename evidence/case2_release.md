# Rank Stability of Post-hoc Calibration under Covariate Shift: A Frozen-Protocol Controlled Study of One-vs-Rest Logistic Regression with Sigmoid and Isotonic Calibration on Wine Quality and Iris

## Abstract

Post-hoc calibration methods such as Platt-style sigmoid scaling and isotonic regression are widely used to correct classifier confidence, yet they are usually validated on unshifted data and judged by a single metric. This paper reports an executed, frozen-protocol study (`tabular_calibration_selective_v1`) centered on the wine_quality dataset — quality binarized into good (quality ≥ 6) versus bad — with iris executed under the identical protocol as a secondary contrast dataset. A one-vs-rest logistic regression classifier, trained from first principles, is compared under three confidence treatments — uncalibrated, sigmoid-calibrated, and isotonic-calibrated — against a majority-class baseline, at four fixed covariate-shift severity levels (0.0, 0.25, 0.5, 0.75), measured by accuracy, positive-class expected calibration error (ECE$_{+}$), and selective risk–coverage area (AURC). Under this single-execution protocol, rankings were stable with respect to severity within each dataset: no severity-driven rank reversal occurred for any metric. Reversals instead appeared across metrics and datasets. On wine_quality, the sigmoid treatment attained the highest accuracy (0.615625 [RESULT-41]) and the best AURC (0.019094 [RESULT-43]) yet the worst ECE$_{+}$ (0.415709 [RESULT-42]) at severity 0.0, whereas uncalibrated scores attained the best ECE$_{+}$ (0.024025 [RESULT-45]) but the worst AURC (0.448188 [RESULT-46]); on iris, isotonic was best on both ECE$_{+}$ (0.005185 [RESULT-2]) and AURC (0.05 [RESULT-3]) while sigmoid was worst on both (0.188889 [RESULT-5]; 0.196669 [RESULT-6]). These dissociations, anticipated by counterexample theory but here instantiated in an executed severity-sweep pipeline, motivate multi-metric, multi-dataset evaluation before deploying calibration under shift.

## 1. Introduction

Reliable class-probability estimates are a prerequisite for deploying classifiers in settings where decisions are thresholded, deferred, or cost-weighted rather than reduced to a top-1 label. Post-hoc recalibration — fitting a lightweight map on a held-out calibration split on top of a frozen base classifier — is the dominant remedy for miscalibrated confidence, and a substantial body of *background* work studies how probability estimates and their evaluation might be adapted when training and deployment distributions differ, including importance estimation under covariate shift [SOURCE-3], class-prior and label shift [SOURCE-20], and the alignment of calibration evaluation with deployment error costs in clinical settings [SOURCE-17]. None of that corrective machinery is executed in the present study; it serves as motivation. The working assumption in much applied practice is that a recalibration method which looks best on one dataset, under one metric, at one shift level, will remain best when any of those conditions change.

That assumption is theoretically suspect. Prior work constructs exact finite counterexamples showing that classification accuracy, strictly proper scores, and expected calibration error can diverge from one another, so that an improvement in one need not entail an improvement in the others [SOURCE-2]. Independent evidence from day-ahead load forecasting shows that average-error criteria can fail to rank forecasting configurations by the peak-alert reliability that actually matters operationally — an instance of metric-driven rank mismatch [SOURCE-5]. In selective prediction, where a classifier abstains below a confidence threshold, the interaction between calibration and the risk–coverage trade-off is known to change before and after calibration [SOURCE-7]. What this literature leaves open, and what motivates the executed study, is whether such dissociations arise *empirically inside a standard pipeline* as a function of covariate-shift severity — the deployment condition most often cited when recalibration is proposed.

The executed study is deliberately minimal and fully frozen. The base model is a set of independent one-vs-rest binary logistic regression classifiers trained with full-batch gradient descent from first principles; per-class logits are combined by softmax normalization. Post-hoc calibration is fitted only for the designated positive class, using either a grid-searched Platt-style sigmoid map or a pool-adjacent-violators isotonic map, with the remaining probability mass redistributed proportionally. The registered executed dataset is wine_quality, with the target binarized as good (quality ≥ 6) versus bad; the classical iris dataset was executed under the identical frozen protocol and is reported as a secondary contrast condition. Both datasets are compared against a majority-class baseline at four fixed severity levels, on three metric families: accuracy, positive-class ECE with 10 equal-width bins, and AURC estimated at ten fixed confidence thresholds. Severity 0.0 denotes the lowest-severity reference condition of the evaluation harness, not a claim of zero distributional change.

The contribution is deliberately bounded; the study introduces no new calibration method, no new theory, and no new estimator, and its two small datasets do not support a generality claim. Its contributions are: (i) a frozen, fully specified severity-sweep protocol for calibration and selective-classification evaluation on tabular data, in which every hyperparameter of the base learner, the calibration maps, and the metric estimators is fixed in advance and executed once; (ii) the executed observation that method rankings were stable across severity within each dataset — on both wine_quality and iris, the rank order of the three treatments was unchanged from severity 0.0 through 0.75 for all three metrics; (iii) the executed observation of sharp reversals along the other two axes — between datasets and between metric families; and (iv) practical guidance for evaluating shift-robust recalibration, together with an explicit statement of what was *not* executed: no shift-aware comparators (importance-weighted calibration, recalibration on shifted data, multiclass temperature scaling) and no ablations over calibration-set size, bin count, or shift mechanism. Those are future work, discussed as such in Sections 6 and 7.

## 2. Related Work

**Calibration error as a distinct statistical object.** A growing body of work argues that calibration error must be analyzed separately from accuracy and proper scoring rules. Minimal counterexamples demonstrate concretely that accuracy, strictly proper scores such as cross-entropy and Brier score, and expected calibration error can be decoupled in finite samples, undermining the practice of reading a low cross-entropy or calibration error as evidence of generally trustworthy probabilities [SOURCE-2]. In clinical applications, recent work argues that evaluation might align calibration assessment with label shift and the actual error costs of deployment, rather than with generic aggregate criteria [SOURCE-17]. A separate line develops corrective machinery for distribution change itself: importance estimation and weighting under covariate shift [SOURCE-3] and class-prior estimation under label shift [SOURCE-20]. These lines propose or analyze *corrective* methods; they are background here. The present study instead asks a prerequisite diagnostic question — whether the ranking of simple, widely used post-hoc calibrators is even stable as shift severity grows — and executes no corrective method. Its relationship to the counterexample literature [SOURCE-2] is explicitly one of instantiation: the paper contributes a two-dataset, four-severity grid in which the predicted dissociation arises in a standard pipeline, not a new theoretical result.

**Metric-driven rank mismatch and selective prediction.** Evidence from operational forecasting shows that hourly-average accuracy criteria fail to rank day-ahead configurations by peak-alert reliability, i.e., the metric choice reorders the candidates [SOURCE-5]. In selective prediction, accuracy-versus-coverage behavior changes before and after calibration, indicating that recalibration does not leave deferral behavior invariant [SOURCE-7]. The executed study contributes a tabular counterpart of these findings within a single frozen pipeline: on wine_quality, the sigmoid treatment wins accuracy and AURC while losing ECE$_{+}$ by a wide margin at every severity — a within-pipeline rank reversal across metric families (Section 5.2).

**Terminological contrast.** The word "calibration" also denotes correction for covariate measurement error in regression settings [SOURCE-1] and instrument recalibration after a standard shift in metrology and engineering contexts [SOURCE-4]. Those senses are unrelated to class-probability calibration studied here, but they share the structural concern that a fitted correction can silently lose validity when the reference conditions drift — the same concern that motivates the severity sweep in this paper.

## 3. Methodology

### 3.1 Problem setup

Let $\mathcal{D} = \{(x_i, y_i)\}_{i=1}^{n}$ be a tabular dataset with features $x_i \in \mathbb{R}^d$ and labels $y_i \in \{1, \dots, K\}$. Let $c_+$ denote the designated positive class, defined as the last class in sorted label order. The study evaluates a single base architecture under three confidence treatments $m \in \{\text{uncalibrated}, \text{sigmoid}, \text{isotonic}\}$, against a majority-class baseline, at four fixed covariate-shift severity levels $s \in \{0.0, 0.25, 0.5, 0.75\}$, where 0.0 denotes the lowest-severity reference condition of the evaluation harness and larger values denote stronger fixed covariate shift applied to the evaluation condition. The severity levels and the transformation that realizes them are fixed by the harness and are not tunable inputs; the frozen contract reported below does not further specify the functional form of that transformation, which is acknowledged as a limitation in Section 7. For each dataset, severity, and treatment, three quantities are measured: accuracy, positive-class expected calibration error ($\mathrm{ECE}_{+}$), and the area under the risk–coverage curve (AURC).

### 3.2 Frozen method contract (reproduced verbatim)

The following method contract was frozen prior to execution and is reproduced verbatim:

- The base model is a set of independent one-vs-rest binary logistic regression classifiers. Each binary model is trained with full-batch gradient descent (learning rate 0.05, 1000 epochs, L2 penalty 0.001) implemented from first principles; no external machine-learning library is used. Per-class scores are combined into class probabilities by softmax normalization of the per-class logits.
- Post-hoc calibration is fitted only for the designated positive class (the last class in sorted label order). Sigmoid (Platt-style) parameters are selected by grid search over a fixed candidate set of (a, b) values minimizing binary cross-entropy on the calibration split; an isotonic map (pool-adjacent-violators) is fitted on the positive-class probability against the indicator y = positive class. At application time only the positive-class probability is calibrated; the remaining probability mass is redistributed across the other classes proportionally to their uncalibrated probabilities.
- Expected calibration error (ECE) is computed with 10 equal-width bins on the positive-class probability: within each bin it compares the mean positive-class probability against the empirical frequency of the positive class (y = positive class), and averages the absolute gaps weighted by bin size. It is not the standard top-class-confidence ECE.
- The area under the risk-coverage curve (AURC) is estimated by evaluating selective risk and coverage at ten fixed confidence thresholds (0.0 to 0.9 in steps of 0.1), using the maximum class probability as the confidence score and correctness of the predicted class as the risk basis, then trapezoid-integrating those ten (coverage, risk) points. It is not an integral over the full sample ordering.

### 3.3 Formal details

Each binary submodel for class $k$ minimizes the L2-regularized negative log-likelihood

$$
\min_{w_k,\,b_k}\; -\frac{1}{n}\sum_{i=1}^{n}\Big[\mathbb{1}[y_i = k]\log\sigma(z_k(x_i)) + \mathbb{1}[y_i \neq k]\log\big(1-\sigma(z_k(x_i))\big)\Big] \;+\; \lambda \,\|w_k\|_2^2,
$$

where $z_k(x) = w_k^\top x + b_k$, $\sigma(z) = (1 + e^{-z})^{-1}$, and $\lambda = 0.001$, using full-batch gradient descent with learning rate $0.05$ for $1000$ epochs. Class probabilities are obtained by softmax normalization of the per-class logits,

$$
\hat p_k(x) \;=\; \frac{\exp(z_k(x))}{\sum_{j=1}^{K}\exp(z_j(x))}.
$$

**Post-hoc calibration of the positive class.** The sigmoid treatment applies a Platt-style map to the positive-class probability,

$$
q_+(x) \;=\; \sigma\!\big(a\,\hat p_{c_+}(x) + b\big),
$$

with $(a,b)$ selected by grid search over a fixed candidate set minimizing binary cross-entropy on the calibration split. The isotonic treatment fits a monotone map $q_+(x) = g(\hat p_{c_+}(x))$ by pool-adjacent-violators against the indicator $y = c_+$. In both cases the calibrated class distribution renormalizes by proportional redistribution:

$$
\tilde p_{c_+}(x) = q_+(x), \qquad
\tilde p_j(x) = \hat p_j(x)\,\frac{1 - q_+(x)}{1 - \hat p_{c_+}(x)} \quad (j \neq c_+),
$$

and predictions are $\hat y(x) = \arg\max_k \tilde p_k(x)$. Because redistribution changes relative mass among the non-positive classes, calibration can change the argmax prediction — a property that proves consequential in the results. The uncalibrated treatment uses $\hat p$ directly.

**Metrics.** With equal-width bins $B_1, \dots, B_{10}$ on the positive-class probability,

$$
\mathrm{ECE}_{+} \;=\; \sum_{b=1}^{10} \frac{|B_b|}{n}\,\Big|\,\frac{1}{|B_b|}\sum_{i \in B_b}\tilde p_{c_+}(x_i)\;-\;\frac{1}{|B_b|}\sum_{i \in B_b}\mathbb{1}[y_i = c_+]\Big|.
$$

Selective AURC uses the confidence score $\kappa(x) = \max_k \tilde p_k(x)$. At thresholds $\tau_j \in \{0.0, 0.1, \dots, 0.9\}$,

$$
c(\tau_j) = \frac{|\{i : \kappa(x_i) \ge \tau_j\}|}{n}, \qquad
r(\tau_j) = \frac{1}{|\{i : \kappa(x_i) \ge \tau_j\}|}\sum_{i:\,\kappa(x_i)\ge\tau_j}\mathbb{1}[\hat y(x_i)\neq y_i],
$$

and $\mathrm{AURC}$ is the trapezoidal integral of the ten points $(c(\tau_j), r(\tau_j))$. Lower values of $\mathrm{ECE}_{+}$ and $\mathrm{AURC}$ indicate better calibration and better selective behavior respectively; higher accuracy is better.

### 3.4 Execution details

For each dataset the data are split stratified by target, with the first 80% as train and the last 20% as test, under a fixed shuffle with seed 42. The protocol was executed once; there are no seed replications or repeated runs. Consequently, all statements below — including the statement that no rank reversal occurred across severity — are descriptive of this single executed run, and no statistical significance test is reported; the absence of replications makes such a test impossible, which is stated as a limitation in Section 7.

## 4. Experimental Design

**Datasets.** The registered executed dataset is wine_quality, a physicochemical wine dataset whose target is binarized into good (quality ≥ 6) and bad (quality < 6) and whose classes exhibit imbalance, reflected in the majority-class baseline of 0.534375 [RESULT-74]. The iris dataset — the classical three-class flower-measurement dataset with four continuous features, majority-class baseline 0.333333 [RESULT-37] — was executed under the identical frozen protocol and is reported as a secondary contrast condition. No other dataset was executed.

**Conditions.** The design crosses three factors: dataset (wine_quality, iris), covariate-shift severity (0.0, 0.25, 0.5, 0.75, fixed by the harness), and confidence treatment (uncalibrated, sigmoid, isotonic), yielding twelve executed cells per dataset plus the registered baseline. The registered primary metric of the study is the baseline accuracy (majority_class), which anchors the difficulty of each dataset; the analysis additionally examines accuracy, $\mathrm{ECE}_{+}$, and AURC for the three treatments. All treatments share the identical base learner, calibration split usage, and evaluation sets at a given dataset and severity, so observed differences are attributable to the calibration map and its redistribution step.

**Comparator adequacy (explicit scope).** The comparator set includes a majority-class baseline and the uncalibrated treatment (the naive in-domain analog), and the naive cross-condition behavior is implicitly present, since every calibrator is fitted on the calibration split and evaluated at shifted conditions. The design does *not* include shift-aware comparators — importance-weighted calibration [SOURCE-3] as background motivation, recalibration on shifted data, or multiclass temperature scaling — and executes no ablations over calibration-set size, bin count, or shift mechanism. For a study whose subject is shift robustness this is a significant gap; these comparators and ablations are therefore labeled unexecuted future work (Sections 6 and 7) and must not be read as findings.

**Protocol details.** The base learner's hyperparameters are fixed by the frozen contract (learning rate 0.05, 1000 full-batch epochs, L2 penalty 0.001) and are not tuned per dataset. The sigmoid and isotonic maps are fitted on the calibration split only for the designated positive class; the contract does not further specify the construction of the calibration split beyond its being held out, which is fixed by the harness. The metric estimators are exactly those of Section 3.2, including the 10-bin positive-class ECE and the ten-threshold trapezoidal AURC; these estimators are deliberately coarse and fixed, which avoids tuning the evaluation to any treatment [SOURCE-14].

**Ablation structure.** The severity sweep functions as the shift ablation: because treatments are compared at identical severities within a dataset, any change in ranking across severity levels would isolate the effect of covariate shift on the comparison. The treatment axis functions as the calibration ablation (none vs. parametric sigmoid vs. nonparametric isotonic). No other ablation axes were executed.

## 5. Results

### 5.1 Iris (secondary contrast dataset)

| Severity | Treatment | Accuracy | ECE$_{+}$ | AURC |
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
| — | majority_class (baseline) | 0.333333 [RESULT-37] | — | — |

On iris, accuracy is identical across the three treatments at every severity (isotonic 0.933333 [RESULT-1], sigmoid 0.933333 [RESULT-4], uncalibrated 0.933333 [RESULT-7] at severity 0.0), so positive-class calibration never changed the argmax prediction on this dataset. Accuracy declines modestly with severity, from 0.933333 [RESULT-7] to 0.909091 [RESULT-34] for the uncalibrated treatment, and all treatments remain far above the majority-class baseline of 0.333333 [RESULT-37]. Calibration separates the treatments sharply on the other two metrics, with a stable order at every severity: isotonic $<$ uncalibrated $<$ sigmoid. At severity 0.0 the AURC order is 0.05 [RESULT-3] $<$ 0.112177 [RESULT-9] $<$ 0.196669 [RESULT-6], and the same order holds for $\mathrm{ECE}_{+}$ (0.005185 [RESULT-2] $<$ 0.014729 [RESULT-8] $<$ 0.188889 [RESULT-5]). Notably, the sigmoid treatment is substantially *worse* than no calibration at all on both metrics at all severities on this dataset (e.g., $\mathrm{ECE}_{+}$ 0.188889 [RESULT-5] versus 0.014729 [RESULT-8], and AURC 0.196669 [RESULT-6] versus 0.112177 [RESULT-9] at severity 0.0). Finally, every iris value at severity 0.75 equals its severity-0.5 counterpart (accuracy 0.909091 [RESULT-28] versus 0.909091 [RESULT-19]; $\mathrm{ECE}_{+}$ 0.024363 [RESULT-35] versus 0.024363 [RESULT-26]; AURC 0.130412 [RESULT-36] versus 0.130412 [RESULT-27]); this is consistent with, though not proof of, a saturation of the severity transformation on this dataset (internal reasoning).

### 5.2 Wine quality (registered executed dataset)

| Severity | Treatment | Accuracy | ECE$_{+}$ | AURC |
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
| — | majority_class (baseline) | 0.534375 [RESULT-74] | — | — |

On wine_quality, unlike iris, calibration changed accuracy: the sigmoid treatment attains the highest accuracy at every severity (0.615625 [RESULT-41], 0.621908 [RESULT-50], 0.638211 [RESULT-59], 0.674877 [RESULT-68]), exceeding the uncalibrated treatment (0.54375 [RESULT-44], 0.54417 [RESULT-53], 0.565041 [RESULT-62], 0.600985 [RESULT-71]) and the isotonic treatment (0.515625 [RESULT-38], 0.530035 [RESULT-47], 0.54878 [RESULT-56], 0.566502 [RESULT-65]). The isotonic treatment falls below the majority-class baseline of 0.534375 [RESULT-74] at the two lowest severities (0.515625 [RESULT-38] at severity 0.0 and 0.530035 [RESULT-47] at severity 0.25), while the sigmoid treatment exceeds the same baseline by a margin computed from the executed values as 0.615625 [RESULT-41] minus 0.534375 [RESULT-74] equals 0.08125 at severity 0.0, growing to 0.674877 [RESULT-68] minus 0.534375 [RESULT-74] equals 0.140502 at severity 0.75. A further observation, reported without causal interpretation, is that accuracy increases with severity for all three treatments on this dataset.

The metric dissociation on wine_quality is stark and holds at every severity. The sigmoid treatment is simultaneously the *best* on AURC (0.019094 [RESULT-43], 0.005532 [RESULT-52], 0.018625 [RESULT-61], 0.055979 [RESULT-70]) and the *worst* on $\mathrm{ECE}_{+}$ (0.415709 [RESULT-42], 0.396727 [RESULT-51], 0.367245 [RESULT-60], 0.299455 [RESULT-69]), with an AURC gap relative to the uncalibrated treatment of roughly an order of magnitude or more at every severity (e.g., 0.448188 [RESULT-46] versus 0.019094 [RESULT-43] at severity 0.0). Symmetrically, the uncalibrated treatment attains the *best* $\mathrm{ECE}_{+}$ at every severity (0.024025 [RESULT-45], 0.019301 [RESULT-54], 0.017567 [RESULT-63], 0.019442 [RESULT-72]) yet the *worst* AURC at every severity (0.448188 [RESULT-46], 0.449834 [RESULT-55], 0.426696 [RESULT-64], 0.38969 [RESULT-73]); for instance, at severity 0.5 it attains the best $\mathrm{ECE}_{+}$ (0.017567 [RESULT-63]) and the worst AURC (0.426696 [RESULT-64]). The isotonic treatment occupies intermediate positions on both metrics on this dataset (e.g., $\mathrm{ECE}_{+}$ 0.15147 [RESULT-57] and AURC 0.325042 [RESULT-58] at severity 0.5).

### 5.3 Answering the research question

**Severity stability.** Within each dataset, no rank reversal was observed across the severity sweep for any metric in this single executed run. On iris, the ordering isotonic $<$ uncalibrated $<$ sigmoid holds for both $\mathrm{ECE}_{+}$ and AURC at all four severities (Section 5.1), and accuracy is tied throughout. On wine_quality, the ordering sigmoid $>$ uncalibrated $>$ isotonic holds for accuracy, uncalibrated $<$ isotonic $<$ sigmoid holds for $\mathrm{ECE}_{+}$, and sigmoid $<$ isotonic $<$ uncalibrated holds for AURC, at all four severities (Section 5.2). Under this protocol, increasing covariate-shift severity from 0.0 to 0.75 changed magnitudes but never changed rankings.

**Cross-dataset and cross-metric reversals.** The reversals appear along the other two axes. Across datasets: isotonic, the strongest treatment on iris at severity 0.0 for both $\mathrm{ECE}_{+}$ (0.005185 [RESULT-2]) and AURC (0.05 [RESULT-3]), is never the best treatment on wine_quality at any severity for any metric (e.g., $\mathrm{ECE}_{+}$ 0.160671 [RESULT-39] and AURC 0.354454 [RESULT-40] at severity 0.0); conversely, sigmoid, the worst treatment on iris for both $\mathrm{ECE}_{+}$ (0.188889 [RESULT-5]) and AURC (0.196669 [RESULT-6]) at severity 0.0, delivers the best accuracy (0.615625 [RESULT-41]) and the best AURC (0.019094 [RESULT-43]) on wine_quality at the same severity. Across metrics: on wine_quality, the treatment with the best $\mathrm{ECE}_{+}$ has the worst AURC and vice versa, at every severity (Section 5.2). Severity, the axis the sweep was designed to stress, was the only axis along which rankings did not move.

## 6. Expected Results

This section states hypotheses for future work; none of the following outcomes has been observed, and no additional datasets, methods, ablations, or replications were executed.

First, it is hypothesized that the metric dissociation will persist on additional tabular datasets, particularly those with class imbalance and confidence distributions resembling wine_quality, on which the redistribution step demonstrably changes argmax predictions (accuracy diverged across treatments, e.g., 0.615625 [RESULT-41] versus 0.515625 [RESULT-38] versus 0.54375 [RESULT-44] at severity 0.0). Conversely, datasets resembling iris, on which calibration left predictions and confidence orderings essentially intact (tied accuracies, e.g., 0.933333 [RESULT-1], 0.933333 [RESULT-4], 0.933333 [RESULT-7]), are expected to show metric agreement.

Second, it is hypothesized that severity-driven rank reversals may emerge at shifts more extreme than the highest executed level (0.75). The observed stability could reflect the bounded severity grid rather than a general law; the identical iris rows at severities 0.5 and 0.75 suggest the applied transformation saturates on that dataset (internal reasoning), and a wider grid might eventually reorder treatments. This remains untested.

Third — explicitly labeled future work, not executed here — shift-aware comparators such as importance-weighted calibration (motivated by background work on importance estimation under covariate shift [SOURCE-3]), recalibration on shifted data, and multiclass temperature scaling, together with ablations over calibration-set size, bin count, and shift mechanism, are expected to narrow the $\mathrm{ECE}_{+}$ degradation observed for the sigmoid treatment on wine_quality (0.415709 [RESULT-42] at severity 0.0) without necessarily preserving its AURC advantage (0.019094 [RESULT-43] at severity 0.0). Any such method should be evaluated under a multi-metric, multi-dataset severity sweep before deployment; single-metric validation on a single dataset would repeat the failure mode documented in Section 5. Expected quantitative improvements are deliberately not speculated, since none were observed.

## 7. Discussion

**Limitations.** The study executes one base learner (linear, one-vs-rest), two small datasets — with wine_quality as the registered dataset and iris as a contrast — and one calibration-target design (positive class only, with proportional redistribution), so the findings characterize this frozen stack rather than post-hoc calibration in general; the contribution is a controlled diagnostic vignette, not a generalizable empirical law, and the central dissociation is anticipated theoretically by counterexample constructions [SOURCE-2]. The protocol was executed once with a single fixed split (stratified by target, first 80% train / last 20% test, fixed shuffle, seed 42) and no replications, so the claim that no severity-driven rank reversal occurred is descriptive of one run and carries no statistical test. The comparator set omits shift-aware baselines — importance-weighted calibration, recalibration on shifted data, and multiclass temperature scaling were not executed — and no ablations over calibration-set size, bin count, or shift mechanism were run; for a shift-robustness study these omissions bound the strength of any recommendation. The severity construction is fixed by the harness and its functional form is not part of the frozen contract, so its saturation on iris cannot be fully diagnosed from the executed results (internal reasoning); likewise, the contract does not further specify the construction of the calibration split, which is fixed by the harness.

**Implications.** The central practical lesson is negative and useful: a severity sweep alone does not stress-test a calibration method, because rankings were severity-stable yet dataset- and metric-unstable. Practitioners who select a calibrator by calibration error on one dataset may deploy the worst possible deferral policy: on wine_quality, the treatment with the best $\mathrm{ECE}_{+}$ at severity 0.0 (uncalibrated, 0.024025 [RESULT-45]) simultaneously has the worst AURC (0.448188 [RESULT-46]), while the treatment with the best AURC (sigmoid, 0.019094 [RESULT-43]) has the worst $\mathrm{ECE}_{+}$ (0.415709 [RESULT-42]).

**Broader impact and ethics.** Selective classification is often deployed precisely where errors are costly; a miscalibrated confidence ordering can silently concentrate errors in the region where the system claims to be reliable. More generally, the redistribution step that improved accuracy on wine_quality (0.615625 [RESULT-41] versus 0.54375 [RESULT-44] at severity 0.0) also degraded selective risk there, a reminder that interventions on probability outputs have distributional side effects; documentation of deployed calibrators should therefore report all three metric families, not only the one that motivated the intervention.

## 8. Conclusion

This paper reported an executed, frozen-protocol study (`tabular_calibration_selective_v1`) of post-hoc calibration ranking stability under covariate shift, centered on the wine_quality dataset (target binarized as good versus bad) with iris as a secondary contrast, comparing one-vs-rest logistic regression under uncalibrated, sigmoid (Platt-style), and isotonic confidence treatments against a majority-class baseline, at four fixed severity levels, measured by accuracy, positive-class ECE, and threshold-based AURC. The executed results attribute to this specific method stack the following observations: rankings were stable across severity within each dataset, while across metrics on wine_quality the sigmoid treatment attained the highest accuracy (0.615625 [RESULT-41], 0.621908 [RESULT-50], 0.638211 [RESULT-59], 0.674877 [RESULT-68]) and the best AURC (0.019094 [RESULT-43], 0.005532 [RESULT-52], 0.018625 [RESULT-61], 0.055979 [RESULT-70]) yet the worst ECE$_{+}$ (0.415709 [RESULT-42], 0.396727 [RESULT-51], 0.367245 [RESULT-60], 0.299455 [RESULT-69]), and the uncalibrated treatment attained the best ECE$_{+}$ (0.024025 [RESULT-45], 0.019301 [RESULT-54], 0.017567 [RESULT-63], 0.019442 [RESULT-72]) yet the worst AURC (0.448188 [RESULT-46], 0.449834 [RESULT-55], 0.426696 [RESULT-64], 0.38969 [RESULT-73]); on iris, isotonic was best on both metrics (e.g., 0.005185 [RESULT-2] and 0.05 [RESULT-3] at severity 0.0) and sigmoid worst. The conclusion for practice is that calibration methods must be validated with multiple metric families on multiple datasets before deployment under shift; severity robustness alone certifies nothing. Future work — none of it executed here — should extend the severity grid beyond 0.75, add seed-level replications with a formal rank-stability test, and evaluate shift-corrected, importance-weighted recalibration schemes, recalibration on shifted data, and multiclass temperature scaling under this same multi-metric protocol, alongside ablations over calibration-set size, bin count, and shift mechanism.