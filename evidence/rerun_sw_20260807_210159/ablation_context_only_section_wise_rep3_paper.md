# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Logistic regression remains one of the most widely used linear classification methods, offering interpretability and competitive performance on structured datasets [SOURCE-1].

Balanced accuracy is a suitable evaluation metric for multiclass classification tasks because it accounts for class imbalance by averaging per-class recall [SOURCE-2].

We investigate logistic regression as a classifier on the Iris dataset, reporting balanced accuracy and ROC-AUC against a majority-class baseline.

Our results show that logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset, substantially outperforming the majority-class baseline, which achieves a balanced accuracy of 0.500 [RESULT-1][RESULT-2].

Logistic regression attains an ROC-AUC of 0.998 on the Iris dataset, indicating strong class separability [RESULT-3].

We aim to we expect this empirical study to provide a rigorous, reproducible benchmark of logistic regression performance on a canonical multiclass dataset, serving as a reference point for future linear-model evaluations.


## Introduction

Classification of botanical specimens remains a foundational benchmark in machine learning, with the Iris dataset—introduced by Anderson and popularized by Fisher—serving as one of the most widely used testbeds for evaluating discriminative algorithms across decades of research [SOURCE-1].

Logistic regression is one of the most extensively studied and deployed linear classification methods, prized for its interpretability, computational efficiency, and well-understood theoretical properties including convex optimization guarantees [SOURCE-1].

While logistic regression was originally formulated for binary classification, its extension to multiclass settings through multinomial (softmax) formulations has made it applicable to problems with three or more classes, such as the three-species Iris classification task [SOURCE-1].

A persistent limitation in evaluating classifiers on the Iris dataset is that standard accuracy can mask poor performance on individual classes, particularly when class distributions are balanced but certain species—such as Iris versicolor and Iris virginica—exhibit substantial overlap in their feature spaces, making them harder to separate than Iris setosa [SOURCE-1] [SOURCE-2].

Prior work has noted that many published evaluations on Iris report only aggregate accuracy without a trivial baseline comparison, making it difficult to assess whether observed performance reflects genuine discriminative power or merely the relative ease of separating one class from the other two [SOURCE-1].

Balanced accuracy—defined as the arithmetic mean of per-class recall—has been recommended as a more informative evaluation metric than raw accuracy for multiclass problems, as it equally weights each class and penalizes classifiers that perform well on the majority class but poorly on others [SOURCE-2].

We adopt a majority-class predictor as our baseline, following established evaluation protocols that require comparison against a trivial classifier to contextualize the practical utility of more complex models [SOURCE-2].

The use of ROC-AUC as a supplementary metric is motivated by prior work demonstrating its value in characterizing the ranking quality of probabilistic classifiers across decision thresholds, complementing the threshold-dependent balanced accuracy [SOURCE-2].

Prior surveys of linear classification methods have shown that logistic regression, despite its simplicity, often achieves competitive performance on low-dimensional datasets with approximately linear class boundaries, making it a natural first choice for systematic empirical study on Iris [SOURCE-1].

The Iris dataset's four-dimensional feature space (sepal length, sepal width, petal length, petal width) and three-class structure provide a setting in which the decision boundary geometry of logistic regression can be meaningfully examined, as prior work has shown that at least one class boundary is approximately linearly separable [SOURCE-1].

A systematic empirical study that pairs logistic regression with both balanced accuracy and ROC-AUC, while establishing a majority-class baseline, addresses the gap left by prior evaluations that typically report only aggregate accuracy without baseline context [SOURCE-1] [SOURCE-2].


## Related Work

Logistic regression is one of the most widely used linear classification methods, with a long history in statistical learning and numerous applications across scientific domains [SOURCE-1].

Linear classification methods, including logistic regression, have been extensively surveyed and benchmarked across a variety of benchmark datasets, providing a baseline for evaluating classifier performance [SOURCE-1].

Despite its simplicity relative to nonlinear approaches, logistic regression remains competitive on many classification tasks, particularly when classes are approximately linearly separable [SOURCE-1].

A known limitation of linear classification methods is their inability to capture complex nonlinear relationships between features and target classes, which can constrain performance on datasets with intricate feature interactions [SOURCE-1].

Prior surveys have noted that while logistic regression performs well on linearly separable data, its performance may degrade on datasets where class boundaries are more complex [SOURCE-1].

The evaluation of multiclass classification methods requires careful selection of metrics to account for class imbalance and varying class distributions across multiple classes [SOURCE-2].

Balanced accuracy has been proposed and studied as a metric that accounts for class imbalance by averaging per-class recall, providing a more robust evaluation than standard accuracy in multiclass settings [SOURCE-2].

Standard accuracy metrics can be misleading in multiclass settings where class distributions are uneven, potentially overestimating classifier performance on majority classes [SOURCE-2].

ROC-AUC has been used as an additional evaluation metric for classification tasks, particularly useful for assessing the discriminative ability of classifiers across different decision thresholds [SOURCE-2].

The choice of evaluation metric significantly impacts the perceived performance of multiclass classifiers, with balanced accuracy providing a more conservative and informative assessment than raw accuracy, especially when comparing against naive baselines such as majority-class predictors [SOURCE-2].

The Iris dataset has served as a standard benchmark in the classification literature for evaluating linear and nonlinear methods alike, making it a natural testbed for assessing logistic regression [SOURCE-1].


## Proposed Method

Logistic regression is among the most widely studied linear classification methods, with decades of successful application to structured tabular benchmarks in machine learning [SOURCE-1].

For multiclass classification, raw accuracy can obscure per-class performance when distributions are uneven, which has motivated the adoption of balanced accuracy and area-under-curve metrics in rigorous evaluation protocols [SOURCE-2].

We adopt multinomial logistic regression as our primary classifier because prior surveys have demonstrated that linear models remain competitive on low-dimensional tabular data such as the Iris benchmark [SOURCE-1].

We select balanced accuracy as our primary evaluation metric because it equally weights per-class recall, providing a more informative assessment than raw accuracy when evaluating multiclass classifiers [SOURCE-2].

We formulate the Iris species identification task as a multinomial logistic regression problem with three mutually exclusive output classes corresponding to Iris setosa, Iris versicolor, and Iris virginica.

Each input sample is represented as a four-dimensional real-valued feature vector consisting of sepal length, sepal width, petal length, and petal width.

The model maps each feature vector to a probability distribution over the three species via the softmax function applied to a learned linear transformation of the input features.

We train the model by minimizing the multinomial cross-entropy loss between the predicted class probabilities and the one-hot encoded true labels using L-BFGS, a quasi-Newton optimizer [SOURCE-1].

We apply L2 regularization with a fixed inverse regularization strength to mitigate overfitting on the relatively small Iris sample [SOURCE-1].

We hypothesize that L2 regularization may reduce the risk of overfitting given the modest number of training samples relative to feature dimensionality [SOURCE-1].

We compare our logistic regression classifier against a majority-class baseline that always predicts the most frequent species label observed in the training set.

We hypothesize that the majority-class baseline will yield a balanced accuracy near 0.50, reflecting its inability to discriminate among the three species.

We hypothesize that logistic regression may achieve substantially higher balanced accuracy than the majority-class baseline on Iris [SOURCE-1].

We hypothesize that the four morphological features will be largely linearly separable across species boundaries [SOURCE-1].

We evaluate model performance using balanced accuracy as the primary metric [SOURCE-2].

We additionally report ROC-AUC computed via one-vs-rest averaging across the three classes as a secondary metric [SOURCE-2].

We hypothesize that high ROC-AUC values will indicate strong ranking quality of the predicted class probabilities [SOURCE-2].

We partition the Iris dataset into stratified training and test subsets to preserve the per-class proportions in both splits.

We hypothesize that stratified splitting may reduce variance in the estimated balanced accuracy compared to random splitting [SOURCE-2].

We standardize each feature to zero mean and unit variance prior to fitting the logistic regression model [SOURCE-1].

We hypothesize that feature standardization may improve convergence stability of the L-BFGS optimizer [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973, substantially exceeding the majority-class baseline balanced accuracy of 0.500.


## Evaluation Plan

We evaluate our approach on the Iris dataset, a widely used multiclass classification benchmark comprising 150 samples across three species with four continuous features [SOURCE-1].

Following established multiclass evaluation practices [SOURCE-2], we adopt balanced accuracy as our primary metric, defined as the arithmetic mean of per-class recall.

We additionally report ROC-AUC using a one-versus-rest macro-averaging scheme to characterize the model's ranking quality across decision thresholds [SOURCE-2].

We require a majority-class baseline that captures the minimum achievable performance to contextualize the logistic regression results [SOURCE-2].

Balanced accuracy is chosen as the primary metric because it weights per-class recall equally and prevents performance inflation from majority-class predictions [SOURCE-2].

We fit a multinomial logistic regression model with L2 regularization on the training portion of Iris and evaluate balanced accuracy and ROC-AUC on a held-out test set [SOURCE-1].

We hypothesize that logistic regression will substantially outperform the majority-class baseline in balanced accuracy, because the Iris features—particularly petal dimensions—are known to be nearly linearly separable [SOURCE-1].

Our results show that the logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1].

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2].

We observe a macro-averaged ROC-AUC of 0.998, indicating near-perfect class ranking [RESULT-3].

These findings demonstrate that the linear decision boundary learned by logistic regression effectively separates Iris species [RESULT-1] [RESULT-2] [RESULT-3].


## Discussion and Future Work

Logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset, nearly doubling the majority-class baseline of 0.500 [RESULT-1] [RESULT-2] [SOURCE-1].

The ROC-AUC of 0.998 indicates near-perfect pairwise discriminative ability across all Iris species pairs [RESULT-3] [SOURCE-2].

The three Iris species are largely linearly separable under the standard sepal and petal feature representation [SOURCE-1].

The residual misclassification likely originates from morphological overlap between Iris versicolor and Iris virginica in the petal-length and petal-width feature space [SOURCE-1] [RESULT-1].

Balanced accuracy serves as a robust metric because it equally weights sensitivity across classes, mitigating distortion from class imbalance [SOURCE-2].

We hypothesize that incorporating polynomial interaction terms or kernel-based logistic regression could reduce residual versicolor–virginica misclassification by capturing nonlinear structure at the class boundary [SOURCE-1].

We hypothesize that L1 or L2 regularization may influence generalization on Iris-like datasets where sample sizes are small, and that evaluating regularization paths could reveal whether the model overfits training-fold idiosyncrasies.

We aim to logistic regression would achieve comparable or superior balanced accuracy on other morphologically well-separated species classification tasks, with the magnitude of advantage depending on the degree of linear separability inherent to each dataset [SOURCE-1].

We hypothesize that ensemble methods such as random forests or gradient-boosted trees would yield only marginal improvements on Iris given the already high ROC-AUC, potentially limiting the dataset's ability to discriminate among increasingly sophisticated methods [RESULT-3] [SOURCE-1].


## Conclusion

Logistic regression is a well-established linear classification method that has been extensively studied across many benchmark classification tasks [SOURCE-1].

Balanced accuracy is a suitable evaluation metric for multiclass classification, as it accounts for potential class imbalance by averaging per-class recall [SOURCE-2].

Logistic regression achieved a balanced accuracy of 0.973 on the Iris dataset, substantially outperforming the majority-class baseline [RESULT-1] [RESULT-2].

The majority-class baseline yielded a balanced accuracy of 0.500, confirming that non-trivial class structure exists in the data for logistic regression to exploit [RESULT-2].

The logistic regression model attained an ROC-AUC of 0.998, indicating near-perfect ranking performance across the three Iris species [RESULT-3].

The large performance gap between logistic regression and the majority-class baseline confirms that the Iris species boundaries are largely linearly separable [RESULT-1] [RESULT-2].

We aim to this work aims to provide a transparent, reproducible baseline for logistic regression classification on Iris using balanced accuracy and a majority-class comparator.

We aim to this work aims to highlight the limited headroom that the Iris dataset offers for evaluating novel or more complex classification approaches, given the near-ceiling performance of a simple linear model.

We aim to this work aims to encourage the adoption of balanced evaluation metrics and appropriate baselines in linear classification studies on standard benchmarks.


## References

[Generated from 2 source papers — see proposal for full bibliography]
