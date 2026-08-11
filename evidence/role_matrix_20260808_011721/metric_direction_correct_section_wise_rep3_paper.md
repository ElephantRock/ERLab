# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset, comprising three species characterized by four morphological features, is a canonical benchmark for evaluating classification methods [SOURCE-1] [SOURCE-2].

We apply logistic regression to the Iris dataset's four morphological features to classify flowers into three species, using a majority-class predictor as a baseline for comparison.

We aim to logistic regression will substantially outperform the majority-class baseline, achieving balanced accuracy of 0.973 [RESULT-1] versus 0.500 [RESULT-2] for the baseline, with an ROC-AUC of 0.998 [RESULT-3].


## Introduction

The Iris dataset is a canonical benchmark for evaluating classification algorithms, comprising 150 samples across three species with four morphological features each [SOURCE-1].

Linear classification methods model decision boundaries as linear combinations of input features and have been widely used due to their interpretability and computational efficiency [SOURCE-1].

Logistic regression extends from binary to multiclass settings through the softmax (multinomial) formulation and provides probabilistic outputs interpretable as class membership probabilities [SOURCE-1].

Some Iris class pairs, particularly Iris versicolor and Iris virginica, are less easily separated than Iris setosa, requiring a classifier to capture subtle feature relationships [SOURCE-1].

Standard accuracy can be a deceptive metric in multiclass settings, as it may mask poor performance on individual classes when class distributions are uneven or certain classes are systematically harder to predict [SOURCE-2].

A majority-class predictor assigns every sample to the most frequent class and possesses no discriminative power, achieving only chance-level balanced accuracy on balanced datasets such as Iris [SOURCE-2].

Standard accuracy can diverge meaningfully from balanced accuracy when per-class performance is uneven, even on datasets with equal class distributions [SOURCE-2].

Logistic regression is a well-justified choice for the Iris problem because it offers a probabilistic framework, interpretable coefficients, and transparent diagnosis of model adequacy through its explicit linearity assumption [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, provides a more equitable assessment than raw accuracy by penalizing models that neglect minority classes and ensuring credit is awarded only for genuine per-class discrimination [SOURCE-2].

ROC-AUC serves as a complementary measure of ranking quality that captures aspects of discriminative performance not fully reflected by thresholded metrics such as balanced accuracy [SOURCE-2].

Framing evaluation as a controlled comparison using the same dataset, protocol, and metrics for both the logistic regression model and the majority-class baseline allows improvements to be attributed to learned discriminative patterns rather than data artifacts [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have been extensively studied and remain foundational techniques in supervised learning due to their interpretability and computational efficiency [SOURCE-1].

Logistic regression was originally formulated for binary classification but has been extended to multiclass settings through strategies such as one-vs-rest and multinomial (softmax) formulations [SOURCE-1].

Despite the emergence of more complex nonlinear models, logistic regression has been shown to remain competitive on low-dimensional, linearly separable or near-separable datasets [SOURCE-1].

A key limitation of logistic regression is its reliance on linear decision boundaries, which can lead to suboptimal performance when class distributions exhibit complex nonlinear structure [SOURCE-1].

Logistic regression is also sensitive to multicollinearity among input features, which can destabilize coefficient estimates and reduce generalization performance [SOURCE-1].

Regularization techniques such as L1 (Lasso) and L2 (Ridge) penalties have been incorporated into logistic regression to mitigate overfitting and handle correlated features, improving robustness in practice [SOURCE-1].

The Iris dataset, introduced by Fisher, has served as a standard benchmark for evaluating classification algorithms for decades, and logistic regression is frequently included among the baseline methods tested on it [SOURCE-1].

For multiclass classification tasks, accuracy can be misleading when class distributions are imbalanced, and balanced accuracy has been proposed as a more informative metric that accounts for per-class performance [SOURCE-2].

Balanced accuracy is defined as the arithmetic mean of per-class recall and assigns equal weight to each class regardless of its prevalence, yielding a value of 0.5 for a majority-class predictor in a balanced multiclass setting [SOURCE-2].

ROC-AUC has been extended from binary to multiclass settings through averaging strategies such as one-vs-one and one-vs-rest macro-averaging, enabling its use as a threshold-independent measure of discriminative ability [SOURCE-2].

A limitation of ROC-AUC in multiclass settings is that macro-averaging can obscure per-class weaknesses, particularly when one class is perfectly separated while others are more challenging to discriminate [SOURCE-2].

Balanced accuracy, while addressing class imbalance, does not capture confidence-calibrated ranking quality and can yield identical scores for classifiers with very different probability estimates [SOURCE-2].

Simple baseline classifiers such as majority-class predictors and nearest-centroid methods are recommended as lower-bound comparators in classification studies, yet are frequently omitted in published evaluations [SOURCE-2].

Prior surveys of linear classification note that reported performance figures are often not directly comparable across studies due to differences in train-test splits, preprocessing, and regularization choices [SOURCE-1].

Evaluation metric selection has been shown to materially affect conclusions about classifier performance, with studies demonstrating cases where classifiers ranked differently under accuracy versus balanced accuracy or ROC-AUC [SOURCE-2].

Linear methods including logistic regression have been reported to achieve near-perfect accuracy on Iris in multiple prior studies, but such results are often presented without balanced accuracy or a formal baseline comparison, making it difficult to contextualize the practical advantage over trivial classifiers [SOURCE-1].


## Proposed Method

Logistic regression is a well-established linear classification method that models class-conditional probabilities through a logistic (sigmoid) function applied to a linear combination of input features [SOURCE-1].

For multiclass settings such as the three-species Iris problem, multinomial logistic regression extends the binary formulation via the softmax function, producing a normalized probability distribution over all classes [SOURCE-1].

Balanced accuracy is an appropriate primary metric for multiclass evaluation because it computes the arithmetic mean of per-class recall, making it robust to class imbalance [SOURCE-2].

We adopt logistic regression for the Iris classification task because prior surveys indicate that linear classifiers perform competitively on low-dimensional, numerically encoded botanical data [SOURCE-1].

We formulate the task as a supervised multiclass classification problem with three target labels (Iris setosa, Iris versicolor, Iris virginica) and four continuous input features (sepal length, sepal width, petal length, petal width).

We train a multinomial logistic regression model that estimates class probabilities using the softmax function over a learned linear weight matrix and bias vector.

We optimize the model parameters by minimizing the multinomial cross-entropy loss between predicted class probabilities and one-hot encoded true labels.

We apply L2 regularization during optimization to control model complexity and reduce the risk of overfitting on the relatively small Iris dataset.

We establish a majority-class baseline that always predicts the most frequent class observed in the training data, serving as a reference for evaluating whether logistic regression extracts meaningful discriminative signal.

We evaluate all models using balanced accuracy as the primary metric and ROC-AUC as a secondary metric, following established multiclass evaluation protocols [SOURCE-2].

We hypothesize that logistic regression may substantially outperform the majority-class baseline on balanced accuracy, given the well-documented near-linear separability of Iris species in the feature space.

We hypothesize that the multinomial formulation of logistic regression may yield high ROC-AUC by producing well-calibrated probability estimates across all three species.

We hypothesize that we anticipate that L2 regularization may reduce variance in the estimated coefficients without materially degrading classification accuracy on this dataset.


## Evaluation Plan

We use the Iris dataset [SOURCE-1], a canonical multiclass classification benchmark comprising 150 samples across three Iris species (setosa, versicolor, and virginica) with four morphological features per sample, to evaluate logistic regression in a controlled, well-understood setting.

Following established practice for multiclass evaluation [SOURCE-2], we employ balanced accuracy as our primary metric, computed as the macro-average of per-class recall, which is robust to class imbalance and appropriate for the three-class Iris setting.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) [SOURCE-2] as a secondary metric, using the one-vs-rest macro-averaged formulation, which provides a threshold-independent measure of discriminative ability across all three classes.

Our primary comparison is against a majority-class predictor baseline that assigns all samples to the most frequent class observed in the training data, which provides a lower bound on classification performance and is particularly informative under balanced accuracy [SOURCE-1].

We split the Iris dataset into training and test partitions using stratified sampling to preserve class proportions in both subsets, then train a multinomial logistic regression model with L2 regularization on the training split and evaluate on the held-out test set.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that the four morphological features in Iris are known to carry strong discriminative signal for species separation [SOURCE-1].

We hypothesize that we further hypothesize that the model will achieve high ROC-AUC, reflecting strong class separability under the linear decision boundaries learned by logistic regression [SOURCE-1].

Our results confirm these hypotheses: the logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], compared to 0.500 for the majority-class baseline [RESULT-2].

Additionally, the model achieves a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect discriminative ability on the Iris dataset.


## Discussion and Future Work

Our results demonstrate that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, substantially exceeding the majority-class baseline of 0.500 [RESULT-2].

The ROC-AUC of 0.998 [RESULT-3] indicates near-perfect class separation under the comparison model.

These findings are consistent with prior literature characterizing logistic regression as an effective linear classifier for well-separated, low-dimensional data [SOURCE-1].

Balanced accuracy, as a metric that equally weights per-class performance, is particularly informative for the Iris dataset because class frequencies are approximately balanced, meaning the majority-class predictor achieves only 0.500 by design [SOURCE-2] [RESULT-2].

We hypothesize that the near-ceiling performance observed on Iris may not transfer to datasets with higher feature dimensionality or greater class overlap, where the linear decision boundaries of logistic regression may be insufficient to separate classes [SOURCE-1].

We hypothesize that regularization techniques such as L1 or L2 penalties could improve robustness on noisier variants of Iris without significantly degrading the classification accuracy observed on the clean dataset [SOURCE-1].

We hypothesize that kernelized or nonlinear extensions of logistic regression could match or exceed the reported balanced accuracy on datasets where nonlinear class boundaries are present, though potentially at the cost of increased computational complexity [SOURCE-1].

We hypothesize that augmenting the feature space with interaction terms or polynomial features may yield diminishing returns on Iris specifically, given the already high performance of the linear model, but could be more impactful on structurally similar datasets with subtler feature interactions [RESULT-1].

We aim to the evaluation methodology presented here—pairing a standard linear classifier with balanced accuracy and ROC-AUC against a majority-class baseline—can serve as a reproducible template for benchmarking future classification methods on small tabular datasets [SOURCE-2].

We aim to extending this evaluation protocol to include confidence intervals, cross-validation stability analyses, and statistical significance testing would further strengthen the reliability of comparative claims in small-data classification settings [SOURCE-2].


## Conclusion

The Iris dataset remains a widely used benchmark for evaluating classification methods, offering a tractable yet meaningful test bed for linear models [SOURCE-1].

Our results show that logistic regression achieves a balanced_accuracy of 0.973 [RESULT-1], nearly doubling the majority-class baseline balanced_accuracy of 0.500 [RESULT-2], indicating that the model effectively discriminates among the three Iris species rather than relying on class-frequency shortcuts.

The comparison model also attains an ROC-AUC of 0.998 [RESULT-3], suggesting strong ranking performance across classes under a higher-is-better interpretation.

Balanced accuracy provides a more informative view of multiclass performance than raw accuracy, especially when class distributions are uniform yet inter-class separability varies [SOURCE-2].

We aim to this work aims to demonstrate that even a comparatively simple linear model such as logistic regression can deliver near-perfect balanced accuracy on a well-structured benchmark like Iris, reinforcing the value of establishing strong baselines before applying more complex approaches.

We aim to this work aims to motivate future studies to report balanced accuracy and ROC-AUC alongside simple accuracy when evaluating classifiers, so that class-conditional performance is not obscured by aggregate metrics [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
