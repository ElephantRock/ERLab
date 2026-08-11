# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression is a well-established linear classification method widely applied to multi-class problems, where it models class probabilities through a linear combination of input features [SOURCE-1].

Balanced accuracy is an appropriate metric for evaluating classifiers on datasets with potential class imbalance, as it averages per-class recall and is insensitive to class frequency [SOURCE-2].

We apply logistic regression to classify Iris flower species using a linear decision boundary over sepal and petal measurements, comparing against a majority-class predictor as baseline.

Logistic regression achieves balanced accuracy of 0.973 on the Iris dataset, substantially exceeding the majority-class baseline's balanced accuracy of 0.500 [RESULT-1] [RESULT-2].

Logistic regression achieves an ROC-AUC of 0.998 on the Iris dataset, indicating near-perfect class separability under the model [RESULT-3].

We aim to we expect this empirical study to provide a clear, reproducible reference point for evaluating logistic regression as a baseline classifier on the Iris benchmark.


## Introduction

Classification of botanical species from morphological measurements is a foundational problem in machine learning, with the Iris dataset introduced by Fisher remaining one of the most widely used benchmarks for evaluating linear classifiers [SOURCE-1].

Logistic regression is among the most widely adopted linear classification methods, valued for its interpretability, differentiable objective, and mature optimization infrastructure [SOURCE-1].

For multi-class problems, standard accuracy can yield misleading conclusions when class distributions are uneven or when per-class errors carry different costs, motivating the use of class-balanced evaluation metrics [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, mitigates class-imbalance bias and has been recommended as a default metric for multi-class classification benchmarks [SOURCE-2].

Majority-class predictors, which assign every instance to the most frequent label, provide a trivial lower bound on classification performance; on evenly distributed datasets such as Iris, such baselines achieve balanced accuracy of only 0.500, underscoring the need for discriminative models [SOURCE-2].

Although logistic regression is well established, contemporary surveys note that its empirical behavior on canonical benchmarks is often reported only with standard accuracy, leaving its balanced-accuracy profile against simple baselines insufficiently documented [SOURCE-1] [SOURCE-2].

The approximately linear separability of Iris species along petal-derived features makes logistic regression a natural modeling choice, as its linear decision boundaries align with the geometry of the data [SOURCE-1].

Following prior benchmarking practice, we adopt balanced accuracy as the primary metric and compare against a majority-class baseline, ensuring that reported gains reflect genuine discriminative ability rather than class-frequency artifacts [SOURCE-2].


## Related Work

Logistic regression has long served as a foundational linear classification method, offering interpretability and computational efficiency across diverse problem settings [SOURCE-1].

Extensions of binary logistic regression to the multi-class setting, such as multinomial (softmax) regression, have been extensively studied and are widely deployed for problems with more than two mutually exclusive classes [SOURCE-1].

Survey work on linear classification methods has documented that logistic regression provides competitive performance on low-dimensional, linearly separable datasets such as Iris, though performance degrades when class boundaries become highly non-linear [SOURCE-1].

Despite the wide availability of non-linear classifiers, prior surveys note that practitioners frequently default to logistic regression as a baseline due to its simplicity, deterministic training, and ease of regularization, which can yield strong results without extensive hyperparameter tuning [SOURCE-1].

However, prior work highlights a persistent limitation: many published classification studies report only raw accuracy, which can be misleading when class distributions are imbalanced or when per-class performance varies substantially [SOURCE-2].

Balanced accuracy—defined as the macro-averaged recall across all classes—has been proposed specifically to address the shortcomings of raw accuracy by giving equal weight to each class regardless of its frequency in the dataset [SOURCE-2].

Lee (2019) demonstrated that for multi-class evaluation, metrics such as balanced accuracy and macro-averaged F1 are more informative than accuracy alone, as they penalize classifiers that perform well only on the majority class while ignoring minority classes [SOURCE-2].

A further limitation identified in prior evaluation research is that many studies fail to report a meaningful baseline comparison, making it difficult to assess whether a classifier's performance is genuinely non-trivial relative to a majority-class predictor [SOURCE-2].

The Iris dataset, introduced by Fisher, has become one of the most widely used benchmark datasets for evaluating classification algorithms, yet prior surveys note that surprisingly few studies report balanced metrics on it, instead relying on accuracy which masks interesting per-class failure modes [SOURCE-1].

Survey comparisons of linear classifiers indicate that logistic regression is frequently outperformed marginally by kernel methods or ensemble approaches on Iris, but the performance gap is often small enough that the added complexity of non-linear methods may not be justified, a trade-off that has not been systematically quantified under balanced evaluation protocols [SOURCE-1].

Prior work on multiclass evaluation metrics has also emphasized that ROC-AUC, when extended to the multi-class setting via one-vs-rest or one-vs-one averaging, provides a threshold-independent measure of discriminative ability that complements balanced accuracy [SOURCE-2].

Nevertheless, a noted limitation across the evaluation literature is that ROC-AUC in the multi-class setting requires careful handling of class averaging, and inconsistencies in how this averaging is performed make cross-study comparisons unreliable [SOURCE-2].


## Proposed Method

The Iris dataset, introduced by Fisher (1936), comprises 150 samples evenly distributed across three species—Setosa, Versicolor, and Virginica—with 50 samples per class, each described by four continuous morphological features: sepal length, sepal width, petal length, and petal width [SOURCE-1].

Logistic regression is among the most widely studied and applied linear classification methods, with well-understood theoretical properties including convexity of the loss landscape and consistency under proper specification [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been established as a particularly appropriate metric for evaluating classifiers where all classes should be weighted equally regardless of their prior frequencies [SOURCE-2].

For multiclass problems, the multinomial (softmax) extension of logistic regression generalizes binary logistic regression by modeling the posterior probability of each class directly through a normalized exponential function over linear scores [SOURCE-1].

We select multinomial logistic regression as our primary classifier because prior work has established that the Iris dataset's four continuous morphological features exhibit largely linear separability among the three species, making a linear decision boundary appropriate [SOURCE-1].

The multinomial softmax formulation is naturally suited to the three-class Iris classification problem, as it provides a principled probabilistic interpretation without requiring heuristic decompositions into binary subproblems such as one-vs-rest [SOURCE-1].

We adopt balanced accuracy as the primary evaluation metric, following established best practices for multiclass classifier evaluation, and additionally report ROC-AUC as a secondary measure of ranking quality across classes [SOURCE-2].

The balanced class distribution in the Iris dataset (50 samples per species) makes balanced accuracy particularly meaningful, as it weights each class's predictive accuracy equally [SOURCE-2].

We formulate the classification task as follows: given a feature vector x ∈ ℝ⁴ representing the four Iris measurements, predict the species label y ∈ {setosa, versicolor, virginica}.

We propose a multinomial logistic regression model that computes class probabilities via the softmax function: P(y=k|x) = exp(w_kᵀx + b_k) / Σⱼ exp(w_jᵀx + b_j) for k ∈ {1, 2, 3}, where w_k ∈ ℝ⁴ are class-specific weight vectors and b_k ∈ ℝ are class-specific bias terms [SOURCE-1].

The model takes all four raw features—sepal length, sepal width, petal length, and petal width—as input without manual feature engineering or dimensionality reduction.

We standardize all features to zero mean and unit variance prior to model fitting to ensure comparable scale across features and stable optimization.

We apply L2 regularization (ridge penalty) to the weight parameters to control model complexity [SOURCE-1].

The loss function is the penalized negative log-likelihood: L(W, b) = -(1/n) Σᵢ Σₖ 𝟙{yᵢ=k} log P(yᵢ=k|xᵢ) + λ‖W‖²_F, where λ controls regularization strength and W denotes the concatenation of all weight vectors [SOURCE-1].

Model parameters are estimated via maximum likelihood using the L-BFGS quasi-Newton optimization algorithm, which exploits the convexity of the penalized log-likelihood to converge to the global optimum [SOURCE-1].

We compare the proposed logistic regression classifier against a majority-class baseline that always predicts the most frequent species in the training set.

We hypothesize that the logistic regression model may achieve balanced accuracy substantially exceeding the majority-class baseline of 0.500 [SOURCE-1].

We hypothesize that l2 regularization may reduce overfitting on the relatively small Iris dataset (150 total samples), potentially improving generalization to held-out data [SOURCE-1].

We hypothesize that we anticipate that the linear decision boundaries produced by logistic regression will be sufficient to capture the discriminative structure among the three Iris species [SOURCE-1].

We hypothesize that we expect the model to achieve high ROC-AUC, which would indicate well-separated probability estimates across the three classes [SOURCE-2].

Our results show that the proposed logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], substantially exceeding the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

Our results further show a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class separation in the probability estimates produced by the model.

These results demonstrate that linear logistic regression is sufficient for the Iris classification task, confirming that the morphological features are approximately linearly separable across the three species.


## Evaluation Plan

We use the Iris dataset [SOURCE-1], a widely recognized multi-class classification benchmark consisting of 150 instances across three species of iris flowers, each characterized by four morphological features (sepal length, sepal width, petal length, and petal width).

Following [SOURCE-2], we measure balanced accuracy as our primary evaluation metric, which computes the macro-average of per-class recall and is well-suited for multi-class classification tasks where equal importance is assigned to each class.

We additionally report ROC-AUC as a secondary metric to assess the discriminative quality of the classifier's probability estimates across the three Iris classes [SOURCE-2].

Our experimental protocol evaluates logistic regression configured for multi-class classification, with L2 regularization applied to mitigate overfitting on the relatively small Iris dataset [SOURCE-1].

We compare logistic regression against a majority-class predictor baseline, which assigns all test instances to the most frequent class in the training set, providing a lower-bound reference for classification performance.

The choice of balanced accuracy as the primary metric is motivated by the need to give equal weight to each of the three Iris species, ensuring that evaluation is not biased toward any single class even if class distributions were to vary across data splits [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, indicating strong multi-class classification performance.

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2], confirming that logistic regression provides a substantial improvement of 0.473 absolute balanced accuracy points over this trivial baseline.

Logistic regression achieves a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class separation in the probability estimates and corroborating the strong balanced accuracy performance.


## Discussion and Future Work

Logistic regression has long been established as a foundational linear classification method, particularly well-suited to problems where classes are approximately linearly separable in feature space [SOURCE-1].

Balanced accuracy is a recommended metric for multiclass classification because it accounts for class imbalance by averaging per-class recall, avoiding the inflation that can occur with standard accuracy when class distributions are uneven [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3] on the Iris dataset, substantially exceeding the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

The near-perfect ROC-AUC of 0.998 suggests that the logistic regression model produces well-calibrated probability estimates across decision thresholds, not merely accurate point predictions [RESULT-3] [SOURCE-2].

We aim to we contribute an empirical demonstration that standard logistic regression, without ensemble methods or kernel tricks, can achieve strong multiclass performance on a canonical botanical classification benchmark, reinforcing the continued relevance of linear methods in applied machine learning [RESULT-1] [RESULT-2] [SOURCE-1].

We hypothesize that the strong performance observed on Iris will generalize to other datasets with comparable linear separability, but that performance will degrade measurably on datasets with highly nonlinear class boundaries [RESULT-1] [SOURCE-1].

We hypothesize that the addition of L2 regularization will reduce overfitting on smaller training folds without significantly lowering balanced accuracy on Iris, given the dataset's moderate dimensionality and sample size [RESULT-1] [SOURCE-1].

We hypothesize that polynomial feature expansion of degree two or higher will yield diminishing returns on Iris, because the four original features already provide sufficient linear discriminative signal, as evidenced by the 0.973 balanced accuracy [RESULT-1].

We hypothesize that the single misclassification implied by the balanced accuracy of 0.973 occurs at the boundary between versicolor and virginica, the two most morphologically overlapping species, and that targeted feature engineering on petal dimensions may resolve this error [RESULT-1].

We aim to a systematic comparison of logistic regression against nonlinear classifiers such as random forests and support vector machines with radial basis kernels across multiple benchmark datasets would clarify the boundary of applicability for linear methods in botanical taxonomy tasks [RESULT-1] [SOURCE-1].

The Iris dataset is known to be well-separated across its three classes, which partially explains the near-perfect performance and suggests that the difficulty ceiling of this benchmark may limit the generalizability of conclusions drawn from it alone [SOURCE-1].

We hypothesize that balanced accuracy differences between logistic regression and more complex models will be statistically significant only on datasets with class overlap exceeding that of Iris, motivating evaluation on noisier real-world botanical datasets [RESULT-1] [RESULT-2] [SOURCE-2].


## Conclusion

Logistic regression is a well-established linear method for classification, particularly suited to problems where class boundaries are approximately linearly separable [SOURCE-1].

Balanced accuracy is an appropriate primary metric for multi-class classification because it accounts for class frequency and prevents inflated estimates on imbalanced data [SOURCE-2].

We aim to this work aims to provide an empirical demonstration that logistic regression achieves strong multi-class classification on the Iris dataset, with balanced accuracy of 0.973 [RESULT-1] and ROC-AUC of 0.998 [RESULT-3], substantially exceeding the majority-class baseline balanced accuracy of 0.500 [RESULT-2].

We aim to this work aims to establish that even a simple linear classifier can yield near-perfect discrimination on Iris, reinforcing the dataset's reputation as a benchmark where linear separability is largely achievable.


## References

[Generated from 2 source papers — see proposal for full bibliography]
