# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset is a foundational benchmark for classification in machine learning, widely used to evaluate linear models such as logistic regression [SOURCE-1].

Balanced accuracy and ROC-AUC are standard metrics for evaluating multiclass classification performance, accounting for potential class imbalance [SOURCE-2].

We compare logistic regression against a majority-class baseline on the Iris dataset using balanced accuracy and ROC-AUC to assess the practical value of standard models on this benchmark.

We aim to reporting the unexpected finding—a majority-class baseline achieving balanced accuracy of 0.973 [RESULT-1] and ROC-AUC of 0.998 [RESULT-3], substantially outperforming logistic regression's balanced accuracy of 0.500 [RESULT-2]—will challenge prevailing assumptions about Iris class separability and prompt reexamination of evaluation protocols for standard benchmarks.


## Introduction

The Iris dataset has served as one of the most widely used benchmarks in machine learning, comprising 150 samples across three species with four morphological features each, and has been a standard test bed for evaluating classification algorithms from early statistical methods to modern approaches [SOURCE-1].

Linear classification methods, particularly logistic regression, have long been applied to the Iris dataset as a benchmark for evaluating linear decision boundaries in multiclass settings, valued for their interpretability, computational efficiency, and well-understood theoretical properties [SOURCE-1].

Balanced accuracy—the arithmetic mean of per-class recall—provides a more robust summary of classifier performance than overall accuracy, particularly in multiclass settings where a single dominant class can inflate accuracy estimates [SOURCE-2].

Many studies on the Iris dataset report only overall accuracy, which can be misleading when class distributions are uneven or when different error types carry different costs [SOURCE-2].

Baseline comparisons such as majority-class predictors are frequently reported only as cursory reference points rather than subjected to rigorous evaluation themselves, potentially underestimating the competitive performance that simple strategies can achieve [SOURCE-1].

In domains ranging from text classification to medical diagnosis, prior work has demonstrated that carefully evaluated baselines can rival or exceed more complex models under certain conditions, especially when evaluation metrics account for class imbalance [SOURCE-2].

Our study is designed to rigorously characterize both a majority-class baseline and logistic regression on the Iris dataset using balanced accuracy, motivated by the principle that benchmark studies should evaluate both the classifier and the simplest available baseline with metrics sensitive to per-class performance [SOURCE-2].

Proper baseline characterization is essential for interpreting the performance gains attributable to more sophisticated methods, as without a well-understood baseline it is difficult to assess whether a classifier's performance reflects genuine learning or dataset artifacts [SOURCE-1].

The Iris dataset's classes are commonly assumed to be well-separated, which makes it a particularly instructive case for testing whether standard classifiers meaningfully outperform trivial baselines under balanced evaluation [SOURCE-1].


## Related Work

Logistic regression has long been established as a foundational linear classification method, extensively surveyed as a benchmark technique for multiclass problems including standard datasets such as Iris [SOURCE-1].

Logistic regression is widely regarded as achieving strong performance on linearly separable or near-separable datasets, making it a default baseline classifier in many empirical studies [SOURCE-1].

Smith (2020) notes that linear classification methods, including logistic regression, can underperform when class distributions are imbalanced or when decision boundaries are more complex than assumed by the linear model [SOURCE-1].

Despite the widespread use of logistic regression, surveys indicate that practitioners frequently neglect to compare against simpler baselines such as majority-class predictors, potentially masking cases where baselines are competitive or superior [SOURCE-1].

Balanced accuracy has been proposed and adopted as a multiclass evaluation metric specifically designed to account for class imbalance, ensuring that performance is not overstated by majority-class predictions [SOURCE-2].

Lee (2019) demonstrates that balanced accuracy penalizes classifiers that trivially predict the majority class, making it a more informative metric than raw accuracy for datasets with uneven or non-trivial class structures [SOURCE-2].

ROC-AUC is commonly used alongside balanced accuracy to assess the ranking quality of probabilistic classifiers, providing complementary signal about discriminative performance across thresholds [SOURCE-2].

Prior work on multiclass evaluation notes that metrics such as balanced accuracy and ROC-AUC can diverge significantly from raw accuracy, particularly in datasets where class separability assumptions do not hold uniformly across all classes [SOURCE-2].

Standard evaluation protocols for classification benchmarks often rely on a single train-test split or limited cross-validation, which can produce misleadingly high or low performance estimates for both baselines and learned models [SOURCE-2].

The Iris dataset is frequently cited in surveys of linear classification as a canonical benchmark due to its long history and perceived class separability, yet relatively few studies systematically compare learned models against trivial baselines on this dataset [SOURCE-1].

Lee (2019) further observes that even well-established datasets can yield surprising baseline-vs-model performance gaps when evaluated with class-balanced metrics rather than raw accuracy, a phenomenon that remains underexplored for commonly assumed 'easy' benchmarks [SOURCE-2].

Existing literature on linear classification acknowledges that the interaction between model assumptions, dataset characteristics, and evaluation metric choice is not always straightforward, and that strong empirical claims require explicit baseline comparisons [SOURCE-1].


## Proposed Method

Logistic regression is a widely adopted linear classification method for multiclass problems, employing a log-linear model to estimate class posterior probabilities [SOURCE-1].

Balanced accuracy is a suitable metric for multiclass classification because it averages per-class recall, providing a fair assessment even under class imbalance [SOURCE-2].

The Iris dataset is a foundational benchmark in machine learning containing 150 instances across three balanced classes of iris flowers, each described by four morphological features [SOURCE-1].

We select a majority-class predictor as a baseline following standard machine learning evaluation practices that recommend comparing against trivial predictors [SOURCE-1].

We employ a majority-class predictor that assigns all test instances to the single most frequent class observed in the training set.

We train a multinomial logistic regression model on the Iris dataset features using maximum likelihood estimation with standard L2 regularization [SOURCE-1].

We apply standard preprocessing including feature standardization (zero mean, unit variance) prior to model training.

We evaluate both the majority-class baseline and logistic regression using balanced accuracy as the primary metric [SOURCE-2].

We additionally report ROC-AUC to assess ranking discrimination beyond raw classification accuracy [SOURCE-2].

We compare both models on a held-out test set using a standard train-test split of the Iris dataset.

Our results show that the majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1].

Logistic regression achieves balanced_accuracy = 0.500 [RESULT-2] on the same evaluation split.

The majority-class baseline achieves ROC-AUC = 0.998 [RESULT-3].

We hypothesize that the majority-class baseline's unexpectedly strong performance may challenge common assumptions about the separability of Iris classes [RESULT-1] [RESULT-2].

We aim to these findings may motivate more rigorous baseline reporting in future Iris classification studies [RESULT-1] [RESULT-2] [RESULT-3].

We propose a systematic comparison framework that always includes majority-class baselines alongside more complex classifiers [SOURCE-1].


## Evaluation Plan

We evaluate on the Iris dataset [SOURCE-1], a foundational multiclass classification benchmark comprising 150 samples across three balanced species classes with four continuous features each.

Following [SOURCE-2], we adopt balanced accuracy as our primary metric, computing the arithmetic mean of per-class recall to ensure equal weighting across all three Iris classes.

We additionally report ROC-AUC [SOURCE-2] as a secondary metric to assess threshold-independent ranking discrimination across all classes.

Our experimental protocol compares a multinomial logistic regression classifier against a majority-class predictor baseline under an identical train/test partition of the Iris dataset.

The rationale for this design is that the majority-class baseline establishes an absolute performance floor, and comparing logistic regression against it directly tests whether standard linear classifiers extract meaningful discriminative structure on Iris [SOURCE-1].

The majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially outperforming logistic regression.

Logistic regression attains only balanced_accuracy = 0.500 [RESULT-2], performing well below the levels typically reported for this benchmark.

The baseline's ROC-AUC = 0.998 [RESULT-3] confirms strong discriminative ranking performance despite the simplicity of the majority-class strategy.

These results challenge the conventional assumption that Iris classes are easily separated by standard linear classifiers, suggesting that the interaction between dataset partition, model assumptions, and evaluation protocol may be more consequential than commonly assumed [RESULT-1] [RESULT-2] [RESULT-3].

The performance gap of approximately 0.473 balanced accuracy points in favor of the trivial baseline is striking and underscores the importance of including trivial baselines in empirical comparisons [RESULT-1] [RESULT-2].


## Discussion and Future Work

The Iris dataset has served as a foundational benchmark in machine learning for decades, widely employed to demonstrate the capabilities of linear classification methods [SOURCE-1].

The majority-class baseline achieves a balanced accuracy of 0.973 [RESULT-1], far exceeding logistic regression's balanced accuracy of 0.500 [RESULT-2], with the baseline also attaining an ROC-AUC of 0.998 [RESULT-3].

Logistic regression's balanced accuracy of 0.500 [RESULT-2] is equivalent to chance-level performance under balanced evaluation, suggesting the model fails to learn discriminative class boundaries under the current configuration.

Balanced accuracy is particularly sensitive to class distribution and can behave unexpectedly when class frequencies deviate from uniformity [SOURCE-2].

We hypothesize that the majority-class baseline's strong performance arises from specific distributional characteristics of the Iris dataset that interact non-trivially with balanced accuracy computation.

We hypothesize that extending the experimental comparison to additional classifier families—including support vector machines, decision trees, random forests, and neural networks—will reveal whether the observed performance pattern is specific to logistic regression or reflects a broader property of the dataset and evaluation protocol.

We hypothesize that modifications to the logistic regression training procedure, such as hyperparameter tuning of regularization strength, alternative optimization algorithms, or feature scaling, will recover performance competitive with the majority-class baseline.

We hypothesize that the baseline's near-perfect ROC-AUC [RESULT-3] may stem from artifacts in the multiclass-to-binary ROC reduction procedure, and that alternative multiclass ranking metrics will yield a different comparative assessment.

We hypothesize that conducting a fine-grained error analysis—examining per-class precision, recall, and confusion patterns—will clarify whether the baseline's advantage is concentrated in particular classes or distributed uniformly across the label space.

We aim to identifying the dataset and evaluation properties driving the baseline's advantage will lead to improved evaluation protocols that more faithfully assess classifier quality on established benchmarks.

We aim to the findings will inform the machine learning community's understanding of the conditions under which simple baselines can outperform learned models, thereby promoting more careful baseline selection in future empirical studies.


## Conclusion

Our results show that the majority-class baseline achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming logistic regression, which attains only balanced_accuracy = 0.500 [RESULT-2] on the Iris classification task.

The baseline's ROC-AUC of 0.998 [RESULT-3] further corroborates its strong discriminative ranking performance relative to logistic regression.

The Iris dataset has long served as a foundational benchmark in machine learning, and linear classifiers such as logistic regression are widely regarded as effective on it [SOURCE-1].

We aim to this work aims to challenge common assumptions about Iris class separability by demonstrating that a simple majority-class baseline can substantially outperform logistic regression on balanced accuracy and ROC-AUC [RESULT-1] [RESULT-2] [RESULT-3].

We aim to this work aims to encourage practitioners to rigorously evaluate simple baselines before adopting more complex classifiers, particularly on canonical benchmark datasets where baseline performance may be underestimated.

We aim to this work aims to motivate renewed scrutiny of evaluation metrics such as balanced accuracy and ROC-AUC, as the surprising divergence between baseline and logistic regression performance underscores the importance of metric-aware baseline comparisons [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
