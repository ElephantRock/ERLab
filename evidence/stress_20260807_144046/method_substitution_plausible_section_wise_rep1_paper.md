# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Multiclass classification is a fundamental task in machine learning in which instances must be assigned to one of several mutually exclusive categories, and it arises across domains from biology to text categorization [SOURCE-1].

The Iris dataset, comprising four morphological measurements (sepal and petal length and width) across three iris species, serves as a widely studied benchmark for evaluating multiclass classification methods.

We propose logistic regression for multiclass classification of Iris species, using a multinomial softmax formulation that estimates class-membership probabilities from linear combinations of input features [SOURCE-1].

We aim to we expect logistic regression to substantially outperform a majority-class baseline ([RESULT-2] balanced_accuracy = 0.500) by achieving [RESULT-1] balanced_accuracy = 0.973 on the Iris dataset, demonstrating that a simple linear classifier can provide strong multiclass discrimination.

We aim to further validate discriminative quality through [RESULT-3] ROC-AUC = 0.998, confirming near-perfect class separability under the proposed logistic regression approach.


## Introduction

Multiclass classification—the assignment of input instances to one of three or more mutually exclusive categories—is among the most fundamental tasks in supervised machine learning, arising across domains from biology to document categorization [SOURCE-1].

The Iris dataset, comprising 150 samples across three Iris species described by four morphological features, has served as a canonical benchmark for multiclass classification for decades [SOURCE-1].

Linear classification methods, including logistic regression, are widely employed for multiclass problems owing to their interpretability, computational efficiency, and well-characterized statistical properties [SOURCE-1].

Logistic regression models class-conditional probabilities through a softmax of linear feature combinations, yielding decision boundaries that are linear in the original feature space [SOURCE-1].

Appropriate evaluation of multiclass classifiers requires metrics that account for per-class performance; balanced accuracy, which averages recall across all classes, is well-suited because it gives equal weight to each class regardless of its prevalence [SOURCE-2].

On a balanced three-class problem such as Iris, a majority-class predictor that always outputs the most frequent label achieves a balanced accuracy of only 0.500, establishing a trivial lower bound for meaningful classifiers [SOURCE-2].

Despite their prevalence, linear classifiers are inherently limited when class boundaries involve nonlinear structure or complex feature interactions, as their decision surfaces are restricted to linear forms in feature space [SOURCE-1].

Individual decision trees, although capable of modeling nonlinear boundaries, suffer from high variance: small perturbations in training data can yield substantially different tree structures and predictions [SOURCE-1].

This instability arises because each split in a decision tree is selected greedily from the training data, so a change in even a single example can propagate through the entire tree structure [SOURCE-1].

Ensemble methods that aggregate predictions from multiple base learners have been proposed as a principled strategy to reduce variance while preserving the flexibility of individual models [SOURCE-1].

Bootstrap aggregating (bagging) addresses the variance of unstable learners by training multiple models on different bootstrap resamples of the training data and averaging their predictions, under the rationale that the collective average is more stable than any single model [SOURCE-1].

Random forests extend bagging by introducing random feature subsampling at each split point, which further decorrelates individual trees and has been associated with improved generalization in prior classification studies [SOURCE-1].

The combination of bootstrap sampling and split-level feature randomness is analogous to variance-reduction techniques in other areas of statistics, where averaging over perturbed estimators is a well-established strategy for stabilizing noisy predictions [SOURCE-1] [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have been extensively surveyed as foundational techniques in supervised learning, prized for their interpretability and computational efficiency [SOURCE-1].

Logistic regression extends from binary to multiclass classification through multinomial formulations, enabling direct prediction across multiple class labels without requiring pairwise decomposition [SOURCE-1].

Despite their widespread adoption, linear classifiers such as logistic regression impose an assumption of linearly separable or approximately linear decision boundaries between classes, which may not adequately capture complex nonlinear relationships among features [SOURCE-1].

Smith (2020) notes that individual linear classifiers, while robust on small well-separated datasets, can be sensitive to feature scaling and multicollinearity, potentially degrading performance when these assumptions are violated [SOURCE-1].

The evaluation of multiclass classifiers requires specialized metrics that account for prediction errors across all classes simultaneously, as binary metrics do not directly generalize to the multiclass setting [SOURCE-2].

Balanced accuracy has been proposed as a multiclass evaluation metric that computes the arithmetic mean of per-class recall, thereby mitigating the bias introduced by class imbalance that affects standard accuracy [SOURCE-2].

Lee (2019) demonstrates that standard unweighted accuracy can yield misleadingly optimistic assessments when class distributions are skewed, as a classifier can achieve high accuracy by simply predicting the majority class [SOURCE-2].

ROC-AUC has been extended to the multiclass setting through one-vs-rest and one-vs-one averaging schemes, providing a threshold-independent measure of a classifier's ability to discriminate among classes [SOURCE-2].

Lee (2019) observes that balanced accuracy assigns equal importance to each class regardless of its frequency, which can penalize classifiers that perform well on frequent classes but poorly on rare ones, a tradeoff that must be considered when interpreting results [SOURCE-2].

Prior surveys indicate that linear methods remain competitive on low-dimensional, well-separated benchmark datasets such as Iris, where class boundaries are approximately linear [SOURCE-1].

However, surveys of linear classification note that such methods lack the capacity to model feature interactions automatically, requiring manual feature engineering to capture nonlinear dependencies [SOURCE-1].

Lee (2019) recommends reporting multiple complementary metrics, including both threshold-dependent measures like balanced accuracy and threshold-independent measures like ROC-AUC, to provide a holistic view of multiclass classifier performance [SOURCE-2].


## Proposed Method

Logistic regression is a well-established linear classification method that models class-conditional probabilities through parametric estimation [SOURCE-1].

We propose multinomial (softmax) logistic regression for three-class classification of Iris species.

The model computes class probabilities via the softmax function p(y=k|x) = exp(w_k^T x + b_k) / sum_j exp(w_j^T x + b_j), with parameters optimized by minimizing negative log-likelihood under an L2 regularization penalty using an L-BFGS solver.

We select logistic regression because the Iris dataset's four continuous features and three partially separable classes are well-suited to linear decision boundaries [SOURCE-1].

We favor logistic regression over more complex nonlinear models such as random forest ensembles for its interpretability and computational efficiency [SOURCE-1].

We hypothesize that this logistic regression approach may reduce overfitting risk on the small Iris dataset compared to more complex ensemble methods [SOURCE-1].

We adopt balanced accuracy as the primary evaluation metric because it computes the macro-average of per-class recall, which is appropriate for multiclass classification tasks [SOURCE-2].

We compare the proposed model against a majority-class baseline predictor that assigns every sample to the most frequent class.

We hypothesize that the logistic regression model will substantially outperform the majority-class baseline on balanced accuracy.

Our results show that logistic regression achieves [RESULT-1] balanced_accuracy = 0.973 on the Iris dataset.

The majority-class baseline achieves [RESULT-2] balanced_accuracy = 0.500.

The logistic regression model achieves [RESULT-3] ROC-AUC = 0.998 on the Iris dataset.

Proper evaluation of multiclass classifiers requires metrics that account for per-class performance and potential class imbalance [SOURCE-2].


## Evaluation Plan

We evaluate our classification approach on the Iris dataset [SOURCE-1], a widely used multiclass classification benchmark comprising 150 samples evenly distributed across three species—Iris setosa, Iris versicolor, and Iris virginica—each described by four morphological features (sepal length, sepal width, petal length, petal width).

The Iris dataset is well suited for evaluating linear classifiers because two of the three classes are linearly separable while the third exhibits moderate overlap, providing a nuanced testbed for assessing discriminative performance across varying levels of class separability [SOURCE-1].

Following established practice for multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary metric. Balanced accuracy computes the macro-average of per-class recall, ensuring that performance is not inflated by majority-class predictions and providing a fair assessment across all classes.

In addition to balanced accuracy, we report the area under the receiver operating characteristic curve (ROC-AUC) [SOURCE-2], computed as a one-versus-rest macro-average across the three classes. ROC-AUC provides a threshold-independent measure of discriminative power that complements balanced accuracy.

Our experimental protocol compares multinomial logistic regression with L2 regularization against a majority-class baseline on the Iris classification task. Both approaches use all four features and are evaluated using balanced accuracy and ROC-AUC on held-out data [SOURCE-1].

The design rationale for the majority-class baseline is to establish the floor of discriminative performance: any meaningful classifier must substantially exceed a balanced accuracy of 0.500, which is the expected score for a trivial predictor on the balanced three-class Iris problem. Logistic regression serves to characterize the degree of linear separability in the data.

We hypothesize that logistic regression will achieve high balanced accuracy on Iris, substantially exceeding the majority-class baseline, due to the near-linear separability of the dataset's class structure [SOURCE-1].

Our results show that logistic regression achieves [RESULT-1] balanced_accuracy = 0.973, substantially outperforming the majority-class baseline.

The majority-class baseline achieves [RESULT-2] balanced_accuracy = 0.500, confirming the expected performance floor for a trivial predictor on this balanced three-class task.

The logistic regression model also achieves [RESULT-3] ROC-AUC = 0.998, indicating near-perfect class separability and ranking ability across decision thresholds.

We hypothesize that the slight departure from perfect balanced accuracy (0.973 rather than 1.0) is attributable to the well-documented overlap between Iris versicolor and Iris virginica in the feature space, while Iris setosa is classified without error due to its linear separability from the other two classes [SOURCE-1].

We hypothesize that a random forest ensemble, as proposed in the broader work, would match or exceed the logistic regression balanced accuracy by capturing nonlinear decision boundaries in the versicolor–virginica overlap region, though the margin on Iris may be modest given the already strong linear baseline [SOURCE-2].


## Discussion and Future Work

Logistic regression is a well-established linear classification method that performs effectively when classes are approximately linearly separable in the feature space [SOURCE-1].

Our logistic regression model achieved a balanced accuracy of 0.973 on the Iris dataset [RESULT-1], a substantial improvement over the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

The ROC-AUC of 0.998 [RESULT-3] further confirms strong discriminative ability of the logistic regression model across all three Iris species.

The Iris dataset, comprising four sepal and petal measurements across three species, represents a favorable scenario for linear approaches because the species are largely separable by these features [SOURCE-2].

We hypothesize that incorporating L1 or L2 regularization into the logistic regression model may improve robustness when applied to higher-dimensional datasets or those with intercorrelated features [SOURCE-1].

We hypothesize that polynomial or interaction feature expansions could enable logistic regression to capture nonlinear class boundaries that a purely linear model cannot, potentially extending applicability to datasets where classes are not linearly separable.

We hypothesize that the performance advantage of logistic regression over more complex models such as random forests or neural networks may narrow or reverse on datasets exhibiting greater nonlinear structure or higher noise levels.

We aim to extending this evaluation framework to additional multiclass benchmarks—including datasets with higher dimensionality, class imbalance, or label noise—would provide broader evidence regarding the conditions under which logistic regression remains competitive with more complex approaches [SOURCE-2].

We aim to systematic comparison between logistic regression and ensemble methods would help delineate the trade-off between model interpretability and predictive performance across diverse classification scenarios.


## Conclusion

Logistic regression classified the Iris dataset with a balanced accuracy of 0.973, substantially exceeding the majority-class baseline's balanced accuracy of 0.500 [RESULT-1][RESULT-2] [SOURCE-1].

The model attained an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect separability among the three Iris species under the logistic regression formulation [SOURCE-2].

These results are consistent with prior literature showing that linear classifiers perform strongly on the Iris dataset, where class boundaries are approximately linearly separable [SOURCE-1].

We aim to this work aims to establish a logistic regression baseline with rigorous balanced-accuracy and ROC-AUC reporting on Iris, against which future ensemble approaches such as random forests can be meaningfully compared.

We aim to this work aims to demonstrate that standard multiclass evaluation metrics, particularly balanced accuracy, can reveal the near-ceiling performance of simple linear models on well-structured datasets like Iris [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
