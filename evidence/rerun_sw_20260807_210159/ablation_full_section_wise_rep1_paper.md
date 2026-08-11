# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Classification of Iris flower species from morphological features is a foundational benchmark in machine learning [SOURCE-1].

Logistic regression is a well-established linear classification method suitable for multi-class problems [SOURCE-1].

We apply logistic regression to the Iris dataset, comparing balanced accuracy against a majority-class predictor baseline.

Our results show balanced accuracy of [RESULT-1] for logistic regression versus the baseline's [RESULT-2], demonstrating strong discriminative performance [SOURCE-2].

The model achieves an ROC-AUC of [RESULT-3], further confirming strong class separation [SOURCE-2].

We aim to we expect this baseline analysis to serve as a clear reference point for future comparisons of more complex methods on Iris.


## Introduction

Classification of Iris flower species from morphological measurements is one of the most enduring benchmarks in machine learning, serving as a standardized testbed for evaluating classification algorithms across decades of research [SOURCE-1].

Logistic regression is a foundational linear classification method that models class membership probabilities through a linear combination of input features transformed by a logistic function, making it applicable to both binary and multi-class settings [SOURCE-1].

Standard accuracy metrics can obscure per-class performance, particularly in datasets with class imbalance, where a classifier may achieve high overall accuracy while performing poorly on individual classes [SOURCE-2].

Simple baselines such as majority-class prediction provide a lower bound on expected performance but fail to leverage discriminative information in the features, serving primarily as reference points rather than competitive classifiers [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, provides a metric robust to class imbalance and has been advocated as a standard measure for multi-class classification evaluation [SOURCE-2].

Linear classifiers such as logistic regression are particularly suitable as baseline models for benchmark datasets because their interpretability and well-characterized behavior on low-dimensional, feature-rich data provide a transparent point of comparison for more complex methods [SOURCE-1].

Following established benchmarking practices, we pair logistic regression with balanced accuracy as the primary evaluation metric and include a majority-class baseline, ensuring that observed performance reflects genuine discriminative use of morphological features rather than artifacts of class distribution [SOURCE-1] [SOURCE-2].


## Related Work

The Iris dataset, introduced by Fisher, remains one of the most widely used benchmarks for evaluating classification algorithms, comprising 150 samples across three species with four morphological features each [SOURCE-1].

Logistic regression is among the most extensively studied linear classification methods, offering interpretability and computational efficiency through maximum-likelihood estimation of class-conditional probabilities [SOURCE-1].

Multi-class logistic regression extends the binary formulation by employing the softmax function to model the probability distribution across multiple classes simultaneously, enabling direct application to datasets such as Iris with three target categories [SOURCE-1].

Linear classification methods, including logistic regression, have been shown to achieve strong performance on low-dimensional, well-separated datasets, making them competitive with more complex nonlinear approaches in such settings [SOURCE-1].

Surveys of linear classification methods have noted that despite the proliferation of complex models, linear classifiers remain important baselines due to their transparency, low risk of overfitting on small datasets, and ease of deployment [SOURCE-1].

Prior surveys of linear classification methods have frequently omitted systematic comparisons against trivial baselines such as majority-class prediction, making it difficult to contextualize the practical utility of even simple classifiers [SOURCE-1].

The majority-class predictor, which assigns all instances to the most frequent class, serves as the simplest non-trivial baseline and is recommended for establishing a lower bound on expected classification performance [SOURCE-1].

Balanced accuracy has been proposed as a more informative metric than standard accuracy for multi-class classification, as it computes the arithmetic mean of per-class recall and is robust to class imbalance [SOURCE-2].

Under balanced accuracy, a majority-class predictor that correctly identifies only one class will achieve a score reflecting the inverse of the number of classes, penalizing failure to discriminate among all categories [SOURCE-2].

Many prior evaluations of Iris classification rely exclusively on standard accuracy, which can mask poor per-class performance when classes are approximately balanced, leading to overly optimistic assessments of classifier quality [SOURCE-2].

Prior work on multi-class evaluation metrics has emphasized that relying on a single metric can provide an incomplete picture of classifier behavior, recommending the complementary use of threshold-independent measures such as ROC-AUC alongside accuracy-based metrics [SOURCE-2].

The receiver operating characteristic area under the curve (ROC-AUC) provides a threshold-independent assessment of a classifier's ability to rank instances by predicted class probability, and has been widely adopted for binary and multi-class settings through averaging strategies [SOURCE-2].

Prior studies on Iris classification have frequently failed to report both balanced accuracy and ROC-AUC together, limiting comparability across studies and preventing a comprehensive understanding of discriminative performance [SOURCE-2].

The lack of standardized evaluation protocols in prior Iris classification studies has hindered reproducibility, with variations in train-test splits, cross-validation strategies, and reported metrics making cross-study comparison difficult [SOURCE-2].

Regularized logistic regression, including L2-penalized variants, has been demonstrated to perform well on small-to-medium-sized datasets with moderate feature dimensionality, where the risk of overfitting is manageable and model simplicity is advantageous [SOURCE-1].

Prior work has noted that while linear classifiers like logistic regression may underperform nonlinear methods such as kernel SVMs or random forests on complex datasets, they are often competitive or superior on linearly separable or near-separable data [SOURCE-1].

Despite the availability of balanced accuracy as a metric, many published Iris classification results continue to report only raw accuracy, and a non-trivial fraction of studies omit any baseline comparison entirely, undermining the interpretability of reported performance gains [SOURCE-2].

The choice of evaluation metric has been shown to materially affect conclusions about classifier performance, particularly in multi-class settings where micro-averaged and macro-averaged metrics can diverge significantly when per-class sample sizes or difficulties differ [SOURCE-2].

Prior surveys have observed that linear classification methods benefit from well-conditioned, low-dimensional feature spaces, and that performance can degrade when features are highly correlated or when the number of features approaches the number of samples [SOURCE-1].

Existing evaluations of Iris classification have not systematically documented the gap between a majority-class baseline and logistic regression in terms of balanced accuracy, leaving open the question of how much discriminative power linear methods add over trivial prediction on this benchmark [SOURCE-1].


## Proposed Method

Logistic regression is a well-established linear classification method that models class-conditional probabilities through a logistic function applied to a linear combination of input features (Smith, 2020) [SOURCE-1].

For multi-class settings such as the three-species Iris problem, multinomial logistic regression (softmax regression) extends binary logistic regression by computing a normalized probability distribution over all classes simultaneously (Smith, 2020) [SOURCE-1].

The Iris dataset comprises four continuous morphological features—sepal length, sepal width, petal length, and petal width—across three species (setosa, versicolor, virginica), and prior work has demonstrated that these features are largely linearly separable, making logistic regression a natural and interpretable baseline choice (Smith, 2020) [SOURCE-1].

We formulate Iris species classification as multinomial logistic regression, where the model computes class probabilities P(y = k | x) for each species k ∈ {setosa, versicolor, virginica} using the softmax function applied to learned linear weights and bias terms.

The model parameters (weight matrix W ∈ ℝ^{3×4} and bias vector b ∈ ℝ^3) are optimized by minimizing the multi-class cross-entropy loss between predicted probability distributions and one-hot encoded species labels.

We optimize the cross-entropy loss using the L-BFGS quasi-Newton algorithm, which approximates second-order curvature information to accelerate convergence on this low-dimensional problem.

We apply L2 regularization to the weight matrix with a regularization strength hyperparameter λ.

We hypothesize that L2 regularization may mitigate overfitting given the limited number of training samples relative to the number of model parameters.

All four input features are standardized to zero mean and unit variance using statistics computed on the training set before model fitting, and the same transformation is applied to the test set.

Feature standardization is motivated by the differing measurement scales of the four Iris features (e.g., petal width ranges differ from sepal length ranges), which can impede convergence of gradient-based optimization when left unnormalized (Smith, 2020) [SOURCE-1].

We compare our multinomial logistic regression model against a majority-class baseline that always predicts the most frequent species in the training set, which serves as a trivial lower-bound reference.

We hypothesize that the logistic regression model will substantially outperform the majority-class baseline on balanced accuracy.

Balanced accuracy computes the macro-averaged recall across all classes and is robust to class imbalance, making it suitable for multi-class evaluation (Lee, 2019) [SOURCE-2].

We select balanced accuracy as the primary evaluation metric because it equally weights per-class recall, ensuring that the model's discriminative ability is measured fairly across all three Iris species rather than being dominated by the most frequent class (Lee, 2019) [SOURCE-2].

We additionally report the one-vs-rest ROC-AUC as a secondary metric to characterize the model's threshold-independent ranking quality across classes.

ROC-AUC provides a threshold-independent measure of discriminative performance that complements balanced accuracy by capturing the model's ability to rank correct classes above incorrect ones (Lee, 2019) [SOURCE-2].

Model evaluation is performed using a standard train-test split of the 150-sample Iris dataset.

The standard Iris train-test split has been widely adopted in benchmark studies and provides a consistent basis for comparison with prior results (Smith, 2020) [SOURCE-1].

We hypothesize that the strong linear separability of petal-based features in the Iris dataset may enable the logistic regression model to achieve near-perfect classification on at least two of the three species.

Prior work has noted that Iris setosa is linearly separable from the other two species, while versicolor and virginica show partial overlap in feature space, creating a meaningful but tractable classification challenge (Smith, 2020) [SOURCE-1].


## Evaluation Plan

We use the Iris dataset [SOURCE-1] as our evaluation benchmark, comprising 150 samples across three flower species (Setosa, Versicolor, Virginica) with four morphological features each (sepal length, sepal width, petal length, petal width).

Following [SOURCE-2], we measure balanced accuracy as our primary evaluation metric to ensure fair performance assessment across all three Iris species regardless of their relative frequencies in train and test partitions.

We additionally report ROC-AUC following multiclass evaluation conventions [SOURCE-2] to characterize the model's threshold-independent discriminative ability across pairwise class comparisons.

We train a multinomial logistic regression classifier on the Iris feature set and compare it against a majority-class predictor baseline that always assigns the most frequent class label from the training data.

We employ a standardized train-test partitioning of the Iris dataset, fitting model parameters on the training subset and evaluating all reported metrics exclusively on the held-out test set to obtain unbiased estimates of generalization performance.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that prior work suggests the Iris feature space exhibits near-linear class separability [SOURCE-1].

We hypothesize that balanced accuracy and ROC-AUC will converge in their qualitative ranking of model quality, since both metrics capture aspects of the same underlying class-separation structure in Iris [SOURCE-2].

Our results show that logistic regression achieves balanced_accuracy = 0.973 [RESULT-1], substantially exceeding the majority-class baseline.

The majority-class baseline achieves balanced_accuracy = 0.500 [RESULT-2], confirming that non-trivial classification requires exploiting the morphological feature space rather than relying on class frequency alone.

Our results show that the logistic regression model achieves ROC-AUC = 0.998 [RESULT-3], indicating near-perfect class separability across decision thresholds.

We hypothesize that the strong concordance between balanced accuracy (0.973) and ROC-AUC (0.998) supports the reliability of the reported performance assessment, as both metrics independently indicate high classification quality.


## Discussion and Future Work

Logistic regression achieves strong classification performance on Iris, with balanced accuracy of [RESULT-1] versus the majority-class baseline's [RESULT-2], consistent with established surveys of linear classification methods [SOURCE-1].

The ROC-AUC of [RESULT-3] indicates near-perfect class separation, reinforcing that the Iris feature space is highly amenable to linear decision boundaries [SOURCE-1].

Balanced accuracy serves as a more informative evaluation metric than raw accuracy in multiclass settings, as a majority-class predictor collapses to chance-level performance under balanced averaging [SOURCE-2] [RESULT-2].

We hypothesize that incorporating polynomial feature interactions will yield diminishing returns on the standard Iris dataset given its high linear separability, but may provide measurable gains on noise-augmented variants where class boundaries become less linearly separable [RESULT-3].

We hypothesize that logistic regression will exhibit more graceful performance degradation than tree-based ensemble methods under controlled feature perturbation, owing to the smooth, continuous nature of its decision boundaries.

We hypothesize that applying PCA prior to logistic regression will not significantly reduce balanced accuracy on Iris, given the dataset's low dimensionality and known inter-feature correlations [SOURCE-1].

We hypothesize that the near-ceiling performance observed on Iris implies a ceiling effect that limits the benchmark's utility for discriminating among advanced classification methods, and that more challenging variants are necessary for meaningful comparisons [RESULT-1].

We aim to the evaluation methodology demonstrated in this work—pairing a transparent linear baseline with a majority-class comparator under balanced accuracy—will serve as a reusable template for establishing lower-bound performance in multiclass classification studies on other classical benchmarks [SOURCE-2].


## Conclusion

Classification of Iris flower species from morphological features is a foundational benchmark in machine learning, widely used to evaluate linear and nonlinear classifiers alike [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of [RESULT-1], substantially outperforming the majority-class baseline, which yields [RESULT-2].

The model attains a ROC-AUC of [RESULT-3], reflecting strong discriminative ability across the three Iris species.

The use of balanced accuracy ensures that mild class imbalance is properly accounted for, aligning with best practices in multiclass evaluation [SOURCE-2].

We aim to this work aims to establish a transparent and reproducible baseline for Iris classification using standard logistic regression, against which more complex methods can be benchmarked.

We aim to this work aims to highlight the importance of comparing against simple baselines such as the majority-class predictor, particularly for well-studied datasets where strong performance may be taken for granted [RESULT-1] [RESULT-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
