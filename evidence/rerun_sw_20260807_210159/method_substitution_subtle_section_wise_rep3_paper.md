# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Multiclass classification on small, well-structured datasets serves as a standard benchmark for evaluating regularized linear models [SOURCE-1].

Balanced accuracy provides a robust evaluation metric for multiclass classification by averaging per-class recall, thereby accounting for potential class imbalance [SOURCE-2].

We apply L2-penalized (ridge) logistic regression to multiclass classification on the Iris dataset, where the L2 penalty term shrinks all coefficient magnitudes uniformly toward zero to control model complexity and mitigate overfitting [SOURCE-1].

We compare our regularized model against a majority-class baseline predictor that always selects the most frequent class, using balanced accuracy as the primary evaluation metric.

We aim to we expect our L2-regularized logistic regression model to achieve a balanced accuracy of 0.973 [RESULT-1] on Iris classification, substantially outperforming the majority-class baseline at 0.500 [RESULT-2].

We aim to we further aim to demonstrate that the regularized model achieves strong overall discriminative power, with an ROC-AUC of 0.998 [RESULT-3] on the Iris dataset.


## Introduction

Multiclass classification—assigning instances to one of three or more discrete categories—is a foundational task in machine learning with applications spanning text categorization, image recognition, and bioinformatics [SOURCE-1].

Logistic regression is one of the most widely studied linear classification methods, offering interpretable coefficients and convex optimization objectives that guarantee global solutions [SOURCE-1].

The Iris dataset, introduced by Fisher, remains a standard benchmark for evaluating multiclass classifiers due to its manageable size, four continuous features, and three balanced classes [SOURCE-1].

Unregularized linear models can overfit on small datasets, particularly when feature dimensions are comparable to the number of training samples, leading to unstable coefficient estimates and poor generalization [SOURCE-1].

Accuracy as a sole evaluation metric can be misleading, especially when class distributions are uneven, motivating the use of balanced accuracy which averages per-class recall and is robust to class imbalance [SOURCE-2].

Naive baselines such as majority-class prediction, while trivial, provide a critical lower bound on acceptable performance; a classifier that fails to exceed such a baseline on balanced accuracy offers no practical utility [SOURCE-2].

L2 (ridge) regularization addresses the overfitting problem by adding a squared-magnitude penalty on coefficients to the loss function, shrinking weights toward zero without inducing exact sparsity, thereby controlling model variance while retaining all features [SOURCE-1].

L2-penalized logistic regression has been successfully applied across diverse classification domains—including gene expression analysis and document classification—demonstrating its robustness and general applicability as a regularized linear model [SOURCE-1].

The Iris dataset's continuous, moderately correlated features make it well-suited for studying the effects of ridge regularization, since L2 shrinkage is particularly effective when predictors are correlated and multicollinearity would otherwise destabilize unregularized estimates [SOURCE-1].

A systematic comparison of L2-regularized logistic regression against a majority-class baseline using balanced accuracy provides a rigorous, reproducible assessment of how much signal a regularized linear model can extract from a compact, well-structured benchmark [SOURCE-2].


## Related Work

Linear classification methods have been extensively studied and remain foundational for supervised learning tasks, with logistic regression being one of the most widely adopted approaches [SOURCE-1].

Logistic regression can be extended to multiclass classification through formulations such as one-vs-rest or multinomial (softmax) encoding, both of which are standard practices documented in surveys of linear methods [SOURCE-1].

Regularization techniques, including L1 (lasso) and L2 (ridge) penalties, are routinely applied to logistic regression to mitigate overfitting by constraining the magnitude of model coefficients [SOURCE-1].

L2 regularization shrinks all coefficient weights uniformly toward zero without setting any to exactly zero, thereby retaining all input features in the model while reducing variance [SOURCE-1].

The Iris dataset, introduced by Fisher, has served as a canonical benchmark for evaluating classification algorithms, including linear methods, for decades and remains a standard test bed in the machine learning literature [SOURCE-1].

Balanced accuracy has been recommended as a more informative metric than raw accuracy for classification tasks, because it averages per-class recall and is robust to class imbalance [SOURCE-2].

ROC-AUC provides an additional threshold-independent measure of discriminative performance that complements balanced accuracy by summarizing the trade-off between true positive and false positive rates across all decision thresholds [SOURCE-2].

A persistent limitation in prior classification studies is the reliance on raw accuracy as the sole evaluation metric, which can produce misleadingly optimistic scores when class distributions are skewed, thereby masking poor minority-class performance [SOURCE-2].

Prior evaluations of linear classifiers frequently omit comparison against trivial baselines such as a majority-class predictor, making it difficult to assess whether reported performance reflects genuine discriminative learning rather than class-prior exploitation [SOURCE-2].

Although surveys of linear methods note that logistic regression with L2 regularization is a well-understood and theoretically grounded approach, many empirical studies fail to report multiple complementary metrics, limiting the interpretability and reproducibility of their findings [SOURCE-1, SOURCE-2].

Surveys of linear classification methods confirm that logistic regression achieves competitive performance on low-dimensional, well-separated datasets, yet these surveys also note that the relative ranking of regularized variants depends heavily on dataset characteristics and evaluation protocol [SOURCE-1].

Evaluation metric studies have shown that balanced accuracy reduces to standard accuracy when classes are perfectly balanced but diverges meaningfully under imbalance, making it a strict generalization that is appropriate even for datasets like Iris that are near-balanced [SOURCE-2].


## Proposed Method

Logistic regression is a well-established linear classification method that models class-conditional posterior probabilities through the softmax function [SOURCE-1].

Balanced accuracy, defined as the macro-average of per-class recall, is a suitable metric for multiclass classification because it assigns equal weight to each class regardless of its sample count [SOURCE-2].

Prior work has shown that L2 (ridge) regularization controls model complexity by uniformly shrinking all coefficient magnitudes toward zero [SOURCE-1].

We adopt L2 regularization because its uniform shrinkage property is particularly suited to small, well-structured datasets where the risk of overfitting is elevated [SOURCE-1].

We propose an L2-penalized (ridge) logistic regression model with multinomial loss for three-class classification on the Iris dataset.

Specifically, we use scikit-learn's LogisticRegression configured with penalty='l2', the lbfgs solver, and multinomial loss.

The optimization objective minimizes the negative log-likelihood of the multinomial distribution augmented by an L2 penalty term (1/C) * ||w||_2^2, where w denotes the model coefficients and C is the inverse regularization strength [SOURCE-1].

We hypothesize that L2 regularization may reduce overfitting on the Iris dataset.

We hypothesize that this regularized model will substantially outperform a majority-class baseline on balanced accuracy.

We evaluate on the Iris dataset, comprising 150 samples evenly distributed across three species (Setosa, Versicolor, Virginica) with four morphological features: sepal length, sepal width, petal length, and petal width.

We adopt balanced accuracy as the primary evaluation metric for model comparison [SOURCE-2].

We compare our method against a majority-class predictor that always assigns the most frequent class label.

Our results show that the L2-regularized logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1].

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2].

The model additionally attains a ROC-AUC of 0.998 [RESULT-3].


## Evaluation Plan

We evaluate on the Iris dataset [SOURCE-1], a widely used multiclass classification benchmark comprising 150 samples evenly distributed across three species: Iris setosa, Iris versicolor, and Iris virginica, each described by four continuous morphological features.

The Iris dataset's low-dimensional, largely linearly separable class structure provides a clean testbed for assessing decision boundary quality and the effect of regularization strength, with Iris setosa being linearly separable from the other two species while versicolor and virginica exhibit some overlap [SOURCE-1].

Following established practices for multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary metric, defined as the macro-average of per-class recall, which is robust to class imbalance and ensures that performance on each class contributes equally to the final score.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC), computed using a one-vs-rest averaging strategy, which summarizes the model's ranking quality across decision thresholds and provides a complementary view of discriminative performance [SOURCE-2].

We fit an L2-penalized (ridge) logistic regression model using scikit-learn's LogisticRegression with the L2 penalty and the lbfgs solver, optimizing the multinomial loss directly to ensure that probability estimates are calibrated jointly across all three classes.

The L2 penalty was chosen over L1 regularization because the Iris feature set is small (four features) and all features carry meaningful discriminative information; sparsity-inducing regularization would risk discarding useful signal without commensurate benefit, whereas L2 provides gentle shrinkage that stabilizes coefficient estimates without eliminating features [SOURCE-1].

As a baseline, we employ a majority-class predictor that always predicts the most frequent class; since Iris is class-balanced (50 samples per class), the majority-class baseline is expected to yield a balanced accuracy of approximately 0.500, representing chance-level performance.

The regularization strength is set to C=1.0 (the scikit-learn default), reflecting a moderate level of shrinkage appropriate for a dataset of this size and dimensionality, with a maximum of 1000 iterations and tolerance of 1e-4 for convergence.

Features are used in their raw form without additional preprocessing such as standardization, as logistic regression with L2 regularization is expected to perform adequately on Iris given the similar magnitude ranges of the four measurements.

We hypothesize that L2-regularized logistic regression will substantially outperform the majority-class baseline in balanced accuracy, given that the Iris features provide strong linear separability between species [SOURCE-1].

We hypothesize that we further hypothesize that the model will achieve balanced accuracy above 0.90 and near-perfect ROC-AUC above 0.95, reflecting the high degree of class separation in the four-dimensional feature space [SOURCE-2].

Our experimental results confirm these expectations: the L2-penalized logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], compared to 0.500 for the majority-class baseline [RESULT-2].

The model also attains a ROC-AUC of 0.998 [RESULT-3], indicating excellent discriminative capability across all three classes.

We hypothesize that the modest gap between balanced accuracy (0.973) and ROC-AUC (0.998) suggests that the few misclassifications arise from samples near the versicolor/virginica decision boundary rather than from systematic ranking errors [SOURCE-1].


## Discussion and Future Work

Our results demonstrate that L2-regularized logistic regression achieves strong multiclass classification performance on the Iris dataset, with a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3] [SOURCE-1].

This performance substantially exceeds the majority-class baseline, which yields a balanced accuracy of only 0.500 [RESULT-2], confirming that the model discriminates among the three Iris species rather than exploiting class frequency [SOURCE-2].

On a dataset like Iris, where all four morphological features—sepal length, sepal width, petal length, and petal width—carry discriminative information, the uniform coefficient shrinkage imposed by the L2 penalty is well-matched, as no feature needs to be entirely excluded [SOURCE-1].

The high ROC-AUC of 0.998 [RESULT-3] further indicates that the model's class probability estimates are well-ordered, which is valuable for downstream decision-making tasks that depend on threshold calibration [SOURCE-2].

The Iris dataset is small (150 samples), well-separated, and low-dimensional, which means our findings may not transfer directly to noisier, higher-dimensional settings where the distinction between L1 and L2 regularization paths has greater practical consequence [SOURCE-1].

We hypothesize that L1-regularized (lasso) logistic regression, by driving irrelevant feature weights to exactly zero, would yield interpretable sparse feature subsets while maintaining classification accuracy comparable to that of L2 regularization on datasets with higher dimensionality or feature redundancy [SOURCE-1].

We hypothesize that we further hypothesize that a systematic comparison of L1 and L2 regularization paths across a suite of botanical or biological classification benchmarks would reveal distinct regimes of superiority, particularly as feature dimensionality and inter-feature correlation vary [SOURCE-1].

We aim to such a comparative study would contribute a practical selection guideline tying regularization type to dataset characteristics such as feature-to-sample ratio, redundancy level, and expected number of informative features [SOURCE-1].

We hypothesize that elastic net regularization, which interpolates between the L1 and L2 penalties, would inherit the feature selection capability of the lasso while retaining the coefficient stability of ridge regression in correlated feature settings [SOURCE-1].

We aim to extending the evaluation to include per-class precision-recall curves, calibration plots, and learning curves would yield a more nuanced understanding of model behavior, particularly in low-data regimes where the choice of regularization strength is critical [SOURCE-2].


## Conclusion

The Iris dataset, with its well-separated feature space across three species, serves as an established benchmark for evaluating regularized linear classification methods [SOURCE-1].

Balanced accuracy provides a fair evaluation metric for multiclass classification, as it accounts for potential class imbalance and avoids the misleading inflation of raw accuracy under majority-class dominance [SOURCE-2].

L2-regularized (ridge) logistic regression achieved a balanced accuracy of 0.973 on the Iris dataset, substantially outperforming the majority-class baseline at 0.500 [RESULT-1] [RESULT-2].

The model achieved an ROC-AUC of 0.998, indicating strong discriminative ability across all three Iris classes under the L2-penalized model [RESULT-3].

We aim to this work aims to provide a reproducible evaluation framework for L2-regularized logistic regression on multiclass classification benchmarks by reporting both balanced accuracy and ROC-AUC alongside a majority-class baseline.

We aim to this work aims to demonstrate that L2 (ridge) regularization, which shrinks coefficient magnitudes uniformly without inducing sparsity, is sufficient for achieving near-perfect classification when the underlying feature space is well-structured, as is the case with the Iris measurements [RESULT-1].

We aim to this work aims to motivate future comparisons between L2-regularized and L1-regularized (lasso) logistic regression, to assess whether implicit feature selection through sparsity yields comparable predictive performance or additional interpretability advantages on benchmark datasets such as Iris.

We aim to this work aims to establish that the performance gap between L2-regularized logistic regression and the majority-class baseline (0.973 vs. 0.500 balanced accuracy) is substantial enough to confirm that the model learns discriminative class boundaries rather than degenerating to majority-class prediction [RESULT-1] [RESULT-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
