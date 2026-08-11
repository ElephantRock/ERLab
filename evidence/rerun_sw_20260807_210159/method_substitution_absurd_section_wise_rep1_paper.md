# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression is a well-established linear classification method widely used for multiclass problems such as species classification on the Iris dataset [SOURCE-1].

Balanced accuracy and ROC-AUC are standard metrics for evaluating classification performance, particularly when comparing against trivial baselines across potentially imbalanced class distributions [SOURCE-2].

We train a logistic regression classifier on the Iris dataset and benchmark it against a majority-class baseline, using balanced accuracy as the primary metric and ROC-AUC as a secondary measure.

We aim to we expect logistic regression to substantially outperform the majority-class baseline on balanced accuracy, demonstrating that even a simple linear discriminative model captures the class structure of the Iris dataset.


## Introduction

Linear classification methods have long served as foundational tools in machine learning, prized for their interpretability, computational efficiency, and well-characterized theoretical properties [SOURCE-1].

Logistic regression, through softmax generalization, extends naturally to multiclass settings and provides calibrated probability estimates useful for both decision-making and downstream probabilistic reasoning [SOURCE-1].

The Iris dataset, originally introduced by Fisher, remains one of the most widely recognized benchmark problems for evaluating classification algorithms owing to its clean four-dimensional feature space and three well-separated species classes [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more informative evaluation metric than raw accuracy for multiclass problems because it equally weights performance on each class regardless of its prevalence [SOURCE-2].

Surveys of linear classification methods observe that many published studies report only raw accuracy and frequently omit comparisons against trivial baselines such as the majority-class predictor, making it impossible to determine whether observed accuracy reflects genuine feature-based discrimination or merely exploitation of class proportions [SOURCE-1].

The literature on multiclass evaluation metrics notes that the absence of balanced reporting is particularly acute in older studies, where high raw accuracy was sometimes treated as prima facie evidence of model utility without interrogating whether all classes were being learned equally [SOURCE-2].

The simplicity and transparent geometric interpretation of logistic regression as a linear decision boundary make it an ideal vehicle for assessing how much discriminative power is achievable on Iris from a linear feature space alone, without confounding from opaque nonlinear interactions [SOURCE-1].

Benchmarking against a majority-class predictor mirrors established evaluation practices in which the value of a model is measured relative to the floor set by trivial strategies, providing a clear and interpretable reference point for assessing practical contribution [SOURCE-1].

Selecting balanced accuracy as the primary metric follows recommended best practices for multiclass evaluation, ensuring that the comparison is sensitive to per-class performance and is not dominated by any single class [SOURCE-2].


## Related Work

Logistic regression has long been established as one of the most widely used linear classification methods, offering a principled probabilistic framework grounded in maximum likelihood estimation [SOURCE-1].

Surveys of linear classification methods consistently identify logistic regression alongside linear discriminant analysis and support vector machines as the canonical family of linear discriminative approaches for structured tabular data [SOURCE-1].

The extension of binary logistic regression to multiclass settings, typically through the softmax or one-vs-rest formulation, has been shown to be effective on standard multiclass benchmarks including the Iris dataset [SOURCE-1].

Despite its simplicity, logistic regression can underperform when the decision boundaries between classes are highly nonlinear, as it is fundamentally constrained to learning linear separators in the feature space [SOURCE-1].

Prior work has noted that linear models, including logistic regression, may struggle to fully separate classes in datasets where feature distributions exhibit partial overlap across class boundaries, which can limit achievable accuracy [SOURCE-1].

Evaluation of multiclass classifiers requires metrics that account for class imbalance and per-class performance, as single scalar measures such as raw accuracy can obscure poor performance on minority classes [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more informative metric than standard accuracy for evaluating classifiers on datasets with potential or actual class imbalance [SOURCE-2].

Standard accuracy has been shown to be a misleading metric when one class dominates, as a trivial majority-class predictor can achieve deceptively high accuracy while providing no discriminative power [SOURCE-2].

The ROC-AUC metric, originally developed for binary classification, has been extended to multiclass settings through averaging strategies such as one-vs-rest macro-averaging, providing a threshold-independent measure of discriminative ability [SOURCE-2].

Prior analyses have demonstrated that even simple majority-class baselines can yield non-trivial scores under raw accuracy on imbalanced or skewed datasets, underscoring the need for balanced metrics and explicit baseline comparisons [SOURCE-2].

Comprehensive surveys of linear classification methods have shown that logistic regression remains competitive with more complex nonlinear methods on low-dimensional, well-separated datasets, making it a strong baseline for benchmarking purposes [SOURCE-1].

The choice of evaluation protocol, including whether to report per-class metrics or aggregate summaries, significantly affects the perceived quality of a classifier, and prior work has recommended reporting both for completeness [SOURCE-2].

A limitation identified in prior evaluations of linear classifiers is that reported accuracies on balanced multiclass datasets, where classes are equally represented, may not reflect robustness when the model is deployed on skewed data distributions [SOURCE-1].

Research on multiclass evaluation metrics has further established that balanced accuracy penalizes classifiers that perform well only on the majority class, making it particularly suitable for distinguishing meaningful classifiers from trivial baselines [SOURCE-2].

Linear classification surveys have documented that the Iris dataset, due to its modest size and relatively clean feature structure, has served as a standard testbed for decades of methodological development in discriminative modeling [SOURCE-1].


## Proposed Method

Logistic regression is a well-established linear classification method that has been widely applied to discriminative learning tasks across diverse domains [SOURCE-1].

Balanced accuracy, defined as the macro-average of per-class recall, mitigates class imbalance bias and has been recommended for multiclass evaluation [SOURCE-2].

We select multinomial logistic regression because linear models have been shown effective on low-dimensional, well-separated classification benchmarks [SOURCE-1].

We employ multinomial (softmax) logistic regression with L2 regularization as our primary classifier.

We standardize all input features to zero mean and unit variance prior to model fitting.

We use the L-BFGS optimizer for parameter estimation with a maximum of 1000 iterations and an inverse regularization strength of C=1.0.

We implement a majority-class predictor that always predicts the most frequent class in the training set as a trivial baseline comparator.

We hypothesize that logistic regression may achieve substantially higher balanced accuracy than the majority-class baseline.

We hypothesize that we expect the model to achieve high discriminative performance as measured by ROC-AUC, given the near-linear separability of Iris species.

We adopt balanced accuracy as the primary evaluation metric for comparing the logistic regression model against the majority-class baseline [SOURCE-2].

We additionally report ROC-AUC to assess the model's ranking discrimination across classes [SOURCE-2].

We evaluate both the proposed logistic regression model and the majority-class baseline on the Iris dataset using identical train-test splits to ensure fair comparison.


## Evaluation Plan

We use the Iris dataset [SOURCE-1], a well-established multiclass classification benchmark comprising 150 samples across three flower species (Setosa, Versicolor, and Virginica), each described by four morphological features.

Following [SOURCE-2], we adopt balanced accuracy as our primary evaluation metric, which computes the macro-averaged recall across all classes and is robust to class imbalance—an important property when comparing against a majority-class baseline that trivially exploits class frequency.

We additionally report ROC-AUC [SOURCE-2] to characterize the discriminative capability of the logistic regression model across varying decision thresholds, providing a threshold-independent complement to balanced accuracy.

We compare logistic regression against a majority-class baseline predictor, which assigns every test sample to the single most frequent class in the training set, thereby establishing a trivial lower-bound reference that any meaningful classifier must exceed.

The design rationale for selecting a majority-class baseline is that it provides the most conservative non-trivial comparator; on the balanced three-class Iris problem, this baseline yields a balanced accuracy of 0.500, since it correctly classifies only one of the three classes while achieving zero recall on the remaining two.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that the Iris dataset is known to exhibit high linear separability between at least two of the three species [SOURCE-1].

We hypothesize that we further hypothesize that the ROC-AUC of logistic regression on Iris will approach the upper bound of 1.0, reflecting the model's ability to produce well-calibrated probability estimates that rank-order instances correctly across classes [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], while the majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], confirming that the logistic model substantially exceeds the trivial lower bound.

The logistic regression model attains an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class discrimination on the Iris dataset and supporting our hypothesis regarding threshold-independent ranking quality.

The margin between the logistic regression balanced accuracy (0.973) and the baseline (0.500) corresponds to a near-doubling of classification performance, demonstrating the value of the learned linear decision boundaries over trivial prediction [RESULT-1] [RESULT-2].


## Discussion and Future Work

Logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, substantially exceeding the majority-class baseline balanced accuracy of 0.500 [RESULT-2] [SOURCE-1].

The ROC-AUC of 0.998 [RESULT-3] corroborates the strong discriminative capacity of the model, indicating well-calibrated predicted class probabilities [SOURCE-2].

Linear classifiers such as logistic regression are known to be competitive on low-dimensional, well-separated datasets, and Iris exemplifies such a regime [SOURCE-1].

Balanced accuracy ensures reported performance is not inflated by class imbalance, and the 0.500 baseline provides a meaningful floor reflecting genuine learned structure [SOURCE-2].

We hypothesize that L2 regularization would preserve or modestly improve balanced accuracy on Iris-like datasets while reducing variance under smaller training splits [SOURCE-1].

We hypothesize that logistic regression's advantage over the majority-class baseline would diminish on datasets with inherently nonlinear class boundaries, where kernel or neural methods may be required [SOURCE-1].

We hypothesize that the near-ceiling ROC-AUC of 0.998 [RESULT-3] would decrease substantially under feature perturbation or label noise, and quantifying this degradation would yield a useful sensitivity analysis [SOURCE-2].

We aim to a systematic benchmarking study comparing logistic regression against regularized variants and nonlinear baselines across multiple standard datasets would yield a practical decision guide for classifier selection based on dataset properties [SOURCE-1] [SOURCE-2].


## Conclusion

Our results show that logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset, compared to 0.500 for the majority-class baseline [RESULT-1][RESULT-2].

The ROC-AUC of 0.998 further indicates near-perfect class separability under the logistic regression model [RESULT-3].

The near-doubling of balanced accuracy over the majority-class predictor underscores the value of discriminative linear models even on a dataset as small and structured as Iris [RESULT-1][RESULT-2] [SOURCE-1].

We aim to this work aims to establish logistic regression as a strong, reproducible reference baseline for multiclass flower classification benchmarks.

We aim to this work aims to motivate further investigation into the boundary between linearly separable and more complex biological classification tasks, where linear models may or may not suffice [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
