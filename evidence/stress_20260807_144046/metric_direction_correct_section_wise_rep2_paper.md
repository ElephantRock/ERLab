# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris species classification problem is a long-standing benchmark in machine learning, consisting of 150 samples across three species characterized by four morphological features [SOURCE-1].

Logistic regression is a well-established linear classification method that models class probabilities through a linear combination of input features and has been widely applied to multiclass classification tasks [SOURCE-1].

We apply multinomial logistic regression to the Iris dataset to classify samples into one of three species using sepal length, sepal width, petal length, and petal width as predictors.

Our logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming the majority-class baseline, which achieves a balanced accuracy of 0.500 [RESULT-2].

The model additionally achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect discriminative ability across the three Iris species.

We aim to we expect this study to provide a robust, reproducible baseline for logistic regression on the Iris dataset that future comparative studies can readily reference.


## Introduction

Linear classification methods constitute a foundational pillar of supervised machine learning, providing interpretable models with well-established theoretical guarantees and efficient training procedures [SOURCE-1].

Logistic regression occupies a particularly prominent position among linear classifiers due to its probabilistic formulation, which directly models class membership probability and produces calibrated outputs amenable to threshold-independent evaluation [SOURCE-1].

The Iris dataset is one of the most widely recognized benchmark datasets for evaluating classification algorithms, comprising 150 samples across three species described by four morphological features [SOURCE-1].

While Iris setosa is linearly separable from the other two species, Iris versicolor and Iris virginica exhibit overlap in feature space, making the full three-class problem non-trivial [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class sensitivity, provides a measure robust to class imbalance by equally weighting each class regardless of its prevalence [SOURCE-2].

ROC-AUC offers a complementary evaluation perspective by measuring the model's ability to rank-order instances by predicted probability across varying decision thresholds [SOURCE-2].

Many studies evaluating classification on standard benchmarks such as Iris fail to include comparisons against trivial baselines like majority-class predictors, making it difficult to assess whether reported accuracy reflects meaningful learning [SOURCE-2].

Existing surveys of linear classification methods report empirical results with inconsistent evaluation protocols—varying train-test splits, cross-validation schemes, and metric sets—which hinders direct and fair comparison across studies [SOURCE-1].

Some studies report only overall accuracy, a metric that can be misleading in multiclass settings where a model might perform well on dominant classes while struggling with others [SOURCE-2].

Logistic regression's performance is frequently presented without adequate context in prior surveys, either without comparison to a trivial baseline or without comprehensive metric reporting [SOURCE-1].

The Iris dataset's moderate dimensionality and predominantly linear structure make it well-matched to the assumptions underlying logistic regression, motivating its selection as the classification method [SOURCE-1].

Logistic regression's direct probabilistic output enables evaluation using threshold-independent metrics such as ROC-AUC, providing a richer assessment than accuracy alone [SOURCE-1].

Pairing logistic regression with a majority-class predictor baseline and evaluating with balanced accuracy addresses the identified limitations of inconsistent and incomplete reporting in prior work [SOURCE-2].


## Related Work

Linear classification methods have long been foundational to supervised learning, with logistic regression remaining one of the most widely used due to its interpretability and strong performance on linearly separable data [SOURCE-1].

The Iris dataset has served as a standard benchmark for evaluating classification algorithms since its introduction, making it an appropriate testbed for establishing baseline performance of fundamental methods [SOURCE-1].

Prior surveys of linear classification have noted that logistic regression achieves competitive accuracy on small, low-dimensional datasets where classes are approximately linearly separable [SOURCE-1].

However, many existing studies on linear classification report only raw accuracy, which can be misleading when class distributions are imbalanced or when multiclass scenarios obscure per-class performance [SOURCE-1].

Balanced accuracy has been proposed as a more robust alternative that averages per-class recall, providing a fairer assessment of classifier performance across all classes [SOURCE-2].

ROC-AUC has similarly been recommended for evaluating the ranking quality of probabilistic classifiers, particularly in multiclass settings where threshold selection impacts performance interpretation [SOURCE-2].

Despite the availability of these metrics, a significant body of prior work on classic datasets such as Iris continues to rely on a limited set of evaluation criteria, making it difficult to compare results across studies or to identify specific weaknesses of trained models [SOURCE-1].

Furthermore, much of the existing literature on Iris classification emphasizes complex or ensemble methods, while comparatively fewer studies document the performance ceiling achievable by simple, interpretable baselines such as logistic regression under rigorous multiclass evaluation [SOURCE-1].

Standard multiclass evaluation protocols, including per-class metric decomposition and comparison against majority-class baselines, have been advocated as essential for honest reporting but are inconsistently applied across published benchmark studies [SOURCE-2].

Prior work has also noted that the absence of a majority-class baseline comparison can lead to inflated perceptions of classifier quality, particularly on datasets where class distributions may not be perfectly uniform [SOURCE-2].


## Proposed Method

The Iris classification task requires assigning one of three species labels (setosa, versicolor, virginica) to each instance on the basis of four continuous morphological features: sepal length, sepal width, petal length, and petal width.

Logistic regression is a foundational linear classification method that has been extensively surveyed and remains a strong reference point for low-dimensional tabular classification problems [SOURCE-1].

We adopt multinomial (softmax) logistic regression as our primary classifier [SOURCE-1].

For each class k, the model computes P(y = k | x) = exp(w_kᵀx + b_k) / Σ_j exp(w_jᵀx + b_j), and the parameter set Θ is estimated by minimizing the L2-regularized cross-entropy loss via gradient-based optimization [SOURCE-1].

The Iris feature space is low-dimensional, a regime in which linear classifiers are known to remain competitive with more flexible nonlinear alternatives [SOURCE-1].

The resulting coefficients w_k are directly interpretable in terms of the original morphological measurements, which is a desirable property for a baseline reference study [SOURCE-1].

Multinomial logistic regression provides calibrated class-probability estimates, which makes additional ranking metrics such as ROC-AUC directly applicable without auxiliary calibration [SOURCE-1].

We employ a majority-class predictor that assigns every test instance to the most frequent class observed in the training set, as a non-informative reference baseline.

Balanced accuracy is well suited to multiclass evaluation and is robust to class-frequency effects, which is why it is recommended for reporting alongside raw accuracy in multiclass settings [SOURCE-2].

We additionally report the one-vs-rest ROC-AUC as a secondary indicator of the model's ability to rank classes correctly across decision thresholds [SOURCE-2].

We hypothesize that the multinomial logistic regression model may substantially exceed the majority-class baseline on balanced accuracy, because the Iris classes are largely — though not perfectly — linearly separable [SOURCE-1].

We hypothesize that we expect the model to attain a ROC-AUC near the upper end of the [0.5, 1.0] range, reflecting strong class separation [SOURCE-2].


## Evaluation Plan

We use the Iris dataset [SOURCE-1], a standard multiclass classification benchmark consisting of 150 samples across three species (Setosa, Versicolor, and Virginica) with four morphological features each.

Following [SOURCE-2], we adopt balanced accuracy as our primary evaluation metric, computed as the arithmetic mean of per-class recall, which is appropriate given equal class sizes in Iris.

We additionally report ROC-AUC [SOURCE-2] as a secondary metric to characterize the model's discriminative ability across decision thresholds.

We partition the dataset into training and testing subsets using stratified sampling to preserve class proportions, and we train a multinomial (softmax) logistic regression model with L2 regularization on the training portion [SOURCE-1] [SOURCE-2].

As a baseline, we employ a majority-class predictor that assigns all test samples to the most frequent training class, providing a lower-bound reference for balanced accuracy [SOURCE-2].

All metrics—balanced accuracy and ROC-AUC—are computed on the held-out test set after a single train/test split, without cross-validation, to establish a straightforward and reproducible baseline result [SOURCE-1].

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that Iris features provide strong linear separability between species [SOURCE-1].

We hypothesize that we further hypothesize that the model will achieve near-perfect ROC-AUC due to high-confidence, well-separated class probability estimates on Iris [SOURCE-2].

Our results confirm the first hypothesis: the logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], compared to 0.500 for the majority-class baseline [RESULT-2].

Our results also support the second hypothesis: the model achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class discrimination on the held-out test set.


## Discussion and Future Work

Our results demonstrate that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, substantially outperforming the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

The model achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect discriminative ability across the three Iris species and suggesting that the learned decision boundaries effectively partition the feature space with minimal overlap.

This performance level aligns with prior literature documenting the near-linear separability of Iris features, where even fundamental linear classifiers achieve high classification accuracy [SOURCE-1].

The use of balanced accuracy as the primary evaluation metric is particularly relevant for multi-class problems, as it averages per-class recall and mitigates the risk of inflated performance estimates arising from class imbalance or unequal class priors [SOURCE-2].

The Iris dataset's characteristics—150 instances, four morphological features, and well-separated class distributions—constrain the generalizability of these findings to classification tasks involving higher-dimensional, noisy, or overlapping data.

We hypothesize that applying L1 or L2 regularization to logistic regression on Iris will maintain comparable classification accuracy while producing sparse, interpretable feature importance profiles that reveal which morphological measurements contribute most to species discrimination.

We hypothesize that logistic regression will remain competitive with more complex models such as kernel SVMs or shallow neural networks on botanical classification tasks involving moderate dimensionality, but will degrade on tasks with highly nonlinear class boundaries [SOURCE-1].

We hypothesize that the choice of multi-class decomposition strategy—one-vs-rest versus multinomial—will yield statistically significant performance differences on datasets where class covariance structures are heterogeneous across classes.

We hypothesize that standardizing input features will have negligible impact on Iris classification performance due to the comparable measurement scales of sepal and petal dimensions, but will be critical on datasets combining features with disparate units and ranges.

We hypothesize that ensemble methods combining logistic regression with tree-based classifiers could improve performance specifically on datasets where linear separability is partial rather than complete.

We aim to we expect this baseline to serve as a reproducible reference point for future studies that apply more advanced methods to Iris, enabling fair and standardized assessment of incremental performance gains [RESULT-1] [RESULT-2].

We aim to we expect these findings to reinforce the practical value of simple, transparent linear models as strong starting points for structured classification problems, particularly in applied domains where interpretability and computational efficiency are prioritized [SOURCE-1].


## Conclusion

In this study, we applied logistic regression to the Iris species classification task to establish a robust baseline using a fundamental machine learning algorithm [SOURCE-1].

The Iris dataset, a longstanding benchmark in the machine learning community, provides an ideal setting for evaluating the effectiveness of classical classification methods due to its well-defined features and clearly differentiated classes [SOURCE-1].

Our results show that the logistic regression model attained a balanced accuracy of 0.973, substantially outperforming the majority-class baseline, which achieved a balanced accuracy of 0.500 [RESULT-1] [RESULT-2].

The near-doubling of balanced accuracy from baseline to model confirms that logistic regression captures meaningful discriminative patterns rather than trivially predicting the majority class [RESULT-1] [RESULT-2].

The model achieved an ROC-AUC of 0.998, indicating excellent discriminative ability across all three Iris species [RESULT-3].

These findings are consistent with prior work showing that linear classifiers perform well on the Iris dataset, where the classes are largely linearly separable [SOURCE-1] [RESULT-1].

Balanced accuracy serves as an appropriate primary metric for multiclass classification tasks, particularly when class distributions may be imbalanced or when equal importance is assigned to each class [SOURCE-2].

By reporting both balanced accuracy and ROC-AUC, we provide a comprehensive evaluation that captures both classification correctness and the model's ability to rank instances by predicted probability [RESULT-1] [RESULT-3] [SOURCE-2].

We aim to this work aims to provide a clear, reproducible baseline for the Iris classification task using logistic regression.

We aim to this work aims to demonstrate that even relatively simple linear methods can achieve near-perfect classification on well-structured benchmark datasets, motivating future comparisons against more complex approaches such as kernel methods, ensemble classifiers, or neural network architectures.

We aim to future investigations may explore feature engineering, hyperparameter tuning, or comparisons with nonlinear classifiers to determine whether meaningful performance gains are achievable beyond the strong baseline established here.


## References

[Generated from 2 source papers — see proposal for full bibliography]
