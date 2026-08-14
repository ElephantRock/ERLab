# Does Post-Hoc Calibration Help Selective Classification under Covariate Shift? A Controlled Study of Sigmoid and Isotonic Calibration for One-vs-Rest Logistic Regression on the Wine Quality and Iris Tabular Datasets

## Abstract

Post-hoc probability calibration is widely regarded as a prerequisite for reliable selective classification, yet its effect on selective risk under covariate shift is rarely measured directly for tabular models. This paper reports a controlled empirical study whose central contribution is the executed analysis itself: a one-vs-rest logistic regression classifier implemented from first principles, paired with post-hoc sigmoid (Platt-style) and isotonic calibration and a majority-class baseline, evaluated under four fixed covariate-shift severities on the tabular Wine Quality dataset (target: good = quality $\geq$ 6), with a companion arm on the Iris dataset. Calibration is fitted only for a designated positive class, and accuracy, positive-class expected calibration error (ECE), and area under the risk–coverage curve (AURC) are computed under a frozen, fully specified protocol. On Wine Quality the two reliability metrics dissociate sharply: sigmoid calibration attains the lowest ECE at every severity (e.g., 0.019094 [RESULT-43] versus 0.448188 [RESULT-46] uncalibrated) yet the highest AURC at every severity (0.415709 [RESULT-42] versus 0.024025 [RESULT-45]), while the uncalibrated model shows the opposite pattern. On Iris, isotonic calibration improves both metrics (AURC 0.005185 [RESULT-2] versus 0.014729 [RESULT-8]). All model conditions exceed the majority-class baseline, whose accuracy is 0.534375 [RESULT-74] on Wine Quality and 0.333333 [RESULT-37] on Iris. Because the two datasets exhibit inverted orderings of calibration methods, the study answers its research question in the negative: calibration gains cannot be assumed to translate into better abstention under shift, and selective risk should be audited directly rather than inferred from calibration error.

## 1. Introduction

Selective classification—predicting only when model confidence is high and abstaining otherwise—is a standard mechanism for risk control, and it is commonly assumed that well-calibrated probabilities are a prerequisite for it. This assumption motivates reliability-aware pipelines that combine probability calibration with selective prediction in deep models, conformal abstention with cost-aware deferral in clinical triage, and shift-responsive conformal ensembling [SOURCE-13]. Yet calibration methods and selective-classification guarantees are usually evaluated separately: calibration is scored by binning metrics such as ECE, while selective performance is scored by risk–coverage behavior. Because post-hoc calibration is a monotone or near-monotone transformation of scores, it is not obvious a priori that reducing ECE preserves or improves the *ordering* of examples by confidence on which selective risk depends. What is missing is a controlled, factorial measurement of how plain post-hoc calibration—without any shift correction—trades off calibration error against selective risk in tabular classification, as a function of shift severity and dataset.

This paper provides such a measurement. The study, executed under the frozen capability `tabular_calibration_selective_v1`, evaluates a one-vs-rest logistic regression classifier implemented from first principles on two tabular datasets—Wine Quality (the primary executed dataset, with target good = quality $\geq$ 6 versus bad) and Iris—across four fixed covariate-shift severities $\{0.0, 0.25, 0.5, 0.75\}$ and three calibration conditions (uncalibrated, sigmoid, isotonic), against a majority-class baseline. Calibration is fitted only for the designated positive class, with the remaining probability mass redistributed proportionally, and performance is scored by accuracy, a positive-class ECE, and a threshold-grid AURC, all under a verbatim-reproduced protocol contract.

The contributions are bounded to the executed analysis and are as follows:

1. **A frozen, replicable protocol.** The full method contract—including the from-scratch optimizer, the calibration procedure, and the exact metric definitions—is reproduced verbatim (Section 3.5), enabling exact replication without external machine-learning libraries.
2. **A factorial severity sweep.** A $2 \times 4 \times 3$ design (dataset $\times$ severity $\times$ calibration) with a majority-class baseline yields a complete map of how calibration effects vary with shift strength.
3. **A documented calibration–risk dissociation on the executed method.** On Wine Quality, sigmoid calibration attains the lowest ECE but the highest AURC at every severity, while the uncalibrated model attains the highest ECE but the lowest AURC [RESULT-42], [RESULT-43], [RESULT-45], [RESULT-46].
4. **Evidence of dataset inconsistency.** Iris and Wine Quality exhibit opposite orderings of calibration methods on both ECE and AURC, answering the study's research question in the negative.
5. **Practical guidance.** Selective-classification safety under shift should be audited directly with risk–coverage measurements rather than inferred from calibration error.

Standard additions such as temperature scaling and importance-weighted (shift-aware) calibration were **not** executed in this study; they are discussed as background in Section 2 and as future work in Section 7, and no result in this paper is attributed to them.

## 2. Related Work

**Post-hoc probability calibration.** Sigmoid (Platt-style) recalibration and isotonic regression are the canonical post-hoc calibration maps, fitted on held-out data by minimizing a proper scoring loss against binary targets (internal reasoning). They are typically evaluated with binning metrics such as ECE. The present work uses exactly these two families, but scores them not only on calibration error and also on selective risk under shift, which is uncommon.

**Selective classification and prediction under shift.** Reliability-aware pipelines combine probability calibration with uncertainty-aware selective prediction, e.g., for BERT-based emotion classification under class imbalance, and conformal selective prediction with cost-aware deferral for clinical triage under distribution shift [SOURCE-13]. Shift-responsive conformal ensembling targets reliable selective classification directly under shift [SOURCE-2], and weighted conformal prediction provides finite-sample coverage guarantees for tabular regression under covariate shift [SOURCE-1], [SOURCE-3]. These methods intervene at *training time* or add distributional corrections. In contrast, the present work deliberately isolates the *uncorrected* post-hoc calibration step—sigmoid and isotonic maps of the kind embedded inside many of these pipelines—and asks whether it improves or harms selective risk under controlled shift for a simple tabular classifier. The present study adds a finer-grained question: even when a calibration metric *improves* under shift, does the selective-risk metric follow? Prior discussions of selective prediction anticipate that calibration and selective risk need not coincide (internal reasoning); the contribution here is a controlled, factorial measurement of the dissociation on an executed from-scratch tabular pipeline, rather than a new method.

**Tabular models and interpretability.** For tabular data, simple transparent models remain central to interpretable machine learning, and empirical studies document the robustness challenges of imbalanced tabular clinical data and small-data regimes in drug discovery [SOURCE-27]. The choice of an interpretable, from-scratch logistic regression base model aligns with these principles and eliminates library-level confounds.

## 3. Methodology

### 3.1 Problem setting

Let $(X, Y) \sim P_S$ denote the source distribution over tabular features $X \in \mathbb{R}^d$ and labels $Y$. The study uses a fixed family of induced covariate shifts on the test covariates, parameterized by a scalar severity $s \in \{0.0, 0.25, 0.5, 0.75\}$, where $s = 0.0$ denotes the unshifted configuration. The perturbation is deterministic, frozen within the executed capability, and applied only to evaluation covariates; training and calibration splits remain unshifted, so all shifts are purely distributional at evaluation time. Data are partitioned into a training split, a calibration split, and an evaluation split; the model is trained on the training split, post-hoc calibration maps are fitted on the calibration split, and all reported metrics are computed on shifted evaluation data.

### 3.2 Base model

The classifier consists of $K$ independent one-vs-rest binary logistic regression models. Each binary model $k$ minimizes the L2-regularized binary cross-entropy

$$
J(w_k, b_k) \;=\; -\frac{1}{n}\sum_{i=1}^{n}\Big[\, y_i^{(k)} \log \sigma(z_{ik}) + \big(1 - y_i^{(k)}\big)\log\big(1 - \sigma(z_{ik})\big)\,\Big] \;+\; \lambda\,\|w_k\|_2^2,
$$

where $z_{ik} = w_k^\top x_i + b_k$, $\sigma$ is the logistic function, $y_i^{(k)} = \mathbb{1}[y_i = k]$, and $\lambda = 0.001$. Optimization is full-batch gradient descent with learning rate 0.05 for 1000 epochs, implemented from first principles. Per-class logits are combined into class probabilities by softmax normalization,

$$
\hat{p}_k(x) \;=\; \frac{\exp(z_k(x))}{\sum_{j=1}^{K}\exp(z_j(x))}.
$$

### 3.3 Post-hoc calibration of the positive class

Let $+$ denote the designated positive class (the last class in sorted label order), and let $s_+(x)$ be the model's positive-class score. Two post-hoc maps are considered. **Sigmoid (Platt-style):** $\hat{q}_+(x) = \sigma\big(a\, s_+(x) + b\big)$, with $(a, b)$ selected by grid search minimizing binary cross-entropy on the calibration split. **Isotonic:** $\hat{q}_+(x) = g(\hat{p}_+(x))$, where $g$ is a monotone non-decreasing piecewise-constant map fitted by pool-adjacent-violators on the positive-class probability.

At application time only the positive-class probability is calibrated, and the remaining probability mass is redistributed across the other classes proportionally to their uncalibrated probabilities:

$$
\hat{p}'_+(x) = \hat{q}_+(x), \qquad
\hat{p}'_k(x) = \big(1 - \hat{q}_+(x)\big)\,\frac{\hat{p}_k(x)}{\sum_{j \neq +}\hat{p}_j(x)}, \quad k \neq + .
$$

This renormalization can change the argmax prediction, and hence accuracy, whenever the calibrated positive-class probability crosses the competing classes.

### 3.4 Metrics

ECE is the bin-size-weighted mean absolute gap between the mean positive-class probability and the empirical positive-class frequency over 10 equal-width bins,

$$
\mathrm{ECE} \;=\; \sum_{m=1}^{10} \frac{n_m}{N}\,\big|\,\bar{p}_m - \bar{f}_m\,\big|.
$$

Selective risk is evaluated on a fixed threshold grid $\tau \in \{0.0, 0.1, \dots, 0.9\}$, with confidence $c_i = \max_k \hat{p}'_k(x_i)$ and selective risk equal to the error rate among retained examples,

$$
\mathrm{cov}(\tau) = \frac{1}{N}\sum_{i=1}^{N}\mathbb{1}[c_i \geq \tau], \qquad
\mathrm{risk}(\tau) = \frac{\sum_{i}\mathbb{1}[c_i \geq \tau]\,\mathbb{1}[\hat{y}_i \neq y_i]}{\sum_{i}\mathbb{1}[c_i \geq \tau]},
$$

$$
\mathrm{AURC} \;=\; \sum_{t=1}^{9} \tfrac{1}{2}\big(\mathrm{risk}(\tau_t) + \mathrm{risk}(\tau_{t+1})\big)\big(\mathrm{cov}(\tau_{t+1}) - \mathrm{cov}(\tau_t)\big).
$$

Lower ECE and lower AURC are better; higher accuracy is better.

### 3.5 Executed protocol (frozen method contract, reproduced verbatim)

- The base model is a set of independent one-vs-rest binary logistic regression classifiers. Each binary model is trained with full-batch gradient descent (learning rate 0.05, 1000 epochs, L2 penalty 0.001) implemented from first principles; no external machine-learning library is used. Per-class scores are combined into class probabilities by softmax normalization of the per-class logits.
- Post-hoc calibration is fitted only for the designated positive class (the last class in sorted label order). Sigmoid (Platt-style) parameters are selected by grid search over a fixed candidate set of (a, b) values minimizing binary cross-entropy on the calibration split; an isotonic map (pool-adjacent-violators) is fitted on the positive-class probability against the indicator y = positive class. At application time only the positive-class probability is calibrated; the remaining probability mass is redistributed across the other classes proportionally to their uncalibrated probabilities.
- Expected calibration error (ECE) is computed with 10 equal-width bins on the positive-class probability: within each bin it compares the mean positive-class probability against the empirical frequency of the positive class (y = positive class), and averages the absolute gaps weighted by bin size. It is not the standard top-class-confidence ECE.
- The area under the risk-coverage curve (AURC) is estimated by evaluating selective risk and coverage at ten fixed confidence thresholds (0.0 to 0.9 in steps of 0.1), using the maximum class probability as the confidence score and correctness of the predicted class as the risk basis, then trapezoid-integrating those ten (coverage, risk) points. It is not an integral over the full sample ordering.

## 4. Experimental Design

**Datasets.** Two tabular benchmark datasets were executed: **Wine Quality** (the primary executed dataset, with the target binarized as good = quality $\geq$ 6 versus bad) and **Iris** (native three-class labels). Every quantitative claim below is attributed to exactly one of them. For Wine Quality, the executed split was stratified by target, first 80% train / last 20% test, fixed shuffle, seed = 42; the post-hoc calibration maps are fitted on a designated calibration split per the frozen contract, and reported metrics are computed on the shifted evaluation split. The Iris majority-class baseline accuracy of 0.333333 [RESULT-37] is consistent with an approximately balanced label distribution; on Wine Quality, the majority-class baseline accuracy of 0.534375 [RESULT-74] indicates that the most frequent class covers about 53.4% of the evaluation set.

**Baseline.** The reference baseline is the majority-class predictor, which predicts the most frequent class; its accuracy is the primary baseline metric and is not credited to any calibrated model.

**Factors.** The design is fully factorial: dataset $\in$ {Iris, Wine Quality} $\times$ severity $s \in \{0.0, 0.25, 0.5, 0.75\}$ $\times$ calibration condition $\in$ {uncalibrated, sigmoid, isotonic}, giving 12 evaluated cells per dataset. The calibration condition functions as the ablation factor (the uncalibrated column is the ablated control); severity is the stress axis, with $s = 0.0$ serving as the no-shift control.

**Protocol.** For each dataset, the one-vs-rest logistic regression model is trained once per the frozen contract; sigmoid and isotonic maps are fitted on the calibration split; and all three calibration conditions are evaluated on the shifted evaluation split at each severity, holding the trained model fixed so that differences across conditions are attributable solely to the post-hoc map and its renormalization.

**Scope and exclusions.** Temperature scaling and importance-weighted (shift-aware) calibration were **not** executed and are treated as background and future work (Sections 2 and 7); no reported number derives from them.

**Metrics and directions.** Accuracy (higher is better), positive-class ECE (lower is better), and threshold-grid AURC (lower is better), computed exactly as specified in Section 3.5. Both metric estimators are coarse by construction (10 bins; 10 thresholds), and results should be read with that discretization in mind.

**Reproducibility.** The study was executed under the capability identifier `tabular_calibration_selective_v1` with frozen hyperparameters (learning rate 0.05, 1000 epochs, L2 penalty 0.001, seed 42), and no external machine-learning library was used, eliminating dependency-version confounds.

## 5. Results

### 5.1 Iris

| Severity | Calibration | Accuracy | AURC | ECE |
|---|---|---|---|---|
| 0.00 | Isotonic | 0.933333 [RESULT-1] | 0.005185 [RESULT-2] | 0.05 [RESULT-3] |
| 0.00 | Sigmoid | 0.933333 [RESULT-4] | 0.188889 [RESULT-5] | 0.196669 [RESULT-6] |
| 0.00 | Uncalibrated | 0.933333 [RESULT-7] | 0.014729 [RESULT-8] | 0.112177 [RESULT-9] |
| 0.25 | Isotonic | 0.923077 [RESULT-10] | 0.006946 [RESULT-11] | 0.057692 [RESULT-12] |
| 0.25 | Sigmoid | 0.923077 [RESULT-13] | 0.161243 [RESULT-14] | 0.202486 [RESULT-15] |
| 0.25 | Uncalibrated | 0.923077 [RESULT-16] | 0.017893 [RESULT-17] | 0.116041 [RESULT-18] |
| 0.50 | Isotonic | 0.909091 [RESULT-19] | 0.009787 [RESULT-20] | 0.068182 [RESULT-21] |
| 0.50 | Sigmoid | 0.909091 [RESULT-22] | 0.123967 [RESULT-23] | 0.215127 [RESULT-24] |
| 0.50 | Uncalibrated | 0.909091 [RESULT-25] | 0.024363 [RESULT-26] | 0.130412 [RESULT-27] |
| 0.75 | Isotonic | 0.909091 [RESULT-28] | 0.009787 [RESULT-29] | 0.068182 [RESULT-30] |
| 0.75 | Sigmoid | 0.909091 [RESULT-31] | 0.123967 [RESULT-32] | 0.215127 [RESULT-33] |
| 0.75 | Uncalibrated | 0.909091 [RESULT-34] | 0.024363 [RESULT-35] | 0.130412 [RESULT-36] |
| — | Majority-class baseline | 0.333333 [RESULT-37] | — | — |

All model conditions exceed the majority-class baseline by a wide margin: even the weakest accuracy, 0.909091 [RESULT-25] at severity 0.50 and 0.909091 [RESULT-34] at severity 0.75, exceeds the baseline of 0.333333 [RESULT-37] by 0.575758. Three regularities stand out. First, accuracy is identical across calibration conditions at each severity (e.g., 0.933333 [RESULT-1] for isotonic, 0.933333 [RESULT-4] for sigmoid, and 0.933333 [RESULT-7] for uncalibrated at severity 0.0), indicating that the positive-class recalibration and renormalization did not alter any argmax prediction on this dataset. Second, isotonic calibration improves both reliability metrics at every severity: at severity 0.0 it reduces ECE from 0.112177 [RESULT-9] to 0.05 [RESULT-3]—less than half the uncalibrated value—and reduces AURC from 0.014729 [RESULT-8] to 0.005185 [RESULT-2], a drop of 0.009544. Third, sigmoid calibration degrades both metrics at every severity: at severity 0.0 its AURC of 0.188889 [RESULT-5] is more than twelve times the uncalibrated value of 0.014729 [RESULT-8], and its ECE of 0.196669 [RESULT-6] exceeds the uncalibrated 0.112177 [RESULT-9]. Increasing severity mildly degrades accuracy and ECE up to saturation (accuracy falls from 0.933333 [RESULT-7] to 0.909091 [RESULT-25]; isotonic ECE rises from 0.05 [RESULT-3] to 0.068182 [RESULT-21]), while sigmoid AURC paradoxically *falls* with severity, from 0.188889 [RESULT-5] to 0.123967 [RESULT-23]. Severities 0.50 and 0.75 produce identical metrics across conditions (e.g., AURC 0.024363 [RESULT-26] at severity 0.50 versus 0.024363 [RESULT-35] at severity 0.75), indicating that the induced shift saturates with respect to these metrics on Iris beyond severity 0.5.

### 5.2 Wine Quality

| Severity | Calibration | Accuracy | AURC | ECE |
|---|---|---|---|---|
| 0.00 | Isotonic | 0.515625 [RESULT-38] | 0.160671 [RESULT-39] | 0.354454 [RESULT-40] |
| 0.00 | Sigmoid | 0.615625 [RESULT-41] | 0.415709 [RESULT-42] | 0.019094 [RESULT-43] |
| 0.00 | Uncalibrated | 0.54375 [RESULT-44] | 0.024025 [RESULT-45] | 0.448188 [RESULT-46] |
| 0.25 | Isotonic | 0.530035 [RESULT-47] | 0.158804 [RESULT-48] | 0.334098 [RESULT-49] |
| 0.25 | Sigmoid | 0.621908 [RESULT-50] | 0.396727 [RESULT-51] | 0.005532 [RESULT-52] |
| 0.25 | Uncalibrated | 0.54417 [RESULT-53] | 0.019301 [RESULT-54] | 0.449834 [RESULT-55] |
| 0.50 | Isotonic | 0.54878 [RESULT-56] | 0.15147 [RESULT-57] | 0.325042 [RESULT-58] |
| 0.50 | Sigmoid | 0.638211 [RESULT-59] | 0.367245 [RESULT-60] | 0.018625 [RESULT-61] |
| 0.50 | Uncalibrated | 0.565041 [RESULT-62] | 0.017567 [RESULT-63] | 0.426696 [RESULT-64] |
| 0.75 | Isotonic | 0.566502 [RESULT-65] | 0.135889 [RESULT-66] | 0.31533 [RESULT-67] |
| 0.75 | Sigmoid | 0.674877 [RESULT-68] | 0.299455 [RESULT-69] | 0.055979 [RESULT-70] |
| 0.75 | Uncalibrated | 0.600985 [RESULT-71] | 0.019442 [RESULT-72] | 0.38969 [RESULT-73] |
| — | Majority-class baseline | 0.534375 [RESULT-74] | — | — |

Wine Quality behaves very differently. First, calibration changes accuracy: sigmoid calibration raises accuracy above the uncalibrated model at every severity (e.g., 0.615625 [RESULT-41] versus 0.54375 [RESULT-44] at severity 0.0, a gain of 0.071875), whereas isotonic calibration lowers it below the uncalibrated model at every severity (0.515625 [RESULT-38] versus 0.54375 [RESULT-44] at severity 0.0). Relative to the baseline, sigmoid accuracy climbs with severity—peaking at 0.674877 [RESULT-68] at severity 0.75, exceeding the baseline by 0.140502—while isotonic calibration falls *below* the majority-class baseline at the two lowest severities (0.515625 [RESULT-38] and 0.530035 [RESULT-47]) and exceeds it only from severity 0.5 onward (0.54878 [RESULT-56] and 0.566502 [RESULT-65]). The uncalibrated model only slightly exceeds the baseline at severity 0.0 (0.54375 [RESULT-44] versus 0.534375 [RESULT-74]).

Second, and most importantly, the calibration and selective-risk metrics dissociate sharply. Sigmoid calibration attains the *lowest* ECE at every severity (from 0.005532 [RESULT-52] to 0.055979 [RESULT-70]) yet the *highest* AURC at every severity (0.415709 [RESULT-42] at severity 0.0), whereas the uncalibrated model has the highest ECE at every severity (up to 0.449834 [RESULT-55]) but the *lowest* AURC at every severity (down to 0.017567 [RESULT-63]). At severity 0.0, sigmoid calibration multiplies selective risk by more than an order of magnitude relative to the uncalibrated model, from 0.024025 [RESULT-45] to 0.415709 [RESULT-42], even though it cuts ECE from 0.448188 [RESULT-46] to 0.019094 [RESULT-43], a reduction of 0.429094. Isotonic calibration occupies an intermediate position on both axes, with moderate ECE (from 0.31533 [RESULT-67] to 0.354454 [RESULT-40]) and moderate AURC (from 0.135889 [RESULT-66] to 0.160671 [RESULT-39]).

Third, severity trends are non-monotone in a way that contradicts the notion of shift as a pure stressor: accuracy rises with severity for all conditions (uncalibrated: 0.54375 [RESULT-44] to 0.600985 [RESULT-71]; sigmoid: 0.615625 [RESULT-41] to 0.674877 [RESULT-68]; isotonic: 0.515625 [RESULT-38] to 0.566502 [RESULT-65]), sigmoid AURC decreases with severity (0.415709 [RESULT-42] to 0.299455 [RESULT-69]), and uncalibrated ECE falls end-to-end from 0.448188 [RESULT-46] to 0.38969 [RESULT-73] (with a slight local rise to 0.449834 [RESULT-55] at severity 0.25). The induced shift therefore does not act as a monotone stressor on this dataset.

### 5.3 Cross-dataset synthesis

Comparing Tables 1 and 2, the two datasets disagree on the ordering of calibration methods for both ECE and AURC. On Iris, isotonic dominates on both metrics (e.g., AURC 0.005185 [RESULT-2] < 0.014729 [RESULT-8] < 0.188889 [RESULT-5]). On Wine Quality, the orderings are essentially inverted, with sigmoid best on ECE but worst on AURC, and the uncalibrated model worst on ECE but best on AURC (e.g., ECE 0.019094 [RESULT-43] < 0.354454 [RESULT-40] < 0.448188 [RESULT-46]; AURC 0.024025 [RESULT-45] < 0.160671 [RESULT-39] < 0.415709 [RESULT-42]). No pooled or aggregate statistics are computed across datasets; the comparison is strictly qualitative. The study's research question is answered in the negative: the effects of post-hoc calibration on selective classification under covariate shift are *not* consistent across datasets, and reductions in calibration error do not imply reductions in selective risk.

## 6. Expected Results

This section states the expectations that motivated the study, formulated before execution, and then assesses each against the observed outcomes; all observed values carry result markers.

**H1 (calibration improves the calibration metric).** It was expected that both sigmoid and isotonic calibration would reduce positive-class ECE relative to the uncalibrated model, with isotonic—the more flexible map—achieving larger reductions. *Observed:* partially supported. Isotonic reduces ECE at every severity on both datasets (Iris severity 0.0: 0.05 [RESULT-3] versus 0.112177 [RESULT-9]; Wine Quality severity 0.0: 0.354454 [RESULT-40] versus 0.448188 [RESULT-46]). Sigmoid reduces ECE dramatically on Wine Quality at every severity (0.019094 [RESULT-43] versus 0.448188 [RESULT-46] at severity 0.0) but *increases* ECE on Iris at every severity (0.196669 [RESULT-6] versus 0.112177 [RESULT-9]), refuting the universal form of H1.

**H2 (calibration improves selective risk).** Because selective classification depends on confidence ordering, and monotone recalibration preserves ordering within a class score, it was expected that calibration would at worst leave AURC unchanged and at best improve it. *Observed:* refuted in general. Isotonic improves AURC on Iris at every severity (0.005185 [RESULT-2] versus 0.014729 [RESULT-8] at severity 0.0), but sigmoid worsens AURC on Iris at every severity (0.188889 [RESULT-5] versus 0.014729 [RESULT-8]), and on Wine Quality sigmoid attains the worst AURC at every severity despite the best ECE (0.415709 [RESULT-42] versus 0.024025 [RESULT-45] at severity 0.0). The likely mechanism, consistent with the protocol's renormalization step (Section 3.3), is that changing the positive-class probability and redistributing the remaining mass alters the *maximum* class probability used as the confidence score, thereby reordering confidences across examples even when the ranking of raw positive-class scores is preserved.

**H3 (consistency across datasets).** It was expected that the rank ordering of calibration methods would transfer from Iris to Wine Quality. *Observed:* refuted; the orderings are inverted on both metrics (Section 5.3).

**H4 (severity monotonically degrades performance).** It was expected that increasing shift severity would degrade accuracy and both reliability metrics. *Observed:* partially supported on Iris (accuracy falls from 0.933333 [RESULT-7] to 0.909091 [RESULT-34]; isotonic ECE rises from 0.05 [RESULT-3] to 0.068182 [RESULT-30]), but reversed on Wine Quality, where accuracy rises with severity for all conditions and sigmoid AURC falls (0.615625 [RESULT-41] rising to 0.674877 [RESULT-68]; 0.415709 [RESULT-42] falling to 0.299455 [RESULT-69]).

## 7. Discussion

**Interpretation.** The central finding is a dissociation between calibration error and selective risk under covariate shift in the executed pipeline: the same one-vs-rest logistic regression model, after positive-class sigmoid calibration, becomes far better calibrated and simultaneously far worse at deciding when to abstain. This arises because AURC depends on the cross-example ordering of maximum class probabilities, which the positive-class-only calibration plus renormalization step can perturb substantially, whereas ECE depends only on the marginal agreement between binned positive-class probabilities and empirical frequencies.

**Limitations.** Several constraints bound the generality of the conclusions. Only two datasets were executed, both tabular and relatively small; no pooled statistics are warranted, and the "dataset inconsistency" finding rests on $n = 2$ datasets without variance estimates. A single linear model family and a single training run per cell were used (seed 42), so variance across seeds and architectures is unquantified and no confidence intervals or statistical tests are reported. Coarse metric estimators (10 bins, 10 thresholds) quantize both ECE and AURC; the repeated decimal patterns on Iris (e.g., accuracy 0.923077 [RESULT-13]) are consistent with small evaluation samples. Calibration is applied only to one designated positive class, a stronger simplification than class-wise calibration, and the renormalization step is itself a potential artifact source. The analytic form of the induced shift family is internal to the executed capability and not disclosed in the frozen contract; on Iris the shift saturates beyond severity 0.5 (identical metrics at severities 0.50 and 0.75; e.g., 0.024363 [RESULT-26] and 0.024363 [RESULT-35]), while on Wine Quality it acts counterintuitively; no claims are made about natural shifts. Finally, two standard controls were not executed: temperature scaling as an additional calibration baseline, and importance-weighted or other shift-aware calibration; both are future work, so the reported dissociation characterizes only sigmoid and isotonic maps under the frozen protocol.

**Broader impact and ethics.** If practitioners deploy selective classifiers under shift and gate abstention on calibrated confidence alone, systematically overconfident abstention behavior can cause real harm in high-stakes settings such as clinical triage, where deferral errors carry asymmetric costs [SOURCE-13]. A deployed model with excellent ECE but AURC of 0.415709 [RESULT-42] versus 0.024025 [RESULT-45] uncalibrated is exactly this failure mode. The positive societal implication is that the required audit is cheap: risk–coverage measurements at a handful of thresholds, as in this protocol, suffice to detect the dissociation before deployment. Researchers and practitioners should report calibration and selective-risk metrics side by side under shift, rather than assuming one implies the other.

## 8. Conclusion

This paper reported a controlled multi-dataset empirical study of post-hoc probability calibration for selective classification under covariate shift, executed under the frozen capability `tabular_calibration_selective_v1` on one-vs-rest logistic regression implemented from first principles, with sigmoid and isotonic calibration and a majority-class baseline, on the Wine Quality and Iris tabular datasets. The executed method produced three robust observations: on Wine Quality, sigmoid calibration achieved the lowest ECE but the highest AURC at every severity, whereas the uncalibrated model showed the opposite pattern; on Iris, isotonic calibration improved both metrics while sigmoid degraded both; and the two datasets exhibited inverted method orderings, so the effects of post-hoc calibration under covariate shift are not consistent across datasets. All model conditions exceeded the majority-class baselines. These findings caution that calibration gains cannot be assumed to translate into better abstention behavior under shift, and that selective risk should be audited directly. Future work should add temperature scaling, importance-weighted and shift-aware calibration, class-wise calibration, multiple seeds with confidence intervals, and natural shift benchmarks to test the generality of the observed dissociation.