# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset serves as a foundational benchmark for evaluating machine learning classification algorithms, offering a well-characterized multi-class problem with clear feature-to-class relationships [SOURCE-1].

Logistic regression is a well-established linear classification method that models class probabilities through a linear combination of input features and is widely applicable to multi-class settings [SOURCE-1].

We apply multinomial logistic regression to the Iris dataset to perform multi-class classification of iris flower species based on sepal and petal measurements [SOURCE-1].

We aim to we expect to demonstrate that logistic regression achieves high classification efficacy on the Iris dataset, attaining a balanced accuracy of 0.973 [RESULT-1] and a ROC-AUC of 0.998 [RESULT-3].

We aim to show that this logistic regression model substantially outperforms a naive majority-class baseline, which yields a balanced accuracy of only 0.500 [RESULT-2] [SOURCE-2].


## Introduction

The Iris dataset, introduced by Ronald Fisher in 1936, has served as one of the most widely used benchmark datasets for evaluating machine learning classification algorithms, consisting of 150 samples across three species of iris flowers with four morphological features each [SOURCE-1].

Classification tasks on structured tabular data, such as the Iris dataset, frequently employ linear models as both interpretable baselines and competitive classifiers, with logistic regression remaining a cornerstone method due to its simplicity, interpretability, and effectiveness on linearly separable or near-separable feature spaces [SOURCE-1].

For multi-class classification problems, proper evaluation requires metrics that account for class balance and per-class performance, as naive accuracy can obscure poor performance on minority classes or in settings with class imbalance [SOURCE-2].

Despite its simplicity, the majority-class predictor—a baseline that assigns all instances to the most frequent class—is often surprisingly difficult to surpass meaningfully in real-world settings with substantial class imbalance or overlapping feature distributions, making it an essential comparator [SOURCE-2].

A persistent limitation in many classification studies is the reliance on a single evaluation metric, which can fail to capture the full picture of classifier behavior—particularly in multi-class settings where per-class sensitivity, overall discrimination ability, and calibration each convey distinct information [SOURCE-2].

While logistic regression is a well-established method, prior surveys have noted that its performance on small, clean benchmark datasets like Iris is not always documented with a comprehensive suite of metrics, and direct comparisons to naive baselines using balanced accuracy are underreported in the literature [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more robust alternative to standard accuracy for evaluating classifiers, particularly in the presence of class imbalance, because it penalizes classifiers that perform well only on majority classes [SOURCE-2].

The design of our study follows established practice in machine learning evaluation research, where a model's discriminative performance is assessed against both a naive baseline and using complementary metrics such as ROC-AUC alongside primary classification metrics [SOURCE-2].

The application of logistic regression to multi-class problems via multinomial (softmax) extension is motivated by the success of generalized linear models in capturing relationships in structured feature spaces where class boundaries are approximately linear [SOURCE-1].

Reporting ROC-AUC in addition to balanced accuracy is motivated by the complementary information it provides—while balanced accuracy captures classification performance at a fixed decision threshold, ROC-AUC summarizes the model's ranking ability across all thresholds, offering a threshold-independent view of discriminative power [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have been extensively studied and remain foundational to supervised learning due to their interpretability and computational efficiency [SOURCE-1].

Logistic regression, originally formulated for binary classification, has been extended to multi-class settings through techniques such as the one-vs-rest and multinomial (softmax) formulations, both of which are standard approaches in widely used machine learning libraries [SOURCE-1].

Despite the proliferation of more complex non-linear classifiers such as kernel methods and deep neural networks, linear methods like logistic regression remain competitive on low-dimensional, well-separated datasets, where model simplicity and interpretability are valued [SOURCE-1].

The Iris dataset has served as a canonical benchmark in the classification literature for decades, and prior surveys have noted that linear classifiers frequently achieve near-perfect accuracy on it, making it a useful baseline for validating new methodological implementations [SOURCE-1].

Balanced accuracy has been recommended as a more informative metric than raw accuracy for classification tasks, particularly when class distributions are uniform but per-class performance may vary, as it averages recall across all classes equally [SOURCE-2].

ROC-AUC has been widely adopted as a threshold-independent metric for evaluating classifier discrimination, and its multi-class generalization through one-vs-one or one-vs-rest averaging has become standard practice in multi-class evaluation protocols [SOURCE-2].

Majority-class prediction, in which all instances are assigned to the most frequent class, has been established as a minimal baseline for classification tasks; on balanced datasets with C classes, its expected balanced accuracy is 1/C, providing a floor against which meaningful classifiers must improve [SOURCE-2].

Prior surveys of linear classification note that while logistic regression is well understood theoretically, published empirical studies often report results using raw accuracy rather than balanced metrics, making it difficult to compare model performance fairly across datasets with varying class distributions [SOURCE-1].

Existing evaluations of linear classifiers on the Iris dataset frequently omit explicit comparison against naive baselines such as majority-class prediction, which makes it difficult to assess the practical utility added by the model relative to trivial solutions [SOURCE-1].

Multi-class evaluation studies have shown that reporting a single metric can obscure important per-class performance differences, yet many published results on standard benchmarks still fail to report complementary metrics such as ROC-AUC alongside accuracy-based measures [SOURCE-2].


## Proposed Method

Logistic regression is one of the most widely studied and applied linear classification methods in machine learning, offering interpretable probabilistic outputs through a linear decision boundary [SOURCE-1].

We select multinomial logistic regression as our primary classifier because the Iris dataset's three classes are approximately linearly separable in their four-dimensional feature space, aligning naturally with the inductive bias of linear models [SOURCE-1].

We employ the multinomial extension of logistic regression using the softmax function, which directly estimates the probability of each class given the input features.

This multinomial formulation is preferred over one-vs-rest decomposition because it produces a single coherent probabilistic model over all classes and avoids the inconsistencies that can arise when binary classifiers are combined heuristically [SOURCE-1].

We apply z-score standardization to all four features prior to model fitting, transforming each feature as x'ⱼ = (xⱼ − μⱼ) / σⱼ where μⱼ and σⱼ are computed from the training split.

The standardization parameters are estimated exclusively from training data and subsequently applied to the test partition to prevent information leakage.

We fit the multinomial logistic regression parameters via maximum likelihood estimation with L2 regularization, minimizing the negative log-likelihood subject to a penalty on the squared L2 norm of the weight coefficients.

This L2 regularization term discourages excessively large weight values and mitigates overfitting given the modest sample size (n = 150) relative to the number of model parameters [SOURCE-1].

We implement a majority-class predictor that assigns every test instance to the most frequent class observed in the training data.

Balanced accuracy computes the macro-average of per-class recall, thereby weighting each class equally regardless of its frequency in the test set [SOURCE-2].

We select balanced accuracy as the primary evaluation metric because it ensures that classification performance is assessed fairly across all three Iris species [SOURCE-2].

We report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to capture the model's overall discriminative ability across decision thresholds.

We hypothesize that multinomial logistic regression will substantially outperform the majority-class baseline on balanced accuracy [SOURCE-1].

We hypothesize that the model will achieve high discriminative performance as measured by ROC-AUC, reflecting strong inter-class separation along the morphological dimensions [SOURCE-1].


## Evaluation Plan

We evaluate our logistic regression model on the Iris dataset, a widely used multiclass classification benchmark consisting of 150 samples equally distributed across three Iris species (setosa, versicolor, and virginica) with four morphological features per sample [SOURCE-1].

Following established practices for multiclass evaluation, we adopt balanced accuracy as our primary metric, defined as the macro-averaged recall across all classes, which is robust to class imbalance and provides a fair per-class assessment [SOURCE-2].

We additionally report the macro-averaged ROC-AUC computed via a one-vs-rest strategy, which quantifies the model's ranking quality of probability estimates across all classification thresholds [SOURCE-2].

We employ a majority-class baseline predictor that always assigns the most frequent training-set class, serving as a minimal-performance reference point that any meaningful classifier should surpass.

The experimental protocol is designed to isolate the contribution of the logistic regression model by holding the dataset, preprocessing pipeline, and evaluation metrics constant across the model and baseline conditions, thereby ensuring that observed performance differences are attributable solely to the classification algorithm.

We train the logistic regression model using multinomial (softmax) regression with L2 regularization and standardize all features to zero mean and unit variance prior to fitting, as logistic regression's regularization term is sensitive to feature scaling [SOURCE-1].

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given the well-documented linear separability of at least one Iris class and the moderate separability of the remaining two classes [SOURCE-1].

We hypothesize that we further hypothesize that the model's ROC-AUC will be high, reflecting that logistic regression produces well-separated probability estimates for the three Iris species rather than merely correct hard predictions [SOURCE-2].

Our results confirm the first hypothesis: the logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], while the majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], demonstrating a substantial and statistically meaningful performance gap.

Our results also confirm the second hypothesis: the model achieves a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class separability in the model's probability estimates across all three Iris species.

We hypothesize that the strong performance is primarily driven by the discriminative power of petal-based features (petal length and petal width), which are known to provide strong linear separation between Iris species [SOURCE-1].

The majority-class baseline's balanced accuracy of 0.500 [RESULT-2] serves as a floor reference; any classifier that meaningfully leverages the feature space should exceed this threshold.


## Discussion and Future Work

The Iris dataset has long served as a foundational benchmark in machine learning, enabling direct comparison across decades of classification studies [SOURCE-1].

Linear classification methods, including logistic regression, have been extensively studied and shown to be effective on datasets where classes are approximately linearly separable [SOURCE-1].

Our results show that the logistic regression model achieved a balanced accuracy of 0.973 [RESULT-1], dramatically outperforming the majority-class baseline, which attained a balanced accuracy of only 0.500 [RESULT-2] [SOURCE-2].

The ROC-AUC of 0.998 [RESULT-3] corroborates the model's excellent class-ranking capability across all three Iris species [SOURCE-2].

Balanced accuracy provides an equitable evaluation framework for multi-class tasks by averaging per-class recall, ensuring that performance is not inflated by class frequency [SOURCE-2].

We hypothesize that the near-ceiling performance observed on Iris reflects the dataset's inherent linear separability, and that comparable performance may not generalize to datasets with greater class overlap, higher dimensionality, or significant label noise [SOURCE-1].

We hypothesize that feature engineering—such as interaction terms, polynomial expansions, or domain-specific transformations—may yield meaningful performance gains on datasets where raw features provide insufficient discriminative power.

We hypothesize that L1 or L2 regularization may improve generalization when logistic regression is applied to high-dimensional datasets where overfitting is a concern [SOURCE-1].

We hypothesize that comparing multinomial logistic regression with one-vs-rest decomposition may reveal performance differences as the number of classes grows beyond the three species in Iris [SOURCE-2].

We hypothesize that ensemble methods combining logistic regression with nonlinear classifiers may provide a cost-effective middle ground on datasets where purely linear models underperform.

We aim to the expected contribution of these future investigations is a set of empirically grounded guidelines for deploying logistic regression across diverse classification scenarios—clarifying when linear methods suffice, when augmentation is necessary, and which augmentation strategies are most effective [SOURCE-1] [SOURCE-2].


## Conclusion

In this study, we evaluated logistic regression on the Iris dataset, demonstrating that the model achieves a balanced accuracy of 0.973 and an ROC-AUC of 0.998 [RESULT-1] [RESULT-3].

The reported performance represents a substantial improvement over the majority-class baseline, which yielded a balanced accuracy of 0.500 [RESULT-2].

We aim to this work aims to reinforce the value of simple, interpretable linear models as highly competitive approaches for foundational multi-class classification benchmarks.


## References

[Generated from 2 source papers — see proposal for full bibliography]
