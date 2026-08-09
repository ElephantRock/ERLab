# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression remains one of the most widely used linear methods for classification, offering a favorable trade-off between interpretability and predictive performance across diverse domains [SOURCE-1].

The Iris dataset, comprising 150 samples across three species with four morphological features, is a standard benchmark for evaluating multiclass classification algorithms.

The L1 penalty induces sparsity by driving irrelevant feature weights to exactly zero, thereby performing implicit feature selection within the classification model itself [SOURCE-1].

We propose L1-penalized logistic regression (lasso) with the liblinear solver for multiclass classification on the Iris dataset, jointly optimizing classification accuracy and implicit feature selection.

We aim to the L1-penalized approach will achieve competitive balanced accuracy on the Iris dataset while yielding a sparse, interpretable set of selected features.

We aim to demonstrate that sparsity-inducing regularization can reduce reliance on all four input features without substantial degradation in multiclass discrimination.


## Introduction

Linear classification methods have long been a cornerstone of supervised learning, offering a favorable balance between interpretability, computational efficiency, and predictive performance [SOURCE-1].

Logistic regression extends naturally to multiclass settings through the softmax formulation, providing probabilistic outputs and linear decision boundaries that are straightforward to interpret [SOURCE-1].

The Iris dataset, comprising four continuous features—sepal length, sepal width, petal length, and petal width—measured across three species, has served as a foundational benchmark for evaluating classification algorithms for decades [SOURCE-1].

Balanced accuracy, defined as the average of per-class recall, provides a more informative assessment than raw accuracy for multiclass classification, as it equally weights performance across all classes [SOURCE-2].

Metrics such as the area under the receiver operating characteristic curve (ROC-AUC) complement accuracy-based measures by capturing the ranking quality of probabilistic predictions across classes [SOURCE-2].

Unregularized logistic regression can yield unstable coefficient estimates when features are correlated, as the optimization landscape becomes flat along directions corresponding to correlated feature combinations, allowing coefficients to grow without bound [SOURCE-1].

Unregularized logistic regression can overfit the training data when features are numerous relative to observations or when classes are not perfectly linearly separable, producing decision boundaries that generalize poorly to unseen samples [SOURCE-1].

Majority-class predictors assign all samples to the most frequent class and, on balanced multiclass problems such as Iris, achieve only chance-level balanced accuracy, failing to leverage any discriminative feature information [SOURCE-2].

L2 regularization, analogous to ridge regression in the linear least-squares setting, addresses coefficient instability by adding a penalty proportional to the squared L2 norm of the coefficient vector, thereby constraining coefficient magnitudes and reducing variance [SOURCE-1].

L2-penalized maximum likelihood estimation retains the convexity of the unregularized logistic regression objective, ensuring that the global optimum can be found efficiently with standard solvers such as liblinear [SOURCE-1].

The extension of L2-regularized logistic regression to multiclass settings via the softmax function is well established and preserves the convexity and differentiability properties of the binary formulation [SOURCE-1].

By constraining coefficient magnitudes, L2 regularization encourages the model to distribute discriminative weight across all available features rather than over-relying on any single predictor, which is advantageous when features collectively carry complementary class information [SOURCE-1].


## Related Work

Linear classification methods have long been foundational in supervised machine learning, offering interpretable decision boundaries and efficient training on structured data [SOURCE-1].

Logistic regression remains one of the most widely adopted linear classifiers, providing probabilistic outputs through the logistic function and supporting both binary and multinomial settings [SOURCE-1].

Regularization strategies, including L1 (lasso) and L2 (ridge) penalties, are routinely applied to logistic regression to control model complexity and mitigate overfitting, particularly on datasets with limited samples [SOURCE-1].

The Iris dataset has served as a canonical benchmark in the classification literature, frequently used to evaluate and compare the behavior of linear and nonlinear classifiers under controlled conditions [SOURCE-1].

Multiclass classification introduces additional complexity over binary settings, requiring either decomposition into multiple binary subproblems or direct multinomial formulations of the classifier [SOURCE-1].

Balanced accuracy has been recommended as a more informative metric than raw accuracy for classification tasks, as it averages per-class recall and is less sensitive to class imbalance [SOURCE-2].

ROC-AUC provides a threshold-independent measure of a classifier's ability to discriminate between classes and is commonly reported alongside accuracy-based metrics for comprehensive evaluation [SOURCE-2].

Majority-class baselines, which assign all instances to the most frequent class, are frequently used as lower-bound reference points to verify that a learned model extracts meaningful signal beyond class priors [SOURCE-2].

Unregularized logistic regression can be prone to overfitting and unstable coefficient estimates, especially when the number of features is large relative to the number of observations, motivating the use of explicit penalty terms [SOURCE-1].

Feature selection in linear classification has traditionally required separate preprocessing stages or wrapper methods, which can be computationally costly and may not leverage the model's own structure for selecting relevant variables [SOURCE-1].

Many prior evaluation studies of multiclass classifiers rely primarily on overall accuracy, which can obscure per-class performance differences and underrepresent the difficulty of minority classes [SOURCE-2].

Comparative evaluations of penalized logistic regression variants often focus on high-dimensional settings, leaving the behavior and relative benefits of L1 versus L2 regularization less thoroughly characterized on low-dimensional, well-studied benchmarks [SOURCE-1].

Simple baseline predictors such as majority-class classifiers are sometimes omitted from reported evaluations, making it difficult to assess whether a proposed model's performance reflects genuine discriminative learning rather than trivial class-frequency exploitation [SOURCE-2].


## Proposed Method

Logistic regression is a foundational linear classification method that models class-conditional probabilities through a logistic (sigmoid) function applied to a linear combination of input features [SOURCE-1].

For multiclass settings such as the Iris dataset, logistic regression is extended via the multinomial (softmax) formulation, which jointly optimizes K linear decision boundaries for K classes [SOURCE-1].

The Iris dataset comprises 150 samples across three species (setosa, versicolor, virginica), each with 50 instances and four continuous morphological features (sepal length, sepal width, petal length, petal width), making it a standard benchmark for evaluating linear classifiers [SOURCE-1].

L2 regularization (ridge penalty) penalizes the sum of squared coefficient magnitudes, encouraging the model to distribute weight across all features rather than relying heavily on any single predictor, which is appropriate when all features are expected to carry partial predictive signal [SOURCE-1].

We propose an L2-penalized logistic regression model for multiclass classification of the Iris dataset, implemented using scikit-learn's LogisticRegression with penalty='l2' and the default LBFGS solver.

We hypothesize that L2 regularization may reduce overfitting on the relatively small Iris dataset (n=150) by constraining coefficient magnitudes and thereby trading a small increase in bias for a reduction in variance [SOURCE-1].

The model is trained by minimizing the negative log-likelihood of the multinomial logistic loss augmented by the L2 penalty term: argmin_w sum_i [-log p(y_i | x_i, w)] + (1/C) * ||w||_2^2, where C is the inverse regularization strength [SOURCE-1].

We select the LBFGS quasi-Newton optimization algorithm, which supports multinomial loss with L2 penalties and converges reliably on small-to-medium datasets.

We set the inverse regularization strength to C=1.0, corresponding to a moderate level of regularization that balances fit and shrinkage.

We adopt a majority-class predictor as the baseline, which always predicts the most frequent class in the training set.

We hypothesize that we expect the L2-penalized logistic regression model to substantially outperform the majority-class baseline, since the latter ignores all feature information [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, is used as the primary evaluation metric because it is robust to class imbalance and equally weights each class [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) in a one-vs-rest macro-averaged formulation to capture the model's rank discrimination ability across classes [SOURCE-2].

We hypothesize that incorporating all four features under L2 shrinkage may yield higher balanced accuracy than relying on a subset, since petal and sepal measurements each contribute distinct discriminative information across Iris species [SOURCE-1].

The dataset is split using stratified sampling to preserve the equal class distribution in both training and test partitions [SOURCE-2].

We apply standard z-score normalization (zero mean, unit variance) to the input features prior to fitting the logistic regression model, ensuring that the L2 penalty operates on a comparable scale across all coefficients [SOURCE-1].

We hypothesize that feature standardization may lead to more stable coefficient estimates and prevent any single feature with a large numerical range from dominating the penalty term [SOURCE-1].

Prior work has established that linear classifiers, including logistic regression, achieve competitive performance on the Iris dataset due to its approximately linear separability across species, particularly between setosa and the other two classes [SOURCE-1].

We set the maximum number of optimization iterations to 200 to ensure convergence of the LBFGS solver on the Iris dataset.

We enable multinomial (softmax) loss rather than one-vs-rest decomposition, so that the model jointly estimates all class probabilities in a single optimization [SOURCE-1].


## Evaluation Plan

We evaluate our approach on the Iris dataset [SOURCE-1], a widely used benchmark comprising 150 samples across three species with four continuous features.

Following Lee [SOURCE-2], we adopt balanced accuracy as our primary metric, defined as the arithmetic mean of per-class recall, to mitigate bias from class imbalance in multiclass settings.

We additionally report ROC-AUC as a secondary metric, which provides a threshold-independent measure of the model's discriminative ability across all classes [SOURCE-2].

We train an L2-regularized logistic regression model using scikit-learn's LogisticRegression with the lbfgs solver and default regularization strength C=1.0, which shrinks all coefficients uniformly to control overfitting without inducing sparsity.

We compare the proposed model against a majority-class predictor that always predicts the most frequent label, which on the balanced Iris dataset achieves a balanced accuracy of 0.500.

The dataset is partitioned into training and testing subsets using stratified sampling to preserve the 1:1:1 class ratio, and both balanced accuracy and ROC-AUC are computed for the model and baseline on the identical test split.

The model attains a balanced accuracy of 0.973 [RESULT-1], demonstrating strong multiclass classification performance on Iris.

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], confirming that it fails to learn discriminative features.

The model achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect probabilistic separation between classes.

We hypothesize that L2-regularized logistic regression will maintain high balanced accuracy on other low-dimensional, approximately linearly separable datasets with similar sample-to-feature ratios, as the ridge penalty controls variance without introducing directional bias in coefficient estimates.

We hypothesize that replacing the L2 penalty with an L1 penalty would yield comparable balanced accuracy while producing sparse solutions that implicitly select a subset of the four Iris features.

We hypothesize that the residual classification errors are concentrated at the Versicolor–Virginica decision boundary, where morphological overlap cannot be fully resolved by a linear boundary.


## Discussion and Future Work

L2-regularized logistic regression achieves a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the Iris dataset, substantially outperforming the majority-class baseline of [RESULT-2] balanced_accuracy = 0.500 [SOURCE-1].

The ROC-AUC of [RESULT-3] ROC-AUC = 0.998 indicates that the model's predicted probabilities provide near-perfect class ranking across the three Iris species [SOURCE-2].

Linear classifiers remain highly competitive on low-dimensional, well-separated datasets such as Iris, where the additional expressive capacity of nonlinear models may offer diminishing returns [SOURCE-1].

Balanced accuracy is an appropriate primary evaluation metric for multiclass problems because it weights per-class recall equally and penalizes models that systematically favor the majority class [SOURCE-2].

We hypothesize that l1-regularized (lasso) logistic regression may achieve classification accuracy comparable to the L2 model while simultaneously performing implicit feature selection by driving irrelevant coefficients to exactly zero [SOURCE-1].

We hypothesize that the practical advantages of L1 regularization over L2 regularization become more pronounced as dataset dimensionality increases and as a larger fraction of features become noise or redundant [SOURCE-1].

We hypothesize that the residual classification errors in our model are concentrated near the decision boundary between Iris versicolor and Iris virginica, while Iris setosa is classified without error due to its linear separability.

We hypothesize that nonlinear methods such as kernel support vector machines or gradient-boosted trees may yield only marginal accuracy improvements over logistic regression on Iris due to the dataset's inherent near-linear separability [SOURCE-1].

We aim to a systematic empirical study comparing L1 and L2 penalties across regularization strengths, datasets of varying dimensionality, and both linear and nonlinear classifiers will yield practical guidelines for selecting regularization strategies in small-sample biological classification domains [SOURCE-1] [SOURCE-2].


## Conclusion

This work aims to demonstrate that L2-regularized logistic regression provides strong classification performance on the Iris dataset, achieving a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 compared to the majority-class baseline of [RESULT-2] balanced_accuracy = 0.500 [SOURCE-1] [SOURCE-2].

The model's discriminative ability is further supported by an ROC-AUC of [RESULT-3] ROC-AUC = 0.998, indicating near-perfect separation across Iris classes [SOURCE-2].

We aim to this work aims to show that simple regularized linear models remain competitive for small, well-structured classification tasks, potentially reducing the need for more complex architectures in comparable settings [SOURCE-1].

We aim to this work aims to establish a transparent and reproducible benchmark pipeline—using balanced accuracy as the primary metric—that future studies can extend to other regularizers such as L1 penalties or elastic net variants [SOURCE-1] [SOURCE-2].

We aim to the substantial improvement over the majority-class baseline ([RESULT-2] balanced_accuracy = 0.500) suggests that the learned decision boundaries capture meaningful class structure rather than trivial class-frequency artifacts [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
