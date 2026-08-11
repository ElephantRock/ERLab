# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression is a well-established linear classification method widely applied to multiclass problems such as species identification [SOURCE-1].

Balanced accuracy is a robust evaluation metric for multiclass classification, particularly when class distributions may be uneven [SOURCE-2].

We apply multinomial logistic regression to the Iris dataset and compare against a majority-class baseline, using balanced accuracy as the primary metric.

We aim to logistic regression will substantially outperform the majority-class baseline on balanced accuracy, demonstrating the effectiveness of linear models on this foundational benchmark.


## Introduction

Multiclass classification—the task of assigning input instances to one of several discrete categories—constitutes one of the most fundamental problems in machine learning and pattern recognition [SOURCE-1].

The Iris dataset, comprising 150 flower samples evenly distributed across three species (Iris setosa, Iris versicolor, and Iris virginica) with four morphological features each, has served as a canonical benchmark for classification algorithms since its introduction by Fisher in 1936 [SOURCE-1].

Logistic regression is among the most widely studied and deployed methods for linear classification, modeling class-conditional probabilities through a parametric linear function of input features [SOURCE-1].

The extension of logistic regression to multiclass settings is accomplished through the softmax (multinomial logistic) formulation, which produces a normalized probability distribution over all classes, yielding a convex optimization problem with globally optimal solutions [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a summary metric for classification evaluation because it weights each class equally regardless of its prevalence [SOURCE-2].

Majority-class prediction provides a necessary lower-bound baseline but fails to exploit any feature-based structure in the data; on a balanced three-class problem such as Iris, it achieves a balanced accuracy of only one-third [SOURCE-1].

Standard accuracy can be a misleading evaluation measure for multiclass problems, as it may mask poor per-class performance when classes are unequally represented or when certain error types are disproportionately costly [SOURCE-2].

Prior work on multiclass evaluation has shown that balanced accuracy provides a more informative summary of classifier behavior than raw accuracy alone, particularly when comparing models across datasets with varying class compositions [SOURCE-2].

The choice of multinomial logistic regression for Iris classification is motivated by its documented effectiveness on low-dimensional, numerically structured feature spaces where class boundaries are approximately linear [SOURCE-1].

Benchmarking logistic regression against a majority-class predictor allows direct quantification of the discriminative information captured by the linear model relative to a trivial baseline, following established practice in the linear classification literature [SOURCE-1].

The adoption of balanced accuracy as the primary evaluation metric follows directly from recommendations in the multiclass evaluation literature, ensuring that classification performance is assessed equitably for each Iris species [SOURCE-2].

Reporting ROC-AUC as a supplementary metric is motivated by its ability to characterize the ranking quality of the classifier's probability estimates, complementing the threshold-dependent balanced accuracy [SOURCE-2].


## Related Work

Linear classification methods have been extensively studied in machine learning, with logistic regression remaining one of the most widely used approaches for both binary and multiclass problems [SOURCE-1].

Logistic regression models the posterior probability of class membership using a linear combination of features, making it particularly suitable for datasets where classes are approximately linearly separable [SOURCE-1].

The Iris dataset has served as a standard benchmark for evaluating classification algorithms since the early days of statistical learning, due to its manageable size and well-characterized feature distributions [SOURCE-1].

Multiclass classification problems require careful selection of evaluation metrics, as standard accuracy can mask poor performance on individual classes, particularly when class distributions are imbalanced [SOURCE-2].

Balanced accuracy, defined as the average of per-class recall scores, provides a more informative assessment of classifier performance than raw accuracy, especially in settings where the majority-class baseline achieves deceptively high scores [SOURCE-2].

The softmax (multinomial) extension of logistic regression is the standard generalization for handling multiclass problems natively, rather than relying on pairwise decomposition strategies [SOURCE-1].

Despite its simplicity, logistic regression often achieves competitive performance on low-dimensional, structured datasets compared to more complex nonlinear methods [SOURCE-1].

Majority-class predictors, which always predict the most frequent class, serve as a minimal baseline for classification tasks but fail to exploit any feature information, yielding a balanced accuracy of 0.5 on balanced multiclass problems [SOURCE-2].

A key limitation of standard accuracy as an evaluation metric is that it can be dominated by majority-class performance, leading to inflated estimates of classifier quality on imbalanced datasets [SOURCE-2].

Linear classifiers such as logistic regression can struggle with datasets where class boundaries are inherently nonlinear, requiring kernel methods or feature engineering to achieve adequate separation [SOURCE-1].

ROC-AUC has been established as a useful complementary metric for evaluating ranking quality of probabilistic classifiers, though it was originally designed for binary settings and requires extensions for multiclass problems [SOURCE-2].

Existing surveys of linear classification note that logistic regression's lack of explicit regularization in its basic form can lead to overfitting on high-dimensional data, though this concern is diminished on low-dimensional benchmarks like Iris [SOURCE-1].

Evaluation metrics that do not account for per-class performance have been shown to produce misleading conclusions in multiclass settings, where some classes may be systematically misclassified while overall scores remain acceptable [SOURCE-2].

Simple baselines such as majority-class predictors are frequently omitted or reported inconsistently in prior classification studies, making it difficult to contextualize the practical significance of reported accuracy figures [SOURCE-2].

The interpretation of logistic regression coefficients as indicators of feature importance is well established, but the reliability of such interpretations depends on the absence of strong multicollinearity among input features [SOURCE-1].

Comparative studies have shown that while nonlinear methods such as support vector machines and random forests can achieve higher accuracy on some datasets, the performance gap is often negligible on benchmarks with clear linear separability [SOURCE-1].

A persistent gap in many benchmark evaluations is the failure to report multiple complementary metrics, which can obscure trade-offs between per-class sensitivity and overall classification quality [SOURCE-2].


## Proposed Method

Logistic regression is a well-established linear classification method that has been extensively studied for structured, low-dimensional datasets such as Iris [SOURCE-1].

Balanced accuracy has been recommended as a multiclass evaluation metric that mitigates class imbalance bias by computing the arithmetic mean of per-class recall [SOURCE-2].

We adopt logistic regression as our primary classifier because the Iris dataset's four morphological features—sepal length, sepal width, petal length, and petal width—exhibit approximately linear class boundaries, making a linear model particularly appropriate for this task [SOURCE-1].

We formulate the Iris classification task as a multinomial logistic regression problem, using the softmax function to compute posterior probabilities across the three Iris species (Iris setosa, Iris versicolor, and Iris virginica).

The model is trained via maximum likelihood estimation with L2 regularization to control model complexity.

We hypothesize that l2 regularization will mitigate overfitting given the Iris dataset's modest sample size of 150 instances.

We standardize all four input features to zero mean and unit variance prior to model fitting.

Feature standardization is motivated by the sensitivity of gradient-based optimization to feature scale, a consideration emphasized in prior work on linear classification [SOURCE-1].

We select balanced accuracy as our primary evaluation metric to ensure that performance is measured fairly across all three classes [SOURCE-2].

We establish a majority-class predictor as our baseline, which assigns every test instance to the most frequently observed class in the training data.

We hypothesize that we anticipate that the multinomial logistic regression model will substantially outperform this majority-class baseline on balanced accuracy.

We partition the Iris dataset into training and testing subsets using stratified sampling to preserve class proportions across the split.

We additionally report ROC-AUC as a secondary metric to characterize the model's discriminative ability across all three classes.

We hypothesize that we expect the logistic regression model to achieve high ROC-AUC, reflecting strong class separation.


## Evaluation Plan

We evaluate our logistic regression classifier on the Iris dataset [SOURCE-1], a widely studied multiclass classification benchmark comprising 150 samples distributed equally across three species.

Our primary evaluation metric is balanced accuracy, defined as the macro-averaged recall across all classes. Following Lee (2019) [SOURCE-2], we select this metric because it weights each class equally, preventing any single class from dominating the aggregate score.

We report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to characterize the quality of the model's probabilistic rankings across decision thresholds.

We compare logistic regression against a majority-class predictor, which assigns every test sample to the class most frequently observed in the training set. This baseline establishes a lower bound on useful performance — a model that fails to exceed it provides no practical value.

The dataset is partitioned into training and test subsets. We fit a multinomial logistic regression model using softmax activation and cross-entropy loss on the training partition. Features are standardized to zero mean and unit variance prior to model fitting [SOURCE-1].

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, because the Iris feature space contains strong linear signal [SOURCE-1].

We hypothesize that we further hypothesize that the ROC-AUC will be close to 1.0, reflecting high-quality probability rankings across all three classes.

Logistic regression achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973, while the majority-class baseline achieves [RESULT-2] balanced_accuracy = 0.500.

The model attains a ROC-AUC of [RESULT-3] ROC-AUC = 0.998.

We hypothesize that we attribute the small residual error — approximately 2.7 percentage points below perfect balanced accuracy — to the region of overlap between Iris versicolor and Iris virginica, where even an optimal linear boundary necessarily misclassifies some borderline samples [SOURCE-1] [RESULT-1].


## Discussion and Future Work

Linear models such as logistic regression have long served as standard baselines for multiclass classification benchmarks, including the Iris dataset, due to their interpretability and computational efficiency [SOURCE-1].

Balanced accuracy is a particularly informative metric for multiclass settings because it averages per-class recall and therefore penalizes classifiers that overpredict a single majority class [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the Iris dataset, while the majority-class baseline yields only [RESULT-2] balanced_accuracy = 0.500 [SOURCE-1].

The near-perfect ROC-AUC of [RESULT-3] ROC-AUC = 0.998 further indicates that the logistic decision boundaries produce high-confidence probability rankings across all three classes [SOURCE-2].

We hypothesize that the two principal Iris species are near-linearly separable in petal-length and petal-width feature space, and that the residual error arises primarily from overlap between Iris versicolor and Iris virginica [SOURCE-1].

We hypothesize that we further hypothesize that replacing the softmax logistic regression with a kernel-based classifier would reduce the remaining misclassification rate, with diminishing returns once the versicolor–virginica overlap region is accounted for [SOURCE-1].

We hypothesize that logistic regression will retain a measurable advantage over the majority-class baseline under leave-one-out cross-validation, suggesting the observed performance is not an artifact of the particular train–test split.

We aim to this study contributes a reproducible, metric-grounded benchmark linking balanced accuracy and ROC-AUC for a linear baseline on Iris, clarifying where linear models succeed and where nonlinear alternatives may be warranted [SOURCE-1] [SOURCE-2].

We aim to extending this evaluation protocol to datasets with greater class imbalance and higher feature dimensionality will reveal regimes where the balanced-accuracy gap between logistic regression and majority-class baselines narrows [SOURCE-2].


## Conclusion

Logistic regression is a well-established linear classification method widely used for multiclass problems in machine learning [SOURCE-1].

Balanced accuracy is an appropriate evaluation metric for multiclass classification tasks because it accounts for class imbalance by averaging per-class recall [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the Iris dataset, substantially exceeding the majority-class baseline's [RESULT-2] balanced_accuracy = 0.500.

The ROC-AUC of [RESULT-3] ROC-AUC = 0.998 further indicates strong discriminative performance across classes.

We aim to this work aims to provide a clear, reproducible benchmark of logistic regression on a standard dataset, demonstrating that even a simple linear model can achieve near-perfect balanced accuracy on Iris [RESULT-1] [RESULT-2].

We aim to this work aims to motivate future evaluation of logistic regression on more complex, higher-dimensional datasets to assess the boundaries of linear separability assumptions [SOURCE-1].


## References

[Generated from 2 source papers — see proposal for full bibliography]
