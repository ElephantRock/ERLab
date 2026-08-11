# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset is a foundational benchmark for multiclass classification, widely used to evaluate both linear and nonlinear classification methods [SOURCE-1].

Logistic regression is a well-established linear classification technique widely adopted in practice for multiclass problems [SOURCE-1].

Balanced accuracy, which averages per-class recall, provides a robust metric for evaluating multiclass classifiers, particularly when class distributions may be uneven [SOURCE-2].

Logistic regression models class probabilities through a linear combination of features transformed by the softmax function, enabling direct estimation of multiclass decision boundaries [SOURCE-1].

We aim to we expect logistic regression to achieve strong classification performance on the Iris dataset, with balanced accuracy of 0.973 [RESULT-1] and ROC-AUC of 0.998 [RESULT-3], substantially outperforming a majority-class baseline at balanced accuracy of 0.500 [RESULT-2].

We aim to confirm that simple linear methods such as logistic regression can achieve near-perfect classification on the Iris benchmark, reinforcing the dataset's status as a tractable classification problem for linear approaches [SOURCE-1] [RESULT-1].


## Introduction

The Iris dataset, introduced by Ronald Fisher in 1936, has served as one of the most widely recognized benchmarks for evaluating classification algorithms, comprising 150 samples across three species with four morphological features each, where one class is linearly separable from the other two while the remaining classes exhibit overlapping feature distributions [SOURCE-1].

Logistic regression remains a cornerstone of applied machine learning due to its interpretability, computational efficiency, and robust theoretical grounding, and it is frequently cited as a prototypical method for data with predominantly linear class boundaries [SOURCE-1].

In multiclass settings such as Iris, extensions including multinomial logistic regression enable direct prediction across more than two classes by modeling the probability of each class as a function of the shared feature space [SOURCE-1].

A significant limitation of many published classification evaluations is the reliance on raw accuracy as the sole performance metric, which can be profoundly misleading in multiclass settings where per-class performance may vary substantially even when overall accuracy appears satisfactory [SOURCE-2].

This concern is directly relevant to Iris: because Iris setosa is trivially separable, a classifier may achieve high overall accuracy while failing to distinguish between Iris versicolor and Iris virginica, inflating the apparent quality of the model [SOURCE-2].

Balanced accuracy—defined as the arithmetic mean of per-class recall—addresses this limitation by assigning equal weight to each class, ensuring that a model cannot mask poor performance on difficult classes behind strong performance on easy ones [SOURCE-2].

A further limitation in existing classification studies is the frequent omission of simple baseline comparisons, without which it is difficult to determine whether a model's performance reflects genuine discriminative ability or merely exploits structural properties of the data such as class imbalance [SOURCE-2].

Reporting baseline performance alongside model results is essential for responsible experimental design, as it provides readers with the necessary context to interpret reported metrics [SOURCE-2].

We select logistic regression as a representative linear classifier for Iris, consistent with its prominent role as a benchmark method for linearly structured data, and we adopt balanced accuracy as the primary evaluation metric following recommended practices for multiclass tasks [SOURCE-1] [SOURCE-2].

We include a majority-class predictor as a baseline to establish a minimal performance threshold, ensuring that the evaluation contextualizes logistic regression's discriminative ability against the simplest possible decision rule [SOURCE-2].

We additionally report ROC-AUC as a supplementary metric to characterize the model's ranking performance across classes, complementing the per-class sensitivity captured by balanced accuracy [SOURCE-2].


## Related Work

Logistic regression is among the most established linear classification methods, providing interpretable parametric decision boundaries that have been applied across diverse domains [SOURCE-1].

Linear classifiers, including logistic regression, are known to perform well on low-dimensional datasets where class boundaries are approximately linearly separable [SOURCE-1].

The Iris dataset has served as a canonical benchmark in machine learning, used extensively to evaluate and compare the performance of classification algorithms since the field's inception [SOURCE-1].

Standard accuracy, while commonly reported, can be a misleading metric in classification tasks with imbalanced class distributions, as it may inflate the apparent performance of trivial predictors that always select the majority class [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more robust evaluation metric for multiclass classification, particularly when class priors are unequal [SOURCE-2].

ROC-AUC is widely adopted to measure the discriminative ranking quality of probabilistic classifiers, aggregating performance across all classification thresholds [SOURCE-2].

Multinomial and regularized variants of logistic regression have been developed specifically to extend binary logistic regression to multiclass settings and to mitigate overfitting on small datasets [SOURCE-1].

Many prior evaluations of linear classifiers on the Iris dataset relied primarily on standard accuracy as the sole reported metric, potentially obscuring the relative strengths and weaknesses of models when class distributions are not perfectly balanced [SOURCE-1].

Prior studies evaluating logistic regression on small benchmark datasets frequently omit explicit comparison against trivial baselines such as a majority-class predictor, making it difficult to contextualize whether reported performance reflects genuine model capability [SOURCE-1].

A substantial body of prior multiclass classification work has reported accuracy without accompanying balanced accuracy or per-class metrics, limiting the interpretability and reproducibility of cross-study comparisons [SOURCE-2].

Systematic comparisons between logistic regression and majority-class baselines on canonical benchmarks such as Iris remain sparse in the literature, despite the recognized importance of establishing baseline performance levels [SOURCE-1].

The distinction between comparison model performance and baseline performance is not always clearly delineated or separately reported in published classification results, complicating rigorous assessment of incremental gains [SOURCE-2].

Evaluation frameworks for multiclass classifiers have increasingly emphasized the simultaneous reporting of multiple complementary metrics—such as balanced accuracy and ROC-AUC—to provide a more comprehensive picture of model performance than any single metric alone [SOURCE-2].

Majority-class prediction, while computationally trivial, serves as an essential lower-bound baseline: any classifier that fails to substantially exceed majority-class performance under balanced evaluation may be considered to have learned little beyond class priors [SOURCE-2].


## Proposed Method

Logistic regression is a well-established linear classification method that has been widely applied to multiclass problems with near-linearly separable feature spaces [SOURCE-1].

The Iris dataset consists of 150 samples evenly distributed across three species (Setosa, Versicolor, Virginica), each described by four continuous morphological features (sepal length, sepal width, petal length, petal width).

We propose multinomial logistic regression as our comparison model for Iris species classification.

Specifically, we employ L2-regularized multinomial logistic regression, which models class-conditional probabilities via the softmax function over linear combinations of the four input features [SOURCE-1].

We hypothesize that the linear decision boundaries learned by logistic regression may be sufficient to capture the feature-based separability of the three Iris species.

We use a majority-class predictor as the baseline, which assigns every test sample to the most frequent class observed in the training set.

We select the majority-class predictor as a baseline because it provides a well-defined lower bound on classification performance, enabling the assessment of any added value from the learned model [SOURCE-2].

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that Iris classes are known to exhibit strong feature-based structure.

We use balanced accuracy as the primary evaluation metric.

Balanced accuracy is defined as the macro-average of per-class recall, which equally weights the recall of each class regardless of its frequency [SOURCE-2].

We choose balanced accuracy over raw accuracy because it provides a fairer assessment when per-class performance may differ, ensuring that the majority-class baseline receives a meaningful rather than inflated score [SOURCE-2].

We additionally report ROC-AUC as a secondary metric to capture the quality of the model's probabilistic ranking across classes [SOURCE-2].

We evaluate both the logistic regression model and the majority-class baseline on the same held-out test split of the Iris dataset, ensuring a direct and fair comparison.

Standard regularization strength is used for the logistic regression model, following the default configuration common in prior linear classification work [SOURCE-1].

We hypothesize that the probabilistic output of logistic regression may yield strong ROC-AUC performance, reflecting well-calibrated confidence in correct class assignments.


## Evaluation Plan

We evaluate our approach on the Iris dataset, a widely used multiclass classification benchmark comprising 150 samples evenly distributed across three species—Setosa, Versicolor, and Virginica—each described by four morphological features (sepal length, sepal width, petal length, and petal width) [SOURCE-1].

The Iris dataset has long served as a standard evaluation benchmark for linear classification methods due to its well-documented class structure, balanced class distribution, and varying degrees of inter-class separability, making it an appropriate choice for evaluating logistic regression against a majority-class baseline [SOURCE-1].

Following [SOURCE-2], we adopt balanced accuracy as our primary evaluation metric. Balanced accuracy computes the arithmetic mean of per-class recall, ensuring that each class contributes equally to the score regardless of its prevalence in the dataset.

The balanced accuracy metric is particularly well-suited to our experimental design because it assigns a trivial majority-class predictor a score that reflects its inability to discriminate among classes, rather than an inflated accuracy that could obscure the predictor's limitations [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric, following [SOURCE-2], to capture the ranking quality of the model's predicted class probabilities across all three Iris species.

Our experimental protocol compares two models: (1) logistic regression configured for multiclass classification via a one-vs-rest scheme, serving as the comparison model, and (2) a majority-class predictor that always outputs the most frequent class in the training data, serving as the baseline.

The choice of a majority-class predictor as the baseline is motivated by the need to establish a lower bound on classification performance: any model that fails to substantially exceed this baseline provides no meaningful discriminative signal beyond exploiting class frequency [SOURCE-1].

Both models are trained and evaluated on identical splits of the Iris dataset to ensure a fair comparison, with balanced accuracy and ROC-AUC computed on the held-out test partition.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that the Iris dataset is known to exhibit strong linear separability—particularly between Setosa and the remaining two species [SOURCE-1].

We hypothesize that we further hypothesize that logistic regression will achieve near-perfect ROC-AUC, reflecting well-calibrated and well-separated probability estimates across all three Iris species.

Our results confirm the primary hypothesis: logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming the majority-class baseline, which attains a balanced accuracy of only 0.500 [RESULT-2].

Our results also confirm the secondary hypothesis: logistic regression achieves an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect ranking performance across Iris species.

The gap between the comparison model's balanced accuracy of 0.973 [RESULT-1] and the baseline's balanced accuracy of 0.500 [RESULT-2] demonstrates that logistic regression learns discriminative linear decision boundaries that generalize across all three Iris classes, rather than relying on class frequency alone.


## Discussion and Future Work

Logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, substantially outperforming a majority-class baseline at 0.500 [RESULT-2].

The ROC-AUC of 0.998 [RESULT-3] indicates that logistic regression produces well-separated probability rankings across all three Iris species.

The majority-class baseline balanced accuracy of 0.500 [RESULT-2] reflects the equal class distribution in Iris (50 samples per species) and confirms there is no class imbalance to exploit.

Iris Setosa is linearly separable from Versicolor and Virginica, and the Versicolor–Virginica overlap is modest enough for a linear decision boundary to resolve most cases correctly [SOURCE-1].

Balanced accuracy is an appropriate primary metric for multiclass evaluation because it weights each class equally, preventing any single class from dominating the assessment [SOURCE-2].

We hypothesize that systematic regularization tuning—exploring L1 and L2 penalty strengths—may further improve balanced accuracy beyond 0.973 by reducing overfitting on ambiguous Versicolor–Virginica boundary samples.

We hypothesize that the performance advantage of logistic regression over the majority-class baseline will remain robust under k-fold cross-validation, though the magnitude of the gap may narrow if particular folds concentrate difficult boundary cases.

We hypothesize that incorporating interaction features (e.g., petal area) or polynomial expansions of the original features could push balanced accuracy closer to 1.0, given the near-perfect ranking ability already indicated by an ROC-AUC of 0.998 [RESULT-3].

We aim to applying this same evaluation framework—logistic regression against a majority-class baseline using balanced accuracy—to more complex datasets would reveal regimes where linear models degrade relative to nonlinear alternatives.

The large margin between baseline and comparison model performance (0.973 vs. 0.500 balanced accuracy) demonstrates that even a simple linear classifier extracts rich discriminative signal from four morphological features.


## Conclusion

Logistic regression is a well-established linear classification method widely applied to multiclass problems such as Iris species classification [SOURCE-1].

On the Iris dataset, logistic regression achieved a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3], substantially outperforming the majority-class baseline, which achieved a balanced accuracy of only 0.500 [RESULT-2].

We aim to this work aims to provide a rigorous, reproducible comparison of logistic regression against a majority-class baseline on the Iris dataset, establishing clear performance benchmarks that contextualize linear classifier effectiveness [SOURCE-2].

We aim to this work aims to demonstrate that a straightforward linear classifier paired with an appropriate baseline can reveal the degree of class separability in a dataset, encouraging researchers to report majority-class performance alongside model results [SOURCE-1] [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
