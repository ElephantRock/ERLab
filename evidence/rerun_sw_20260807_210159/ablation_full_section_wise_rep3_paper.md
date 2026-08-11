# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Classification of botanical specimens remains a foundational benchmark in machine learning, with the Iris dataset serving as a widely used test case for evaluating discriminative classification methods [SOURCE-1].

We apply multinomial logistic regression as a discriminative classifier to the Iris dataset, formulating a three-class problem and evaluating against a majority-class baseline using balanced accuracy as the primary metric [SOURCE-1] [SOURCE-2].

We aim to logistic regression will substantially outperform the majority-class baseline, demonstrating strong classification performance on the Iris dataset.


## Introduction

The classification of Iris flower species from sepal and petal measurements, first introduced as a discriminant analysis problem by Fisher in 1936, remains one of the most enduring and widely studied benchmark tasks in machine learning. Its longevity as a reference dataset stems from several advantageous properties: a moderate number of well-defined continuous features, three species classes with known biological relationships, and a well-characterized pattern of class separability in which one species is linearly separable from the other two while the remaining two exhibit partial overlap. These properties make Iris an ideal setting for evaluating the discriminative capacity of classification algorithms, particularly those that construct linear decision boundaries [SOURCE-1].

Linear classification methods, which partition the feature space using decision boundaries defined as linear combinations of input features, represent a foundational and deeply studied family of approaches within supervised learning. Comprehensive surveys of classification methodology consistently highlight the centrality of linear models, noting their favorable trade-off between expressive power and computational tractability, as well as the theoretical guarantees that accompany their well-understood optimization landscapes [SOURCE-1].

Logistic regression, perhaps the most prominent member of the generalized linear model family for classification, models the conditional probability of class membership using the logistic function applied to a linear combination of features. The method's enduring popularity arises from several key properties: a convex objective function that guarantees convergence to a global optimum, naturally calibrated probabilistic outputs that facilitate threshold adjustment and uncertainty quantification, and a straightforward extension to the multiclass setting via the multinomial softmax formulation [SOURCE-1].

The evaluation of classification systems in multiclass settings requires metrics that faithfully capture performance across all classes simultaneously. The selection of an evaluation metric is not merely a reporting detail but a substantive methodological choice that directly shapes conclusions about classifier quality, model comparability, and the reliability of generalization claims [SOURCE-2].

Balanced accuracy, computed as the arithmetic mean of per-class recall, addresses the need for a per-class-sensitive evaluation metric by assigning equal importance to each class irrespective of its frequency in the dataset. This property makes balanced accuracy particularly appropriate for benchmark datasets such as Iris where class distributions are approximately uniform and where the scientific interest lies in overall discriminative capability rather than performance weighted by class prevalence [SOURCE-2].

The majority-class predictor, which assigns every test instance to the most frequent class label observed in the training data, constitutes the simplest possible classification baseline. While this approach requires no feature information and incurs negligible computational cost, it is entirely uninformative about the discriminative structure of the data. On balanced multiclass problems such as Iris, the majority-class predictor achieves a balanced accuracy of merely 1/K, reflecting its complete inability to differentiate among classes and underscoring its role solely as a performance floor rather than a competitive classification strategy [SOURCE-1].

Unweighted classification accuracy, despite its widespread use and intuitive appeal, suffers from a critical limitation in multiclass settings: it can produce deceptively favorable scores when class distributions are skewed, as a classifier achieving high accuracy on the majority class may simultaneously exhibit near-zero recall on minority classes. This metric blindness to per-class performance can lead to the adoption of classifiers that fail on entire classes—a failure mode that is particularly problematic in scientific applications where each class carries independent significance, such as species identification in botany [SOURCE-2].

The selection of logistic regression as the primary classification method is motivated by its well-documented suitability for problems involving continuous features and moderate class counts. The method's convex optimization landscape eliminates concerns about local optima during parameter estimation, and its natural extension to multiclass prediction via the softmax function makes it an ideal reference classifier for benchmark evaluation on the Iris dataset. This methodological choice is consistent with the established practice of employing logistic regression as a baseline discriminative model in classification research, where its transparent decision mechanism facilitates direct comparison against both simpler baselines and more complex nonlinear alternatives [SOURCE-1].

The partial linear separability structure of the Iris dataset—wherein one species is cleanly separable from the other two, but two species share a region of feature-space overlap—provides a particularly informative test for logistic regression, as it directly probes whether a linear decision boundary can adequately capture the discriminative structure that exists in the morphological features. Comparing against a majority-class baseline further contextualizes this evaluation by establishing the performance floor below which a classifier provides no practical utility over naive guessing, following established benchmark comparison protocols in linear classification research [SOURCE-1].

The adoption of balanced accuracy as the primary evaluation metric is motivated by the need for a per-class-sensitive criterion that captures the uniform-class-distribution structure of the Iris dataset and penalizes classifiers that neglect individual species. This choice follows established best practices for multiclass evaluation that emphasize equitable treatment of all classes regardless of their prevalence, ensuring that observed performance differences between logistic regression and the majority-class baseline reflect genuine discriminative capability rather than artifacts of metric insensitivity [SOURCE-2].


## Related Work

Logistic regression remains one of the most widely studied and deployed linear classification methods, with extensive literature documenting its theoretical properties and empirical success across diverse domains [SOURCE-1].

Linear classifiers, including logistic regression, are particularly attractive for problems with moderate dimensionality and separable class structure, as they offer interpretable decision boundaries and efficient training procedures [SOURCE-1].

Smith (2020) surveys a broad family of linear classification methods, including logistic regression, linear discriminant analysis, and support vector machines with linear kernels, noting that these approaches share the fundamental assumption that class boundaries can be well-approximated by hyperplanes in feature space [SOURCE-1].

Despite the proliferation of more complex nonlinear classifiers, logistic regression continues to serve as a strong and competitive baseline on low-dimensional benchmark datasets, where nonlinear models often offer marginal improvements at the cost of interpretability [SOURCE-1].

A known limitation of standard logistic regression is its original formulation as a binary classifier, requiring extensions such as the one-vs-rest or multinomial (softmax) strategies to handle multiclass problems, which introduces additional complexity in both training and evaluation [SOURCE-1].

The Iris dataset, introduced by Fisher, has become the canonical benchmark for evaluating multiclass classification methods, and linear classifiers such as logistic regression have been reported to achieve near-perfect accuracy on it, making it a standard testbed rather than an open challenge [SOURCE-1].

Evaluation of multiclass classifiers requires metrics that account for class imbalance and per-class performance, and Lee (2019) provides a comprehensive analysis of multiclass evaluation metrics including balanced accuracy, macro-averaged F1, and confusion-matrix-based measures [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of sensitivity (true positive rate) for each class, is specifically recommended for classification tasks where class distributions may be skewed, as standard accuracy can be misleadingly high when one class dominates [SOURCE-2].

Lee (2019) demonstrates that naive accuracy can obscure poor per-class performance, particularly in multiclass settings, where a majority-class predictor can achieve deceptively high accuracy while completely failing to identify minority classes [SOURCE-2].

The majority-class predictor, which assigns all instances to the most frequent class, serves as the simplest possible baseline classifier and provides a lower bound on acceptable performance; on balanced datasets like Iris it achieves approximately 33% accuracy across three classes, but balanced accuracy correctly reveals this as inadequate [SOURCE-2].

While the Iris dataset is balanced across its three classes, many real-world multiclass problems are not, and the use of balanced accuracy as a metric ensures that evaluation is robust regardless of class distribution, a property that standard accuracy lacks [SOURCE-2].

A limitation of existing surveys on linear classification is that they frequently report only raw accuracy on benchmark datasets without contrasting against majority-class baselines using class-balanced metrics, making it difficult to assess the practical improvement offered by methods like logistic regression over trivial predictors [SOURCE-1].

Smith (2020) notes that the softmax extension of logistic regression for multiclass problems can suffer from instability when classes are highly overlapping or when features are strongly collinear, although these issues are generally not severe on well-separated benchmarks like Iris [SOURCE-1].

Lee (2019) further observes that the choice of evaluation metric can significantly affect the apparent ranking of classifiers, with balanced accuracy being among the most discriminative metrics for distinguishing meaningful classifiers from trivial baselines in multiclass settings [SOURCE-2].

Prior work on linear classification methods has established that logistic regression benefits from regularization (L1 or L2) to prevent overfitting, particularly when the number of features approaches the number of training samples, though on compact datasets like Iris with only four features, overfitting is rarely a concern [SOURCE-1].


## Proposed Method

Logistic regression has been established as a foundational discriminative classification method in machine learning, valued for its convex loss surface, interpretable linear decision boundaries, principled probabilistic output via the softmax function, and well-understood generalization properties under L2 regularization [SOURCE-1].

Balanced accuracy—defined as the arithmetic mean of per-class recall—has been recommended for evaluating multiclass classifiers because it equally weights each class regardless of its frequency, providing a more informative assessment than unweighted accuracy when per-class performance differences are of scientific interest [SOURCE-2].

The Iris dataset, introduced by Anderson and popularized by Fisher, comprises 150 instances evenly distributed across three species— Iris setosa, Iris versicolor, and Iris virginica—with 50 instances per species, each described by four continuous morphological features: sepal length, sepal width, petal length, and petal width, all measured in centimeters [SOURCE-1].

We select multinomial logistic regression as our primary classifier because prior work has demonstrated that the Iris dataset's morphological measurements exhibit strong linear separability, particularly between Iris setosa and the remaining two species, rendering a linear decision boundary both sufficient and preferable to more complex nonlinear models on grounds of parsimony, interpretability, and generalization [SOURCE-1].

We formulate the Iris species classification task as multinomial logistic regression: for an input feature vector x ∈ R⁴, the model computes the posterior probability of each class k ∈ {setosa, versicolor, virginica} as p(y = k | x) = exp(w_k^⊤ x + b_k) / Σ_{j=1}^{3} exp(w_j^⊤ x + b_j), where w_k ∈ R⁴ is the class-specific weight vector and b_k ∈ R is the class-specific bias term.

The model is trained on all four continuous input features provided by the Iris dataset: sepal length, sepal width, petal length, and petal width.

Prior to model fitting, each feature is independently standardized to zero mean and unit variance using the mean and standard deviation computed exclusively from the training partition, and these same statistics are subsequently applied to the test partition to prevent information leakage.

Model parameters are estimated by minimizing the L2-regularized multinomial cross-entropy loss using the limited-memory BFGS (L-BFGS) quasi-Newton optimization algorithm, with a regularization strength hyperparameter C = 1.0 and a maximum of 100 iterations allowed for convergence.

As a baseline comparator, we implement a majority-class predictor that assigns every test instance to the most frequently occurring class label in the training set, requiring no feature information and representing the weakest non-trivial classification strategy.

We adopt balanced accuracy as the primary evaluation metric because it computes the arithmetic mean of per-class recall, thereby giving equal weight to each of the three Iris species regardless of their representation in any particular train-test partition [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to characterize the model's class-discrimination quality across all possible decision thresholds [SOURCE-2].

We hypothesize that multinomial logistic regression will substantially outperform the majority-class baseline on balanced accuracy, consistent with the well-documented linear separability of Iris morphological features.

We hypothesize that l2 regularization with C = 1.0 will mitigate overfitting, given that the model has 15 free parameters (12 weights and 3 biases) relative to the limited sample size of 150 instances.

We hypothesize that we anticipate that feature standardization will prevent features with larger numerical ranges from dominating the learned weight magnitudes, promoting balanced contributions from all four morphological measurements to the final decision boundary.

We hypothesize that the majority-class baseline will achieve a balanced accuracy near 1/3, reflecting its inability to discriminate between the three equally represented Iris species.


## Evaluation Plan

We use the Iris dataset [SOURCE-1] as our primary evaluation benchmark, comprising 150 samples evenly distributed across three species described by four continuous morphological features.

Following [SOURCE-2], we measure balanced accuracy as our primary metric, defined as the arithmetic mean of per-class recall, to ensure robust evaluation across all three Iris species.

We additionally report ROC-AUC, computed via one-versus-rest averaging, to characterize the discriminative quality of predicted class probabilities beyond a fixed decision threshold [SOURCE-2].

Our experimental design compares a multinomial logistic regression classifier with L2 regularization against a majority-class baseline that assigns every instance to the most frequent training class [SOURCE-1].

The design rationale is that logistic regression produces a well-characterized linear decision boundary suitable for the largely separable structure of Iris features [SOURCE-1], while the majority-class baseline isolates the contribution of the learned discriminative model.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given the well-documented separability of Iris features across the three species [SOURCE-1].

We hypothesize that the four morphological features provide sufficient discriminative information for logistic regression to achieve high ROC-AUC, reflecting near-perfect class separability under the linear decision boundary [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of [RESULT-1], far exceeding the majority-class baseline's balanced accuracy of [RESULT-2].

The logistic regression model attains a ROC-AUC of [RESULT-3], indicating near-perfect discriminative ranking performance across Iris species.


## Discussion and Future Work

Logistic regression is a well-established linear classification method whose assumptions of approximate linear separability are met by many standard benchmark datasets [SOURCE-1].

Balanced accuracy is the recommended metric for multiclass classification under potential class imbalance, as it averages per-class recall and penalizes majority-class bias [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of 0.973 on Iris, indicating strong discriminative performance across all three species [RESULT-1].

The majority-class baseline achieves a balanced accuracy of 0.500, confirming that naive prediction provides no useful discriminative signal under class-balanced evaluation [RESULT-2].

The ROC-AUC of 0.998 further corroborates near-perfect class separability, consistent with the known near-linear separability of Iris species in petal-based feature dimensions [SOURCE-1] [RESULT-3].

The pronounced gap between logistic regression (0.973) and the majority-class baseline (0.500) demonstrates that the feature set — particularly petal length and width — carries strong species-discriminative signal that a linear model can readily exploit [SOURCE-1] [RESULT-1] [RESULT-2].

We hypothesize that explicit regularization tuning — varying L1 or L2 penalty strength via nested cross-validation — may yield statistically significant improvements in balanced accuracy by reducing overfitting on the small training folds of Iris [SOURCE-1].

We hypothesize that adding feature interaction terms (e.g., petal length × petal width) could allow logistic regression to capture residual nonlinear structure, potentially closing the remaining 2.7 percentage-point gap to perfect balanced accuracy [RESULT-1].

We hypothesize that per-class error analysis will reveal that misclassifications concentrate in the Iris versicolor–Iris virginica pair, which is known to overlap in feature space, and that targeted inspection of per-class precision and recall can distinguish systematic from random errors [SOURCE-1].

We hypothesize that applying dimensionality reduction such as PCA prior to logistic regression will not improve classification accuracy on Iris, given that the feature space is already low-dimensional and highly informative, but may yield interpretability benefits for visualization [RESULT-1].

We aim to the experimental protocol used in this study — pairing balanced accuracy and ROC-AUC with a majority-class baseline — can serve as a reusable evaluation template for logistic regression applied to other small structured classification benchmarks [SOURCE-2].

We aim to we anticipate that the comparative results reported here will support future meta-analyses of linear classifier performance, as Iris remains one of the most widely reported benchmarks in the machine learning literature [SOURCE-1] [SOURCE-2].

We hypothesize that stratified k-fold cross-validation with larger fold counts (e.g., 10-fold) will produce tighter confidence intervals around the balanced accuracy estimate of 0.973, enabling more rigorous comparison against alternative classifiers [RESULT-1] [SOURCE-2].


## Conclusion

The Iris dataset remains a canonical benchmark for evaluating multiclass classification methods, providing a well-characterized testbed for discriminative linear approaches [SOURCE-1].

Logistic regression is a well-established discriminative classifier suitable for multiclass problems such as Iris species classification, where linear separability is largely preserved [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset [RESULT-1], substantially outperforming the majority-class baseline, which attains a balanced accuracy of 0.500 [RESULT-2]. This confirms that the learned discriminative model effectively separates the three Iris classes rather than degenerating to a naive prediction.

The ROC-AUC of 0.998 [RESULT-3] further indicates near-perfect ranking quality across classes, suggesting that the decision boundaries learned by logistic regression align closely with the true class structure of the Iris dataset.

Balanced accuracy is an appropriate metric for this task because it equally weights per-class recall, preventing inflated scores on imbalanced or skewed predictions [SOURCE-2].

We aim to this work aims to provide a clear, reproducible baseline comparison that contextualizes the practical effectiveness of logistic regression for small-scale, well-separated multiclass classification tasks.

We aim to this work aims to reinforce the role of the Iris dataset as a foundational benchmark by demonstrating that even a simple linear classifier can achieve near-perfect balanced accuracy, thereby motivating its continued use in evaluating new methods [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
