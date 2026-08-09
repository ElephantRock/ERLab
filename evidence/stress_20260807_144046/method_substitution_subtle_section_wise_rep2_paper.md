# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression is a foundational linear classification method widely employed for both binary and multiclass problems across machine learning applications [SOURCE-1].

Regularization techniques such as L2 (ridge) penalties are commonly incorporated into logistic regression to shrink coefficient magnitudes, thereby controlling model complexity and improving generalization [SOURCE-1].

The Iris dataset—a standard multiclass benchmark comprising 150 samples across three species measured on four features—is widely used to evaluate and compare classification methods [SOURCE-1].

We apply L2-regularized (ridge) logistic regression for multiclass classification on the Iris dataset, wherein the L2 penalty term uniformly shrinks coefficient magnitudes to mitigate overfitting without enforcing strict sparsity.

We evaluate the model against a majority-class baseline using balanced accuracy as the primary metric, which equally weights per-class recall and is appropriate for potentially imbalanced multiclass settings [SOURCE-2].

We aim to l2-regularized logistic regression will substantially outperform the majority-class baseline in balanced accuracy on the Iris classification task, demonstrating that a properly regularized linear model can achieve strong multiclass discrimination on structured data.


## Introduction

Linear classification methods form the foundation of supervised machine learning, with logistic regression remaining one of the most widely adopted and well-understood approaches for both binary and multiclass classification problems due to its simplicity, interpretability, and strong theoretical foundations [SOURCE-1].

The Iris dataset, comprising 150 samples across three iris species—Setosa, Versicolor, and Virginica—with four morphological features each (sepal length, sepal width, petal length, and petal width), has served as a standard benchmark for evaluating classification algorithms for decades [SOURCE-1].

Feature selection plays a critical role in machine learning model development, as it identifies the most relevant predictors, reduces model complexity, improves interpretability, and can enhance generalization performance by mitigating overfitting [SOURCE-1].

Regularization techniques are widely employed in logistic regression to prevent overfitting and improve generalization, with L2 regularization (ridge) being the most commonly used approach, which adds a penalty term proportional to the squared magnitude of the coefficient vector [SOURCE-1].

Standard logistic regression with L2 regularization shrinks all coefficient magnitudes toward zero uniformly but does not perform feature selection, as coefficients are rarely driven to exactly zero, meaning all features remain in the model regardless of their relevance [SOURCE-1].

The retention of all features in L2-regularized models becomes problematic when the input space contains irrelevant or redundant predictors, as these can introduce noise, increase variance, and complicate model interpretation without contributing meaningfully to predictive accuracy [SOURCE-1].

Traditional approaches to feature selection, such as filter methods, wrapper methods, and embedded methods applied as separate preprocessing steps, are decoupled from the model training process, leading to potential suboptimality in feature subset selection and increased computational cost [SOURCE-1].

In multiclass classification, model evaluation must account for potential class imbalance, and metrics such as balanced accuracy—which computes the average of per-class recall—provide a more informative assessment than raw accuracy when class distributions are uneven [SOURCE-2].

A majority-class predictor, which assigns all samples to the most frequent class, serves as a minimal baseline for classification tasks, representing the performance achievable without leveraging any feature information [SOURCE-2].

The assessment of classification models in multiclass settings benefits from multiple complementary metrics, including balanced accuracy for overall performance and area under the receiver operating characteristic curve (ROC-AUC) for ranking quality [SOURCE-2].

L1-regularized logistic regression, commonly known as the lasso, addresses the feature selection limitation of standard regularized models by introducing a penalty term proportional to the absolute values of the coefficients, which induces sparsity in the solution by driving irrelevant feature weights to exactly zero [SOURCE-1].

The convex nature of the L1-penalized logistic regression objective ensures that global optima can be found efficiently, and coordinate descent algorithms such as those implemented in the liblinear solver have been demonstrated to solve this optimization problem effectively for datasets of moderate dimensionality [SOURCE-1].

By performing implicit feature selection during model fitting, L1-penalized logistic regression produces sparse models that can simultaneously achieve competitive predictive performance and enhanced interpretability, directly addressing the limitations of L2-regularized approaches that retain all features [SOURCE-1].

The choice of solver is critical when applying L1-regularized logistic regression, as not all optimization algorithms can handle the non-differentiability of the L1 penalty at zero; coordinate descent methods, such as liblinear, are specifically designed to accommodate this property [SOURCE-1].

For datasets such as Iris, where biological features may exhibit varying levels of discriminative power across species, L1 regularization can reveal which morphological measurements contribute most to classification, providing both practical model simplification and domain-specific insight [SOURCE-1].

The L1 penalty can be understood through the lens of Bayesian inference as imposing a Laplacian prior on the coefficient vector, providing a principled probabilistic foundation for the sparsity-inducing behavior that distinguishes the lasso from ridge regression [SOURCE-1].

The evaluation of feature selection methods on well-understood benchmark datasets is essential for validating their effectiveness, as the known structure of such datasets allows researchers to assess whether the selected features align with domain expectations and prior biological knowledge [SOURCE-1].

Many widely used implementations of logistic regression default to L2 regularization, which, while effective for generalization in many settings, does not provide the sparse solutions that facilitate feature importance assessment and model simplification [SOURCE-1].

The integration of feature selection and classification into a single unified optimization framework, as achieved by the lasso, represents a principled approach that avoids the pitfalls of separate feature selection stages and leverages the full dataset during both selection and model fitting [SOURCE-1].


## Related Work

Logistic regression has long been established as a foundational linear classification method, widely adopted for both binary and multiclass problems due to its simplicity, interpretability, and strong theoretical guarantees regarding maximum likelihood estimation [SOURCE-1].

Regularization techniques, particularly L1 (Lasso) and L2 (Ridge) penalties, have been extensively studied as mechanisms to prevent overfitting and improve generalization in linear models by constraining the norm of the coefficient vector [SOURCE-1].

The L1 penalty induces sparsity in model coefficients by driving irrelevant feature weights to exactly zero, which effectively performs implicit feature selection and enhances model interpretability, in contrast to the L2 penalty which shrinks coefficients uniformly but rarely eliminates them entirely [SOURCE-1].

The Iris dataset has been a standard benchmark in the machine learning literature for evaluating linear classifiers, as its four-dimensional feature space and three-class structure provide a tractable yet meaningful test of discriminative ability [SOURCE-1].

Balanced accuracy has been proposed as a more robust evaluation metric than standard accuracy for classification tasks, as it computes the arithmetic mean of per-class recall and is therefore insensitive to class imbalance [SOURCE-2].

ROC-AUC is widely employed as a threshold-independent measure of a classifier's ability to discriminate between classes, summarizing performance across all possible decision thresholds [SOURCE-2].

Multiclass classification introduces additional complexity over binary settings, requiring strategies such as one-vs-rest or multinomial formulations, and demanding evaluation protocols that account for per-class performance variation [SOURCE-2].

Despite the well-documented advantages of L1-regularized logistic regression for feature selection, there remains a lack of systematic comparison between L1 and L2 penalties on standard benchmark datasets using balanced accuracy as the primary criterion [SOURCE-1].

Standard accuracy, while commonly reported, has been shown to be a misleading metric in multiclass settings because it can mask poor performance on individual classes and does not account for the potentially unequal costs of different misclassification types [SOURCE-2].

Linear classification methods, including regularized logistic regression, are fundamentally limited in their ability to capture complex nonlinear decision boundaries, which can constrain their performance on datasets where classes are not linearly separable [SOURCE-1].

Prior surveys of linear classification note that the choice between L1 and L2 regularization is often guided by heuristics rather than principled empirical comparison, leaving practitioners without clear guidance on which penalty is preferable for a given dataset [SOURCE-1].

Many existing evaluation studies of multiclass classifiers focus predominantly on aggregate metrics, leaving an insufficient understanding of how regularization choices affect per-class discrimination as measured by metrics such as ROC-AUC [SOURCE-2].

The majority-class baseline, which assigns all instances to the most frequent class, has been established as the simplest reference point for classification tasks; failing to substantially exceed this baseline indicates that a model provides little discriminative value [SOURCE-2].

While the Iris dataset is well-studied, prior work has noted that certain species pairs within the dataset exhibit overlapping feature distributions, making complete linear separation difficult and thus testing the limits of linear classifiers [SOURCE-1].


## Proposed Method

Logistic regression is among the most widely used linear classification methods, offering a favorable balance between interpretability and predictive performance for multiclass problems [SOURCE-1].

L2 regularization (ridge penalty) controls model complexity by shrinking coefficient magnitudes toward zero, which is motivated by the need to mitigate overfitting when training data is limited [SOURCE-1].

We propose L2-regularized logistic regression (ridge) for multiclass classification on the Iris dataset.

We implement the model using scikit-learn's LogisticRegression with penalty='l2' and the lbfgs solver, configured for multinomial multiclass classification.

We hypothesize that the L2 penalty will help the model generalize across the three Iris species by constraining coefficient magnitudes and reducing sensitivity to individual training examples.

We hypothesize that L2-regularized logistic regression will substantially outperform a majority-class baseline in terms of balanced accuracy on Iris.

We evaluate our approach on the Iris dataset, a standard multiclass classification benchmark comprising 150 samples across three species with four morphological features each [SOURCE-1].

We adopt balanced accuracy as the primary evaluation metric, as it accounts for per-class performance by averaging recall across all classes [SOURCE-2].

Balanced accuracy is particularly appropriate for multiclass settings where simple accuracy can mask poor performance on individual classes [SOURCE-2].

We compare the proposed model against a majority-class predictor as the baseline.

We additionally report ROC-AUC as a secondary metric to provide a threshold-independent view of discriminative performance [SOURCE-2].


## Evaluation Plan

We use the Iris dataset [SOURCE-1], a standard multiclass classification benchmark comprising 150 samples across three species, to evaluate our logistic regression model.

Following [SOURCE-2], we use balanced accuracy as the primary evaluation metric to ensure fair assessment across all classes, mitigating potential bias from class frequency differences.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) following [SOURCE-2] to assess the model's discriminative ability across thresholds.

Our experimental protocol compares an L2-regularized (ridge) logistic regression model against a majority-class baseline predictor on the Iris dataset [SOURCE-1].

We use an L2 penalty (ridge regularization) rather than L1 because the Iris dataset contains only four features, limiting the expected benefit of the sparsity-inducing L1 penalty while ridge regularization offers stable coefficient shrinkage in low-dimensional settings [SOURCE-1].

We hypothesize that the L2-regularized logistic regression model will substantially exceed the majority-class baseline on balanced accuracy, as the four morphological features in Iris are known to carry strong discriminative signal across species [SOURCE-1].

We hypothesize that the model will achieve high ROC-AUC (above 0.95), reflecting strong class separation under the logistic decision boundary [SOURCE-2].

Our results show that the L2-regularized logistic regression model achieves a balanced accuracy of 0.973 on the Iris dataset [RESULT-1], substantially outperforming the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

The model achieves an ROC-AUC of 0.998 [RESULT-3], confirming strong discriminative performance across decision thresholds.


## Discussion and Future Work

Our results demonstrate that L2-regularized logistic regression achieves strong multiclass classification performance on the Iris dataset, with a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3] [SOURCE-2].

The model substantially outperforms the majority-class baseline, which yields a balanced accuracy of only 0.500 [RESULT-2], confirming that logistic regression learns meaningful discriminative patterns rather than defaulting to the most frequent class [SOURCE-1].

The near-perfect ROC-AUC of 0.998 [RESULT-3] suggests the model produces well-separated probability estimates across decision thresholds, indicating robust decision boundaries rather than overfitting to a single threshold [SOURCE-2].

The Iris dataset, while a standard benchmark, is relatively small (150 samples) and low-dimensional (four features), and its classes are largely linearly separable—conditions under which even straightforward linear models can achieve near-perfect accuracy [SOURCE-1].

L2-regularized logistic regression shrinks all coefficients uniformly but does not perform feature selection; all four features retain non-zero weights regardless of their individual discriminative value, which may limit interpretability [SOURCE-1].

We hypothesize that L1-regularized logistic regression (Lasso) could achieve comparable classification accuracy on Iris while simultaneously performing implicit feature selection by driving irrelevant feature weights to zero, thereby offering a more interpretable model without sacrificing predictive performance [SOURCE-1].

We hypothesize that the strong performance of L2 logistic regression observed on Iris will not fully transfer to datasets with greater class imbalance, higher feature dimensionality, or nonlinear class boundaries, and that evaluating on datasets such as Digits, Wine, or Breast Cancer Wisconsin would reveal the boundary conditions of penalized linear models [SOURCE-1].

We hypothesize that elastic net regularization—a convex combination of L1 and L2 penalties—may provide a superior trade-off between feature selection and coefficient stability, particularly on datasets where some features are redundant and others are individually informative [SOURCE-1].

We aim to the planned investigations comparing penalty types, datasets, and regularization strategies will yield a practical guideline for selecting penalty types and regularization strengths based on dataset characteristics such as dimensionality, class balance, and feature redundancy [SOURCE-1] [SOURCE-2].


## Conclusion

Logistic regression with L2 regularization achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the Iris classification task, substantially outperforming the majority-class baseline of [RESULT-2] balanced_accuracy = 0.500 [SOURCE-1] [SOURCE-2].

The model also achieves an ROC-AUC of [RESULT-3] ROC-AUC = 0.998, indicating strong discriminative performance across classes [SOURCE-2].

These results demonstrate that ridge-regularized logistic regression is a strong, simple baseline for structured tabular classification tasks like Iris [SOURCE-1].

We aim to this work aims to establish a reliable empirical reference point for L2-regularized logistic regression on a canonical dataset, motivating future comparisons with sparse alternatives such as L1-penalized models.

We aim to future work extending this evaluation to L1-regularized logistic regression may reveal whether implicit feature selection yields comparable accuracy while improving model interpretability [SOURCE-1].


## References

[Generated from 2 source papers — see proposal for full bibliography]
