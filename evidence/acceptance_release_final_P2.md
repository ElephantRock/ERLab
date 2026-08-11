# Polynomial-Feature Multinomial Logistic Regression on the Iris Benchmark: Empirical Comparison with a Majority-Class Baseline

## Abstract

This paper evaluates a predeclared polynomial-feature multinomial logistic regression model on the frozen Iris benchmark and compares it with a majority-class baseline using test accuracy as the primary metric. The classifier uses degree-two polynomial features and a one-vs-rest logistic-regression formulation trained iteratively with IRLS/Newton updates. On the frozen test split, the majority-class baseline achieved an accuracy of 0.333333 [RESULT-1], the fitted model achieved 0.966667 [RESULT-3], and the absolute improvement was 0.633333 [RESULT-2]. These results show a large empirical advantage for the registered model on this split. The paper reports the executed experiment and its observed results; it does not claim statistical significance, distribution-free certification, or a validated numerical generalization bound beyond what is supported by the recorded experiment.

## 1. Introduction

Logistic regression is widely used for tabular classification because its parameters are interpretable and its optimization and regularization behavior are well understood. Polynomial feature expansion can extend a linear decision function by introducing interaction and nonlinear terms, but it also increases feature dimensionality and can increase the risk of overfitting.

This study evaluates a registered multinomial logistic-regression experiment on the Iris benchmark. The predeclared comparison is between a degree-two polynomial-feature logistic-regression model and a majority-class baseline. The primary question is empirical and deliberately narrow:

> On the frozen Iris test split, does the registered logistic-regression model achieve higher test accuracy than the majority-class baseline?

The executed experiment answered that question on the frozen split. The majority-class baseline achieved 0.333333 [RESULT-1], the fitted model achieved 0.966667 [RESULT-3], and the absolute improvement was 0.633333 [RESULT-2].

The contributions of this paper are therefore limited to the registered experiment and the evidence it produced: a reproducible specification of the model and evaluation protocol, a direct baseline comparison, and a traceable report of the observed metrics.

## 2. Related Work

Logistic regression has been applied across clinical and tabular prediction settings. Safitri, Chamidah, and Saifudin modeled stroke risk using binary logistic regression alongside multivariate adaptive regression splines [SOURCE-22]. Metharani, Srividya, and Rekha reported a diabetes-risk forecasting application using logistic regression [SOURCE-25]. Kannan and Dudi proposed a hybrid binary classifier that incorporated modified logistic regression [SOURCE-26].

Work on logistic-regression variants also includes kernel and multinomial formulations. Rahayu, Purnami, and Embong applied kernel logistic regression to credit-risk classification [SOURCE-3], while Moghimbeygi described a multinomial logistic-regression approach for shape-data classification [SOURCE-8].

These studies provide context for the use of logistic regression and its variants. The present work does not attempt to establish a new general theorem about logistic-regression generalization. Its narrower purpose is to report a registered experiment on Iris with an explicit majority-class baseline and traceable observed results.

## 3. Methodology

### 3.1 Problem Definition

Let the training data be

\[
\mathcal{D}_{\mathrm{train}} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{N},
\]

where \(\mathbf{x}_i \in \mathbb{R}^4\) contains the four Iris measurements and \(y_i \in \{1,2,3\}\) denotes one of the three Iris classes.

The registered model is evaluated on a frozen train/test split. The comparison model is a majority-class baseline that predicts the most frequent training class for every test example.

The primary metric is test accuracy. Higher values are better.

### 3.2 Polynomial Feature Construction

A degree-two polynomial map expands the four original measurements into monomials up to degree two. With the bias term included, the resulting feature dimension is

\[
D_p = \binom{4+2}{2} = 15.
\]

The same feature construction is applied consistently to the frozen training and test data.

### 3.3 Multinomial Logistic Regression

The multiclass problem is handled with a one-vs-rest decomposition. For each class \(k\), a binary logistic-regression model is fit against all other classes. At inference time, the model predicts the class with the largest one-vs-rest score.

This decomposition is part of the registered method reported by the experiment.

### 3.4 IRLS Optimization

Logistic regression does not have a single-step closed-form solution for its coefficients. The registered solver instead uses Iteratively Reweighted Least Squares (IRLS), equivalently a sequence of Newton-style updates. Each iteration constructs and solves a weighted linear system derived from the current logistic probabilities, then updates the coefficient vector.

The procedure stops when the coefficient change falls below the configured convergence tolerance or when the configured iteration limit is reached. The important distinction is that the *linear system inside each iteration* can be solved by normal-equation methods; the logistic-regression fit itself remains iterative.

### 3.5 Scope of Theoretical Claims

The original draft included an excess-risk discussion based on an uncited internal complexity argument. The supplied evidence does not establish all assumptions required for a validated numerical Rademacher-complexity bound, and the executed experiment does not test such a bound.

Accordingly, this paper makes no claim that the observed performance constitutes a distribution-free guarantee or formal certification. The polynomial feature dimension \(D_p=15\) and the small benchmark size are reported as methodological context only. The empirical claims in this paper are restricted to the frozen experiment and its recorded metrics.

## 4. Experimental Design

### 4.1 Dataset

The Iris benchmark contains 150 observations, four numeric measurements, and three classes. The experiment uses a frozen training split and a frozen test split. The split is fixed before model fitting and is not altered during evaluation.

### 4.2 Baseline

The baseline predicts the most frequent class from the training split for every test observation. On the executed frozen split, its measured test accuracy was 0.333333 [RESULT-1].

### 4.3 Primary Metric

The sole primary metric reported here is test accuracy:

\[
\mathrm{Accuracy}
=
\frac{\text{number of correct test predictions}}
{\text{number of test observations}}.
\]

Higher accuracy is better.

### 4.4 Evaluation Protocol

Degree-two polynomial features are constructed from the frozen data. The one-vs-rest logistic-regression models are fit with the registered IRLS procedure. The fitted model and the majority-class baseline are then evaluated once on the same frozen test split.

No claim of statistical significance is made because the supplied experiment reports point estimates from this frozen evaluation rather than a repeated-sampling significance analysis.

### 4.5 Non-Executed Extensions

The original draft described possible ablations involving polynomial degree, regularization strength, and alternative multiclass formulations. Those analyses were not part of the recorded experiment and are therefore not reported as results. They remain possible follow-on experiments rather than evidence for the present paper.

## 5. Results

The majority-class baseline achieved a test accuracy of **0.333333** [RESULT-1].

The registered polynomial-feature multinomial logistic-regression model achieved a test accuracy of **0.966667** [RESULT-3].

The resulting absolute accuracy improvement was **0.633333** [RESULT-2].

These three values are the observed outputs of the executed experiment. On this frozen test split, the registered model therefore outperformed the majority-class baseline by a large absolute margin.

No additional ablation, confidence interval, cross-validation estimate, or significance test is inferred from these results because those quantities were not supplied by the executed experiment.

## 6. Discussion

### 6.1 Principal Finding

The registered model substantially outperformed the registered majority-class baseline on the frozen Iris test split. The observed model accuracy was 0.966667 [RESULT-3], compared with 0.333333 [RESULT-1] for the baseline, yielding an absolute improvement of 0.633333 [RESULT-2].

This supports the experiment's narrow empirical conclusion: under the registered data split, feature construction, model, and evaluation procedure, the fitted logistic-regression model achieved higher test accuracy than the trivial baseline.

### 6.2 Interpretation

The result is compatible with the model capturing class structure that the majority-class predictor cannot represent. However, the experiment does not by itself establish that degree-two polynomial features are necessary for Iris, that the same margin will hold on other train/test splits, or that the observed result generalizes to unrelated datasets.

The comparison should therefore be interpreted as evidence about this registered experiment, not as a universal guarantee about polynomial logistic regression.

### 6.3 Limitations

Several limitations constrain the conclusions.

First, the experiment reports one frozen train/test evaluation rather than repeated cross-validation or repeated resampling. The reported accuracies are therefore point estimates for that split.

Second, the registered comparison uses a majority-class baseline. This is an appropriate trivial reference but does not establish superiority over stronger classifiers or over a linear logistic-regression model without polynomial expansion.

Third, the supplied experiment does not provide a statistical significance test or confidence interval for the accuracy difference. The paper therefore reports the observed difference without labeling it statistically significant.

Fourth, the original draft's excess-risk argument was not sufficiently supported to justify a formal numerical generalization claim. That claim has been removed rather than strengthened without evidence.

### 6.4 Reproducibility and Evidence Scope

The empirical statements in this paper are tied to the registered experiment and its result markers. In particular:

- 0.333333 [RESULT-1] is the observed majority-class baseline accuracy.
- 0.966667 [RESULT-3] is the observed fitted-model accuracy.
- 0.633333 [RESULT-2] is the observed absolute improvement.

Any future extension—such as alternative feature degrees, stronger baselines, confidence intervals, or repeated evaluation—should be executed and recorded as a new experiment rather than inferred from the present run.

## 7. Conclusion

This paper reports a registered comparison between polynomial-feature multinomial logistic regression and a majority-class baseline on the frozen Iris benchmark. The majority-class baseline achieved 0.333333 [RESULT-1], the fitted logistic-regression model achieved 0.966667 [RESULT-3], and the absolute improvement was 0.633333 [RESULT-2].

The experiment therefore provides direct empirical evidence that the registered model outperformed the registered trivial baseline on this frozen test split. The conclusion is intentionally limited to the evidence produced by the experiment. No unsupported significance, universal generalization, or formal certification claim is added.

Future work may evaluate stronger baselines, repeated train/test splits, alternative polynomial degrees, or alternative multiclass formulations, but those questions require new executed evidence.

## References

[SOURCE-3] S. P. Rahayu, S. W. Purnami, A. Embong (2008). Applying Kernel Logistic Regression in data mining to classify credit risk. *2008 International Symposium on Information Technology.*

[SOURCE-8] Meisam Moghimbeygi. A Method to Classify Shape Data using Multinomial Logistic Regression Model. *Statistics, Optimization & Information Computing.*

[SOURCE-22] Lensa Rosdiana Safitri, Nur Chamidah, Toha Saifudin (2024). Modeling risk of stroke using binary logistic regression and multivariate adaptive regression splines. *AIP Conference Proceedings.*

[SOURCE-25] Metharani N, Srividya R, Rekha G (2021). Diabetes Risk Forecasting Using Logistic Regression. *Advances in Parallel Computing.*

[SOURCE-26] Sarnath Kannan, Sanjay Dudi (2015). A hybrid binary classifier: Using modified Logistic Regression for non-support vector elimination. *2015 IEEE Recent Advances in Intelligent Computational Systems (RAICS).*
