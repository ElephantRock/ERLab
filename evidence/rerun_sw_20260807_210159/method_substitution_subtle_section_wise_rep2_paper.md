# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset is a foundational benchmark for multiclass classification, offering structured botanical features that are well-suited to linear modeling [SOURCE-1] [SOURCE-2].

We apply L2-penalized (ridge) logistic regression to the Iris classification task, comparing against a majority-class baseline [SOURCE-1].

The L2 penalty controls overfitting by shrinking coefficient magnitudes uniformly toward zero while retaining all input features, yielding a stable and interpretable decision boundary [SOURCE-1].

Our model achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973, substantially outperforming the baseline.

The majority-class baseline achieves [RESULT-2] balanced_accuracy = 0.500.

The model attains an ROC-AUC of [RESULT-3] ROC-AUC = 0.998, indicating strong discriminative ability across classes.

We aim to we expect these results to confirm that ridge-regularized logistic regression serves as an effective and interpretable baseline for structured multiclass classification tasks.


## Introduction

The Iris dataset, comprising 150 samples across three species with four continuous features, serves as a foundational benchmark for multiclass classification.

Linear classification methods, including logistic regression, remain widely used owing to their interpretability, computational tractability, and competitive performance on low-dimensional problems [SOURCE-1].

Logistic regression extends naturally to multiclass settings via the softmax (multinomial) formulation, optimizing cross-entropy loss to produce calibrated probability estimates [SOURCE-1].

Unregularized maximum-likelihood logistic regression is susceptible to overfitting, particularly when predictor variables are correlated or when feature dimensionality is not negligible relative to sample size [SOURCE-1].

Conventional classification accuracy can obscure important failure modes when class distributions are uneven or when misclassification costs differ across classes [SOURCE-2].

Balanced accuracy provides a more principled assessment by weighting per-class sensitivity equally, reducing the risk that strong performance on one class masks poor performance on another [SOURCE-2].

L2 regularization penalizes the squared magnitude of coefficients, controlling model complexity through uniform shrinkage without inducing sparsity, analogous to ridge regression in linear least-squares settings [SOURCE-1].

Unlike L1 regularization, which induces sparsity and implicit feature selection, L2 regularization retains all predictors in the model—an appropriate design choice when all features are expected to carry discriminative signal [SOURCE-1].


## Related Work

Linear classification methods, including logistic regression, have long served as foundational techniques in supervised learning for both binary and multiclass settings [SOURCE-1].

Logistic regression models the posterior class probabilities through a linear combination of features transformed by a softmax (multinomial) or sigmoid (binomial) function, making it a probabilistic discriminative classifier widely adopted in practice [SOURCE-1].

L2-regularized (ridge) logistic regression adds a squared-magnitude penalty term to the loss function, which shrinks coefficient estimates toward zero and mitigates overfitting, particularly in settings with correlated or high-dimensional features [SOURCE-1].

Compared to unregularized logistic regression, the L2 penalty improves numerical stability of the optimization and reduces variance in coefficient estimates without performing explicit feature selection, as weights are shrunk but typically not driven to exactly zero [SOURCE-1].

Regularization strength in penalized logistic regression is typically controlled via a hyperparameter that trades off model fit against coefficient shrinkage, and this parameter must be selected carefully through cross-validation or a similar procedure to avoid under- or over-regularization [SOURCE-1].

A known limitation of standard logistic regression is its reliance on a linear decision boundary, which can be insufficient when class separability in the feature space is inherently nonlinear [SOURCE-1].

Prior surveys note that logistic regression, despite its simplicity, often achieves competitive classification accuracy on low-dimensional, well-separated benchmark datasets, though performance is sensitive to feature scaling and multicollinearity [SOURCE-1].

Multiclass classification evaluation requires metrics that account for class imbalance and per-class performance, as standard accuracy can be misleading when class distributions are skewed [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, provides a single scalar metric that equally weights sensitivity across all classes, and is particularly appropriate for evaluating classifiers on balanced or near-balanced multiclass benchmarks [SOURCE-2].

A majority-class baseline that always predicts the most frequent class yields a balanced accuracy equal to 1/(number of classes) in perfectly balanced datasets, representing the lower-bound reference for any non-trivial classifier [SOURCE-2].

ROC-AUC, commonly used in binary classification to summarize the rank-ordering quality of predicted probabilities, has been extended to the multiclass setting through averaging strategies such as one-vs-rest macro-averaging, though its interpretation becomes less straightforward than in the binary case [SOURCE-2].

Prior work has noted that single-metric evaluation can obscure failure modes such as systematic per-class errors, and it is recommended to report multiple complementary metrics including accuracy, per-class recall, and probability-ranking measures for a more complete assessment [SOURCE-2].

Evaluation metrics can diverge significantly when class distributions are imbalanced, and metrics like balanced accuracy and macro-averaged ROC-AUC are preferred in such scenarios because they do not privilege majority classes [SOURCE-2].

The Iris dataset, introduced by Fisher, has served as a canonical multiclass benchmark for evaluating linear classifiers, and prior literature consistently reports that logistic regression and related linear models achieve near-ceiling accuracy on this dataset due to its relatively well-separated class structure [SOURCE-1].

Despite strong average performance on benchmarks like Iris, standard logistic regression can still produce per-class error patterns that reveal systematic weaknesses, and prior studies caution against relying solely on aggregate metrics without inspecting class-level confusion [SOURCE-1].

Comparative surveys have shown that regularized linear models frequently match or exceed more complex nonlinear classifiers on small, low-dimensional datasets, while offering advantages in interpretability and training efficiency [SOURCE-1].

Prior evaluation methodology studies recommend always reporting a simple baseline such as a majority-class or random predictor to contextualize the absolute performance of any learned classifier, as metric values in isolation are difficult to interpret [SOURCE-2].


## Proposed Method

Linear models form a foundational family of classification methods that remain effective on low-dimensional structured data such as the Iris dataset [SOURCE-1].

Logistic regression extends naturally to the multiclass setting through the softmax (multinomial) formulation, which models the probability of each class simultaneously [SOURCE-1].

Balanced accuracy is defined as the macro-averaged per-class recall, making it suitable for multiclass evaluation where each class contributes equally to the score [SOURCE-2].

We adopt L2 regularization—also referred to as ridge regularization—because it uniformly shrinks all coefficient magnitudes toward zero without inducing exact sparsity [SOURCE-1].

We select L2 over L1 regularization because all four morphological features in the Iris dataset are known to carry discriminative signal, making sparsity-inducing penalties potentially counterproductive [SOURCE-1].

We formulate Iris species classification as a multiclass L2-penalized logistic regression problem.

The objective function minimizes the negative log-likelihood of the multinomial logistic model plus an L2 penalty term scaled by the inverse regularization strength C.

We hypothesize that the L2 penalty may reduce overfitting by constraining the magnitude of learned coefficients.

The model is implemented using scikit-learn's LogisticRegression class with penalty='l2'.

The multinomial option is enabled so that the softmax formulation is used for multiclass probability estimation rather than a one-vs-rest decomposition.

Model training uses the default solver configuration provided by scikit-learn for L2-regularized logistic regression.

The regularization strength parameter C is kept at its default value without explicit hyperparameter tuning.

No feature engineering, scaling, or dimensionality reduction is applied; the four raw Iris features—sepal length, sepal width, petal length, and petal width—are used directly as model inputs.

We use the raw features without preprocessing because the Iris features are measured on comparable continuous scales and each is known to contribute discriminative information [SOURCE-1].

A majority-class predictor serves as the baseline comparison model.

The majority-class predictor assigns the most frequent class label from the training data to every test instance, regardless of input features.

We hypothesize that we expect the L2-regularized logistic regression model to substantially outperform the majority-class baseline in terms of balanced accuracy.

Balanced accuracy is adopted as the primary evaluation metric for comparing the regularized model against the baseline [SOURCE-2].

Balanced accuracy is selected as the primary metric because it weights per-class recall equally, providing a fair assessment across all three Iris species [SOURCE-2].

ROC-AUC is additionally reported as a secondary metric to characterize the model's class-separation quality [SOURCE-2].


## Evaluation Plan

We evaluate on the Iris dataset, a standard multiclass classification benchmark widely used in the linear classification literature [SOURCE-1]. The dataset comprises 150 samples across three species—Setosa, Versicolor, and Virginica—with four continuous features (sepal length, sepal width, petal length, and petal width).

Iris is well-suited for evaluating linear models because the classes are largely linearly separable, with the notable exception of partial overlap between Versicolor and Virginica, which provides a meaningful test of a classifier's discriminative ability at class boundaries [SOURCE-1].

Following established practice in multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary evaluation metric. Balanced accuracy computes the arithmetic mean of per-class recall, making it robust to class imbalance and ensuring that performance on each individual class is captured rather than being masked by aggregate accuracy.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to quantify the model's ranking ability across decision thresholds [SOURCE-2].

Our experimental design comprises two models evaluated under identical conditions. The primary model is L2-penalized (ridge) logistic regression, configured with the default regularization strength and optimized via a quasi-Newton solver [SOURCE-1].

L2 regularization is selected over L1 because the Iris feature set is compact (four features) and all features carry known discriminative information; sparsity-inducing penalties are unnecessary in this regime and risk discarding useful signal [SOURCE-1].

The baseline is a majority-class predictor that assigns every test sample to the most frequent class observed in the training set. This baseline establishes a performance floor; any meaningful classifier must substantially exceed it.

Both models are evaluated using stratified train-test splits to preserve class proportions across partitions. We report metrics computed on the held-out test partition [SOURCE-2].

Our results show that the L2-regularized logistic regression model achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973, substantially exceeding the majority-class baseline's balanced accuracy of [RESULT-2] balanced_accuracy = 0.500.

The model also achieves a ROC-AUC of [RESULT-3] ROC-AUC = 0.998, indicating near-perfect ranking ability across decision thresholds.

We hypothesize that the residual misclassification (approximately 2.7 percentage points below perfect balanced accuracy) is primarily attributable to the known morphological overlap between Versicolor and Virginica samples, rather than to model capacity limitations [SOURCE-1].

We hypothesize that L2-penalized logistic regression will outperform an L1-penalized variant on Iris, because the dataset's four features are all informative and L2 regularization retains all coefficients rather than zeroing out discriminative dimensions [SOURCE-1].


## Discussion and Future Work

Our results show that L2-regularized logistic regression achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the Iris classification task, representing near-perfect discrimination across the three species.

The majority-class baseline attains only [RESULT-2] balanced_accuracy = 0.500, confirming that the dataset's class distribution does not trivialize the task and that our model's performance reflects genuine learned discriminative structure.

The ROC-AUC of [RESULT-3] ROC-AUC = 0.998 further corroborates strong ranking performance, indicating that the predicted class probabilities are well-calibrated relative to true labels.

The L2 penalty used in this study shrinks all feature coefficients uniformly toward zero without eliminating any entirely, which preserves all four sepal and petal measurements in the decision boundary.

Linear classification methods remain competitive on well-separated, low-dimensional benchmarks such as Iris, and our findings are consistent with prior surveys documenting strong logistic regression performance on this dataset [SOURCE-1].

Balanced accuracy is an appropriate primary metric for multiclass evaluation because it averages per-class recall and is robust to mild class imbalances [SOURCE-2].

We hypothesize that replacing the L2 penalty with an L1 penalty (lasso) would yield implicit feature selection by driving irrelevant feature weights to exactly zero, thereby producing a sparser and more interpretable model without substantial loss in balanced accuracy [SOURCE-1].

We hypothesize that petal length and petal width will retain non-zero coefficients under L1 regularization, while one or both sepal measurements may be driven to zero, reflecting the well-documented stronger discriminative power of petal features for Iris species separation.

We hypothesize that the sparse L1 model would maintain a balanced accuracy within a narrow margin of the L2 model's performance, on the order of one to three percentage points, because the Iris dataset's strong class separability suggests that a subset of features may suffice [RESULT-1].

We aim to if confirmed, the L1 approach would be expected to contribute a more interpretable classification pipeline that identifies the minimally sufficient feature set for Iris classification, which could inform feature collection strategies in botanical and related domains.

We hypothesize that we further hypothesize that combining L1 and L2 penalties via elastic net regularization could balance sparsity and coefficient stability, potentially offering a middle ground that retains predictive performance while yielding partial feature selection [SOURCE-1].

We aim to a systematic comparison of L1, L2, and elastic net regularization across multiple random train-test splits would be expected to clarify the robustness of each penalty's performance and reveal whether observed differences are statistically significant.


## Conclusion

We applied L2-penalized (ridge) logistic regression to the Iris multiclass classification task, using balanced accuracy as the primary evaluation metric and a majority-class predictor as baseline [SOURCE-1] [SOURCE-2].

Our results show that the ridge-regularized model achieves [RESULT-1] balanced_accuracy = 0.973, a substantial improvement over the majority-class baseline's [RESULT-2] balanced_accuracy = 0.500.

The model also demonstrates excellent discriminative ability, achieving an ROC-AUC of [RESULT-3] = 0.998, indicating near-perfect class separation on Iris.

We aim to this work aims to establish ridge-regularized logistic regression as a strong, interpretable baseline for Iris classification, demonstrating that a simple linear model with L2 regularization can approach ceiling performance without feature selection or nonlinear methods [SOURCE-1].

We aim to this work aims to show that well-regularized linear models remain competitive for structured tabular benchmarks like Iris, motivating careful evaluation of when more complex architectures are genuinely necessary [SOURCE-1] [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
