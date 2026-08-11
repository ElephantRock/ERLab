# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression is a foundational linear classification method widely used in machine learning for discriminative modeling in both binary and multiclass settings [SOURCE-1].

Regularization is critical for controlling model complexity and preventing overfitting, particularly in scenarios where the number of features is moderate relative to the number of training samples [SOURCE-1].

We apply L2-penalized (ridge) logistic regression for multiclass classification on the Iris dataset, where the L2 penalty term controls overfitting by shrinking the squared magnitude of all feature coefficients simultaneously, yielding smoother and more stable decision boundaries without driving any weight exactly to zero [SOURCE-1].

We aim to demonstrate that L2-regularized logistic regression achieves high balanced accuracy on the Iris classification task, substantially outperforming a majority-class baseline predictor.

We aim to the L2 regularization mechanism will provide robust generalization on the Iris dataset by balancing goodness-of-fit with coefficient shrinkage, limiting the influence of any single feature on the decision boundary.


## Introduction

Linear classification methods have long served as the backbone of supervised machine learning, with logistic regression standing out as one of the most widely adopted techniques for both binary and multiclass classification problems [SOURCE-1].

The Iris dataset, comprising 150 samples from three Iris species described by four morphological features (sepal length, sepal width, petal length, and petal width), has served as a standard benchmark for evaluating classification algorithms since its introduction by Fisher [SOURCE-1].

Standard logistic regression without regularization is susceptible to overfitting, particularly when the number of predictor variables is large relative to the number of observations or when features are highly correlated [SOURCE-1].

In high-dimensional settings, the maximum likelihood estimator can produce unstable coefficient estimates with large magnitudes, leading to models that fit the training data well but generalize poorly to unseen data [SOURCE-1].

Manual or heuristic approaches to feature selection, such as filter methods that rank features by univariate statistics or wrapper methods that search over subsets, are often labor-intensive and may fail to account for multivariate interactions among predictors [SOURCE-1].

Filter methods evaluate each feature independently and can miss features that are only predictive in combination with others, while wrapper methods are computationally expensive and prone to overfitting the selection criterion to the training data [SOURCE-1].

Regularization offers a principled alternative to manual feature selection by augmenting the loss function with a penalty term that controls model complexity, with L1 (Lasso) and L2 (Ridge) penalties being the two most common forms in logistic regression [SOURCE-1].

The L1 penalty induces sparsity by driving some coefficients exactly to zero, effectively performing feature selection as part of model training, while the L2 penalty shrinks all coefficients uniformly toward zero and is suitable when all features are expected to carry some predictive signal [SOURCE-1].

L2 regularization distributes shrinkage across all coefficients and tends to perform better when many features contribute weakly to the prediction or when features are highly correlated, as it does not arbitrarily select one feature from a correlated group [SOURCE-1].

In the context of botanical classification, where morphological features such as petal and sepal dimensions may be developmentally correlated, both L1 and L2 penalties offer complementary advantages that warrant empirical comparison [SOURCE-1].

Accuracy, the most commonly reported classification metric, can be misleading when class distributions are uneven, as it may be dominated by the majority class [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, addresses class imbalance by giving equal weight to each class regardless of its frequency, and ROC-AUC offers a threshold-independent measure of discriminative ability [SOURCE-2].

The structured nature of the Iris dataset—four continuous features, three balanced classes—makes it well-suited for isolating the effects of regularization in a controlled setting [SOURCE-1].


## Related Work

Linear classification methods have long been foundational tools in machine learning, with logistic regression being one of the most widely studied and applied techniques for both binary and multiclass problems [SOURCE-1].

Logistic regression models the posterior class probabilities through a linear combination of features transformed by a softmax function, making it particularly suitable for multiclass settings such as the three-class Iris classification task [SOURCE-1].

Regularization techniques, including L1 (Lasso) and L2 (Ridge) penalties, have been extensively incorporated into logistic regression to control model complexity and mitigate overfitting, especially in scenarios with limited training samples [SOURCE-1].

L2-regularized logistic regression, also known as ridge logistic regression, shrinks coefficient magnitudes uniformly without inducing sparsity, thereby retaining all features in the model while reducing variance [SOURCE-1].

Linear classifiers such as logistic regression have demonstrated strong performance on benchmark datasets including Iris, where feature spaces are low-dimensional and classes are largely linearly separable [SOURCE-1].

Despite the general effectiveness of linear methods, standard logistic regression without regularization can be sensitive to multicollinearity among features, which is a known concern in botanical datasets where morphological measurements may be correlated [SOURCE-1].

Prior surveys note that the choice of solver algorithm, such as liblinear versus lbfgs, can affect convergence behavior and runtime for regularized logistic regression, particularly when comparing L1 and L2 penalty types across different implementations [SOURCE-1].

The evaluation of multiclass classifiers requires metrics that account for class imbalance and multiclass structure, as standard accuracy can be misleading when class distributions are skewed or when per-class performance varies significantly [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more informative metric than raw accuracy for multiclass classification tasks, as it equally weights the performance on each class regardless of its frequency [SOURCE-2].

A majority-class baseline, which predicts the most frequent class for all instances, yields a balanced accuracy of 0.500 in balanced three-class settings and serves as a critical lower-bound reference point for evaluating multiclass classifiers [SOURCE-2].

ROC-AUC has been extended to multiclass settings through strategies such as one-vs-rest averaging, providing a threshold-independent measure of discriminative ability that complements balanced accuracy in characterizing classifier performance [SOURCE-2].

Prior work has noted that while ROC-AUC provides a useful summary of ranking performance across thresholds, it can obscure per-class weaknesses in multiclass problems, potentially overstating performance when one class is perfectly separated while others are not [SOURCE-2].

Prior surveys of linear classification have noted that comparisons across regularization strategies are often limited to binary classification tasks, leaving a gap in systematic evaluations of L2-regularized logistic regression on well-structured multiclass benchmarks such as Iris [SOURCE-1].

Existing evaluation frameworks frequently report only raw accuracy for the Iris dataset, which can mask the distinction between strong and weak classifiers, particularly when balanced accuracy and ROC-AUC would reveal more nuanced performance differences [SOURCE-2].

The interaction between regularization strength and multiclass classification performance remains insufficiently characterized in prior literature, particularly regarding how L2 penalty selection influences balanced accuracy on low-dimensional, near-linearly-separable datasets [SOURCE-1].

Survey work has emphasized that the liblinear solver, originally designed for L1-regularized logistic regression, is also applicable to L2-penalized variants, though systematic benchmarking of solver-penalty combinations on canonical datasets like Iris remains limited [SOURCE-1].

Evaluation metric studies have shown that balanced accuracy and ROC-AUC, while both valuable, can diverge substantially in multiclass settings, particularly when one class is more difficult to separate than others, underscoring the importance of reporting multiple complementary metrics [SOURCE-2].

Standard benchmarks for Iris classification frequently lack majority-class baselines, making it difficult to contextualize the practical improvement offered by regularized logistic regression over trivial prediction strategies [SOURCE-2].


## Proposed Method

Logistic regression models the posterior probability of class membership as a logistic (sigmoid) function of a weighted linear combination of input features, making it a foundational linear classification method [SOURCE-1].

For multiclass problems such as Iris (three species), logistic regression is extended via a multinomial (softmax) formulation that jointly models all class probabilities [SOURCE-1].

We adopt L2-penalized (ridge) logistic regression rather than unregularized logistic regression because the Iris dataset's botanical measurements (sepal and petal dimensions) are correlated, which can produce unstable coefficient estimates in unregularized models [SOURCE-1].

We specifically choose L2 (ridge) over L1 (lasso) regularization because the Iris dataset contains only four features—all of which carry known discriminative signal for species separation—making implicit feature selection through sparsity unnecessary [SOURCE-1].

We propose an L2-penalized multinomial logistic regression model for classifying the Iris dataset into its three species: Iris setosa, Iris versicolor, and Iris virginica [SOURCE-1].

The model minimizes the following regularized objective function: min_{w} -log L(w) + λ ||w||²₂, where -log L(w) is the negative log-likelihood of the multinomial logistic model, λ is the regularization strength, and ||w||²₂ is the squared L2 norm of the weight vector [SOURCE-1].

We hypothesize that L2 regularization may reduce overfitting on the Iris dataset by constraining coefficient magnitudes, particularly given the modest sample size of 150 observations.

We hypothesize that we further hypothesize that this L2-regularized model may improve generalization over unregularized logistic regression by distributing weight across correlated features rather than inflating individual coefficients [SOURCE-1].

The model is fit using the L-BFGS quasi-Newton optimization algorithm, which efficiently handles smooth L2-penalized objectives and converges reliably for low-dimensional problems such as Iris [SOURCE-1].

Balanced accuracy is selected as the primary evaluation metric, defined as the arithmetic mean of per-class recall, which fairly evaluates classifiers when class distributions are uneven [SOURCE-2].

We use a majority-class predictor—always predicting the most frequent class—as the baseline, which yields balanced accuracy = 0.500 [RESULT-2] [SOURCE-2].

We hypothesize that the L2-regularized logistic regression model may achieve balanced accuracy substantially exceeding the majority-class baseline of 0.500.

ROC-AUC is additionally reported as a threshold-independent measure of class separability, complementing the balanced accuracy assessment [SOURCE-2].

We hypothesize that we anticipate that the proposed model may produce a high ROC-AUC value, reflecting strong discrimination among the three Iris species.

Our results show that the proposed L2-penalized logistic regression achieves balanced accuracy = 0.973 [RESULT-1] and ROC-AUC = 0.998 [RESULT-3], substantially exceeding the majority-class baseline of 0.500 [RESULT-2] [SOURCE-2].


## Evaluation Plan

We evaluate our approach on the Iris dataset [SOURCE-1], a standard multiclass classification benchmark comprising 150 samples across three Iris species with four morphological features (sepal length, sepal width, petal length, and petal width).

Following established guidelines for multiclass evaluation [SOURCE-2], we employ balanced accuracy as our primary metric, computed as the arithmetic mean of per-class recall to ensure robustness against class imbalance.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) [SOURCE-2], which quantifies the model's discriminative ability across varying decision thresholds for multiclass settings.

Our experimental protocol applies L2-penalized (ridge) logistic regression to the Iris multiclass classification task, comparing against a majority-class predictor baseline that always predicts the most frequent class [SOURCE-1].

The design rationale for this protocol is twofold: first, the Iris dataset is a well-characterized benchmark with known class-separability properties suitable for validating linear classifiers [SOURCE-1]; second, balanced accuracy ensures fair assessment across all three classes, unlike raw accuracy which can be inflated by majority-class predictions [SOURCE-2].

Our results show that the L2-penalized logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset [RESULT-1], demonstrating strong multiclass discrimination capability.

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], consistent with the expectation for a dataset with three roughly balanced classes.

The ROC-AUC of 0.998 [RESULT-3] confirms near-perfect pairwise class separability under the L2-penalized model.

We hypothesize that L2 regularization contributes to generalization by preventing overfitting on the Iris dataset, though the inherent class separability of the dataset may limit the observable impact of regularization strength.


## Discussion and Future Work

L2-penalized logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset, substantially outperforming the majority-class baseline (balanced accuracy = 0.500) [RESULT-1] [RESULT-2].

The ROC-AUC of 0.998 indicates near-perfect class discrimination across the three Iris species [RESULT-3].

These findings are consistent with prior characterizations of the Iris dataset as largely linearly separable, particularly for the Setosa class [SOURCE-1].

The L2 penalty shrinks all coefficient magnitudes toward zero without inducing exact sparsity, so all four features retain non-zero weights in the trained model, offering limited insight into which features are most discriminative [SOURCE-1].

Balanced accuracy was selected as the primary metric to account for potential class imbalance and to ensure meaningful per-class evaluation [SOURCE-2].

We hypothesize that replacing the L2 penalty with an L1 penalty (Lasso) could yield comparable balanced accuracy while producing a sparse solution that enables implicit feature selection and improves model interpretability.

We hypothesize that an elastic net penalty combining L1 and L2 regularization might retain the coefficient stability of ridge regression while benefiting from sparsity-inducing feature selection, particularly in larger botanical datasets with correlated features.

We hypothesize that given the near-ceiling performance observed, more complex non-linear models such as kernel SVMs or gradient-boosted trees will not yield materially higher balanced accuracy on Iris relative to their added complexity [RESULT-1].

We hypothesize that the strong classification results obtained on Iris may not generalize to higher-dimensional botanical datasets with greater class overlap and more species.

We hypothesize that adopting k-fold cross-validation instead of a single train-test split may reveal greater variance in balanced accuracy than the point estimate of 0.973 suggests [RESULT-1].

We aim to extending the balanced-accuracy evaluation framework to imbalanced multiclass botanical classification tasks will demonstrate both the robustness and the boundaries of regularized logistic regression in realistic field-collected settings.


## Conclusion

Classification of botanical specimens such as the Iris dataset is a canonical benchmark for evaluating linear classification methods, where the choice of regularization and evaluation protocol significantly influences reported performance [SOURCE-1].

Our results show that L2-penalized logistic regression (ridge) achieved a balanced accuracy of 0.973 on the Iris classification task [RESULT-1], compared to a majority-class baseline balanced accuracy of 0.500 [RESULT-2], indicating that the model learns discriminative class boundaries well beyond chance [SOURCE-2].

The model further demonstrated strong multiclass discrimination, achieving an ROC-AUC of 0.998 [RESULT-3], suggesting robust separation across the three Iris classes [SOURCE-2].

We aim to this work aims to provide a reproducible baseline for penalized logistic regression on the Iris dataset, establishing balanced accuracy and ROC-AUC benchmarks against a majority-class predictor that future investigations involving alternative regularization strategies (e.g., L1 sparsity-inducing penalties) can build upon [SOURCE-1].

We aim to this work aims to demonstrate that L2-regularized logistic regression, even without explicit feature selection, can achieve near-perfect classification on small, low-dimensional botanical datasets, which may inform methodological choices in applied plant-science classification tasks [SOURCE-1].


## References

[Generated from 2 source papers — see proposal for full bibliography]
