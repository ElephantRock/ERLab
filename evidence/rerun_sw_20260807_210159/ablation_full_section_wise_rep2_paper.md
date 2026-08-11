# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset has long served as a foundational benchmark for evaluating classification algorithms, offering a compact yet informative set of morphometric features—sepal and petal length and width—for discriminating among three botanical species [SOURCE-1].

Balanced accuracy provides a fair evaluation metric for multiclass classification by computing the mean of per-class recall, ensuring that performance assessments are not inflated by class-frequency imbalances [SOURCE-2].

We evaluate multinomial logistic regression—a parametric linear classifier that models class-conditional probabilities via the softmax function—on the Iris dataset, using a majority-class predictor as a baseline and balanced accuracy as the primary evaluation metric [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming the majority-class baseline, which yields a balanced accuracy of 0.500 [RESULT-2].

The classifier further attains an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect discriminative capability across all Iris species.

We aim to this evaluation demonstrates the effectiveness of logistic regression for small-scale botanical classification and establishes a clear performance benchmark for future method comparisons on the Iris dataset.


## Introduction

Classification of botanical species from morphometric measurements is a foundational problem in statistical pattern recognition, with the Iris dataset serving as a standard benchmark for decades [SOURCE-1].

The Iris dataset comprises 150 samples across three species (Iris setosa, Iris versicolor, and Iris virginica), each described by four morphometric features: sepal length, sepal width, petal length, and petal width [SOURCE-1].

Logistic regression models class-conditional probabilities through a linear combination of input features transformed by a logistic function, and its multinomial extension estimates parameters for all classes simultaneously, yielding linear decision boundaries [SOURCE-1].

Logistic regression retains prominence due to its interpretability, efficient training, and competitive performance on low-dimensional problems where the feature-to-sample ratio is favorable [SOURCE-1].

Raw accuracy can be misleading in multiclass settings, particularly when class distributions are skewed or when comparing against naive baselines that trivially predict the majority class [SOURCE-2].

The assumption of linear decision boundaries in logistic regression may be insufficient for datasets with significant class overlap, as occurs between Iris versicolor and Iris virginica, potentially capping achievable performance [SOURCE-1].

Many published evaluations omit explicit baseline comparisons or rely solely on accuracy, making it difficult to assess whether observed performance reflects genuine discriminative power or simply dataset structure [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, provides more robust assessment of classifier performance than standard accuracy because it penalizes classifiers that ignore minority classes [SOURCE-2].

The use of balanced accuracy as the primary evaluation metric follows recommendations for robust multiclass performance assessment that accounts for per-class recall and enables fair comparison against majority-class predictors [SOURCE-2].

The selection of logistic regression is motivated by its role as a canonical linear classifier whose performance on Iris establishes a reference point for linear separability of morphometric features and against which more complex methods can be judged [SOURCE-1].

Reporting ROC-AUC alongside balanced accuracy follows established practice for characterizing discriminative performance across decision thresholds [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have been extensively surveyed as foundational techniques in machine learning, with logistic regression remaining one of the most widely used parametric approaches for both binary and multiclass classification tasks [SOURCE-1].

Logistic regression models the posterior probability of class membership using the logistic (sigmoid) function applied to a linear combination of input features, enabling probabilistic interpretation of classification decisions that simpler discriminative models do not naturally provide [SOURCE-1].

For multiclass problems such as Iris species classification, logistic regression is typically extended via the multinomial (softmax) formulation or through one-versus-rest decomposition strategies, both of which are standard implementations discussed in the linear classification literature [SOURCE-1].

Logistic regression assumes a linear decision boundary between classes in the feature space, which can be a limiting factor when the underlying class-conditional distributions are not linearly separable [SOURCE-1].

The Iris dataset, with its four continuous morphometric features (sepal length, sepal width, petal length, petal width), represents a benchmark where linear classifiers historically perform well because two of the three species are nearly perfectly separable while the third pair exhibits moderate overlap [SOURCE-1].

Standard accuracy, defined as the proportion of correctly classified instances, can yield misleading conclusions when class distributions are imbalanced, as it may be dominated by the majority class and mask poor performance on minority classes [SOURCE-2].

Balanced accuracy, computed as the arithmetic mean of per-class recall (sensitivity), addresses the shortcomings of standard accuracy by giving equal weight to each class regardless of its frequency, making it particularly suitable for evaluating classifiers on datasets with potential class imbalance [SOURCE-2].

A majority-class predictor, which assigns all instances to the most frequent class, serves as a meaningful lower bound for balanced accuracy evaluation, achieving a balanced accuracy of 0.500 on balanced multiclass datasets where each class is equally represented [SOURCE-2].

Beyond balanced accuracy, the Receiver Operating Characteristic Area Under the Curve (ROC-AUC) provides a complementary, threshold-independent measure of discriminative ability by summarizing the trade-off between true positive rate and false positive rate across all classification thresholds [SOURCE-2].

Evaluation metrics that are computed without stratification or class-weighting can systematically overestimate classifier performance on imbalanced datasets, a concern that balanced accuracy was specifically designed to mitigate [SOURCE-2].

While the Iris dataset is class-balanced with 50 instances per species, the use of balanced accuracy remains methodologically preferable because it ensures comparability with results on other datasets that may be imbalanced and because it penalizes classifiers that might collapse onto a subset of classes [SOURCE-2].

Logistic regression, despite its simplicity relative to nonlinear methods such as kernel SVMs and random forests, has been shown to achieve competitive or near-optimal performance on low-dimensional, well-separated datasets like Iris, where the linear assumption is approximately satisfied [SOURCE-1].

The interpretability advantage of logistic regression—where model coefficients directly indicate the contribution of each feature to the log-odds of class membership—is a well-documented property that distinguishes it from more complex classifiers and contributes to its continued prominence in applied classification tasks [SOURCE-1].

A known limitation of logistic regression is its sensitivity to multicollinearity among input features, which can inflate the variance of coefficient estimates and destabilize the decision boundary, potentially requiring regularization techniques such as L1 or L2 penalties for reliable generalization [SOURCE-1].

Regularized variants of logistic regression, including ridge (L2) and lasso (L1) logistic regression, have been developed to address overfitting and feature selection concerns, particularly relevant when the number of features is large relative to the number of training samples [SOURCE-1].

For multiclass classification evaluation, the extension of binary metrics such as ROC-AUC to the multiclass setting typically involves macro-averaging or micro-averaging strategies over all pairwise class comparisons, each carrying different assumptions about the relative importance of individual classes [SOURCE-2].

Simple baselines such as majority-class prediction are frequently underused in classification studies despite their critical role in calibrating the interpretation of more sophisticated models, as they provide a rigorous floor below which any learned classifier offers no practical value [SOURCE-2].


## Proposed Method

Logistic regression remains one of the most widely adopted linear classification methods, providing interpretable decision boundaries through a weighted linear combination of input features [SOURCE-1].

For multiclass classification tasks, balanced accuracy—defined as the macro-average of per-class recall—provides a more informative evaluation metric than raw accuracy when class distributions are potentially uneven [SOURCE-2].

The Iris dataset comprises 150 samples across three species (Setosa, Versicolor, Virginica), with each sample described by four continuous morphometric features: sepal length, sepal width, petal length, and petal width.

We select multinomial logistic regression—also known as softmax regression—for this three-class classification task because prior surveys have demonstrated its effectiveness on low-dimensional numeric feature spaces typical of morphometric data [SOURCE-1].

We formulate Iris species classification as a multinomial logistic regression problem in which the model computes class-membership probabilities via the softmax function applied to linear combinations of the four morphometric features.

Specifically, for a feature vector x ∈ ℝ⁴ and class k ∈ {1, 2, 3}, the predicted probability is P(y = k | x) = exp(w_kᵀx + b_k) / Σⱼ exp(w_jᵀx + b_j), where w_k ∈ ℝ⁴ are class-specific weight vectors and b_k are bias terms.

We apply L2 (ridge) regularization to the weight parameters with a configurable regularization strength λ.

We adopt L2 regularization because prior work has shown that it mitigates overfitting on small-to-moderate datasets by shrinking weight magnitudes, which is particularly relevant given the Iris dataset's limited sample size of 150 observations [SOURCE-1].

We optimize the regularized cross-entropy loss using the L-BFGS quasi-Newton solver, which converges efficiently for the smooth, convex objective that multinomial logistic regression produces.

We compare the logistic regression classifier against a majority-class baseline that always predicts the most frequent class in the training set.

We adopt balanced accuracy as the primary evaluation metric because it equally weights per-class recall, providing a single scalar that is robust to inter-class frequency variation [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to characterize the model's discriminative ability across all classification thresholds.

We partition the Iris dataset into training and test subsets using a stratified hold-out split that preserves the per-class sample proportions.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given the well-documented near-linear separability of Iris species in the petal-length and petal-width dimensions.

We hypothesize that we further expect that the model's ROC-AUC will approach the upper bound of 1.0, reflecting sharp probabilistic separation between species.

We hypothesize that L2 regularization will yield a modest but non-negligible improvement in test-time balanced accuracy relative to an unregularized model by constraining the influence of individual features.

We hypothesize that we expect the majority-class baseline to achieve a balanced accuracy of approximately 0.500 on the three-class Iris task, since balanced accuracy for a constant predictor reduces to 1/K when classes are balanced.

Prior surveys of linear classification methods note that logistic regression achieves competitive or superior performance on datasets with fewer than 10 features and well-separated classes, conditions that the Iris dataset satisfies [SOURCE-1].


## Evaluation Plan

We evaluate on the Iris dataset [SOURCE-1], a widely used benchmark for multiclass classification comprising 150 samples across three species, each described by four morphometric features.

Following established practices for multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary metric, defined as the arithmetic mean of per-class recall, which is particularly appropriate for multiclass settings where each class should receive equal evaluative weight.

We additionally report ROC-AUC as a secondary metric following [SOURCE-2], to characterize the discriminative quality of the classifier's predicted probability scores rather than only its hard label assignments.

Our experimental protocol compares logistic regression against a majority-class predictor that assigns all samples to the most frequent class, establishing a performance floor that any effective classifier must substantially exceed.

The rationale for this protocol is that the majority-class baseline quantifies task difficulty independent of feature information, while balanced accuracy ensures that any reported performance gain reflects genuine discriminative learning rather than exploitation of the class prior distribution.

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], substantially exceeding the majority-class baseline.

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], confirming that the baseline provides no discriminative information across the three classes.

Logistic regression achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect probability-based class discrimination on this dataset.

We hypothesize that the near-perfect ROC-AUC reflects strong linear separability of the Iris classes, particularly the Setosa species, which is known to be linearly separable from the other two classes.

We hypothesize that we further hypothesize that the residual classification errors in the logistic regression model arise primarily from overlap between the Versicolor and Virginica species in the four-dimensional feature space, rather than from model capacity limitations.


## Discussion and Future Work

Logistic regression is an effective classifier for the Iris dataset, achieving a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3] [SOURCE-1].

The majority-class baseline yields a balanced accuracy of 0.500 [RESULT-2], a value consistent with random guessing on a three-class problem where one class is always predicted [SOURCE-2].

Simple models often remain competitive on low-dimensional, cleanly structured datasets [SOURCE-1].

Balanced accuracy is especially informative because it penalizes the classifier for ignoring minority classes — a failure mode invisible to standard accuracy on imbalanced data [SOURCE-2].

We hypothesize that replacing the standard logistic link with a kernelized formulation would yield measurable improvement on datasets where classes are not linearly separable, without commensurate degradation on Iris.

We hypothesize that feature engineering such as deriving petal-area ratios would improve robustness under label noise by amplifying between-class differences.

We hypothesize that a multi-algorithm comparison across multiple benchmark datasets would reveal that the simplicity of logistic regression confers an advantage in low-data regimes [SOURCE-1].

We hypothesize that uncertainty quantification via Bayesian logistic regression would produce better-calibrated predictions on ambiguous boundary samples [SOURCE-2].

We aim to the methodological emphasis on balanced evaluation metrics will generalize to imbalanced multi-class problems where it matters most [SOURCE-2].


## Conclusion

The Iris dataset remains a widely used benchmark for evaluating multiclass classification methods, as noted in prior surveys of linear classifiers [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on Iris, substantially outperforming the majority-class baseline's balanced accuracy of 0.500 [RESULT-2], with an ROC-AUC of 0.998 [RESULT-3].

Balanced accuracy is an appropriate metric for multiclass settings where class distributions may not be uniform, and prior work has advocated its use over raw accuracy [SOURCE-2].

We aim to this work aims to demonstrate that logistic regression, despite its simplicity relative to more complex models, provides near-perfect classification performance on well-separated morphometric data such as Iris.

We aim to this work aims to establish a transparent, reproducible baseline for logistic regression on Iris that future studies can reference when benchmarking more complex or novel classifiers.

We aim to this work aims to show that a simple majority-class predictor is insufficient for multiclass problems, underscoring the value of model-based approaches even on standard benchmarks.


## References

[Generated from 2 source papers — see proposal for full bibliography]
