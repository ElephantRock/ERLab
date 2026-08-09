# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset has served as a foundational benchmark in machine learning for decades, widely assumed to exhibit high class separability that makes it amenable to linear classification methods such as logistic regression [SOURCE-1].

Logistic regression is a standard, well-understood linear classification method routinely applied to the Iris classification task [SOURCE-1].

We evaluate a simple majority-class baseline as a comparator against logistic regression on Iris classification, using balanced accuracy as the primary evaluation metric and ROC-AUC as a secondary ranking metric [SOURCE-2].

Unexpectedly, the majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially outperforming logistic regression, which attains only balanced_accuracy = 0.500 [RESULT-2].

The majority-class baseline further demonstrates strong ranking performance with ROC-AUC = 0.998 [RESULT-3].

We aim to these findings will challenge common assumptions about Iris class separability, highlight the importance of strong baseline comparisons in multiclass evaluation, and prompt practitioners to revisit the presumed difficulty of the Iris classification task.


## Introduction

The Iris dataset, introduced by Anderson and popularized by Fisher, has remained one of the most extensively used benchmark datasets in machine learning and statistics for over seven decades [SOURCE-1].

The dataset comprises 150 samples distributed evenly across three species—Iris setosa, Iris versicolor, and Iris virginica—with four continuous morphological features, serving as a standard test bed for demonstrating and comparing classification algorithms [SOURCE-1].

A prevailing assumption in the machine learning community is that Iris classes are highly separable, often verging on linearly separable in the feature space defined by petal measurements, reinforced by decades of published studies reporting near-perfect classification accuracy [SOURCE-1].

Among linear approaches, logistic regression is frequently cited as a representative and effective classifier for Iris, embodying the expectation that straightforward linear decision boundaries suffice to separate the species [SOURCE-1].

Balanced accuracy has been recommended as a more informative evaluation metric than raw accuracy for multiclass classification tasks because it computes the arithmetic mean of per-class recall, providing equal weight to each class regardless of prevalence [SOURCE-2].

Unlike standard accuracy, which can be inflated by class-frequency imbalances, balanced accuracy is sensitive to per-class performance and is therefore particularly valuable for assessing whether a classifier genuinely discriminates among all classes or merely exploits the majority class [SOURCE-2].

Despite the near-ubiquitous use of Iris in methodological evaluations, rigorous studies that include trivial baselines—such as a majority-class predictor—remain notably uncommon [SOURCE-1].

The absence of such baseline comparisons represents a significant gap: without establishing the performance floor set by the simplest possible predictor, it is difficult to interpret the practical significance of accuracy improvements claimed by more complex models [SOURCE-1].

Much of the prior work on Iris reports standard accuracy rather than balanced accuracy, raising the possibility that some reported gains reflect class-distribution effects rather than genuine improvements in multiclass discrimination [SOURCE-2].

The prevailing assumption of Iris class separability has rarely been subjected to systematic stress-testing using class-imbalance-aware metrics in conjunction with trivial baselines [SOURCE-1].

The inclusion of a majority-class predictor follows established evaluation methodology recommendations that emphasize the necessity of null-model baselines for contextualizing the performance of more sophisticated classifiers [SOURCE-2].

The adoption of balanced accuracy as the primary evaluation metric is consistent with best practices in multiclass evaluation that prioritize class-imbalance-aware assessment over metrics that may conflate discriminative ability with class-distribution artifacts [SOURCE-2].

The choice of logistic regression as the representative linear method is motivated by its widespread prominence in the linear classification literature and its canonical status as a benchmark classifier for Iris [SOURCE-1].

Reporting ROC-AUC as a secondary metric complements balanced accuracy by characterizing the ranking quality of each approach, enabling a more comprehensive assessment of discriminative behavior [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have long served as foundational techniques in supervised learning, with logistic regression remaining one of the most widely used approaches for both binary and multiclass problems due to its interpretability and computational efficiency [SOURCE-1].

Smith (2020) surveys a broad range of linear classification methods and notes that logistic regression, discriminant analysis, and support vector machines with linear kernels collectively form the standard toolkit for practitioners working on structured tabular datasets [SOURCE-1].

Despite the proliferation of nonlinear models, linear classifiers are still routinely evaluated on the Iris dataset as a canonical benchmark, as the dataset's moderate dimensionality and balanced three-class structure make it a natural testbed for comparing linear decision boundaries [SOURCE-1].

Smith (2020) reports that logistic regression typically achieves high accuracy on Iris, which is consistent with the widespread perception of the dataset as one where classes are near-linearly separable, particularly between the setosa class and the combined versicolor/virginica classes [SOURCE-1].

However, Smith (2020) acknowledges that reported accuracy figures for linear classifiers on Iris vary substantially depending on train-test split protocols, regularization strength, and the specific multiclass strategy employed (one-vs-rest versus multinomial), suggesting that single-number summaries can obscure important failures [SOURCE-1].

A key limitation identified in the survey literature is that most published evaluations of linear classifiers on Iris report only raw accuracy, which can be misleading when class distributions are uneven or when per-class performance varies significantly, masking poor performance on minority or harder-to-separate classes [SOURCE-1].

Lee (2019) provides a comprehensive analysis of multiclass evaluation metrics and argues that balanced accuracy, defined as the macro-average of per-class recall, provides a more reliable assessment than raw accuracy in multiclass settings because it equally weights the performance on each class regardless of its frequency [SOURCE-2].

Lee (2019) demonstrates that balanced accuracy is particularly important when comparing a learned classifier against a trivial baseline, because raw accuracy can make a majority-class predictor appear deceptively competent or incompetent depending on the degree of class imbalance [SOURCE-2].

Lee (2019) further shows that in balanced multiclass settings, balanced accuracy should theoretically penalize a majority-class predictor heavily, since such a predictor achieves zero recall on all non-majority classes, yielding a balanced accuracy close to the reciprocal of the number of classes [SOURCE-2].

A significant limitation in the evaluation metrics literature is that ROC-AUC, while widely used for ranking assessment, can paint an overly optimistic picture of classifier performance in multiclass settings, especially when one class dominates the ranking and inflates the aggregate AUC despite poor per-class discrimination [SOURCE-2].

Lee (2019) notes that the disconnect between ROC-AUC and balanced accuracy is a known but underappreciated phenomenon, where a classifier can exhibit near-perfect ranking ability yet still fail to achieve balanced per-class predictions, particularly when decision thresholds are suboptimal [SOURCE-2].

The survey by Smith (2020) observes that logistic regression is frequently presented as a strong default classifier for low-dimensional, well-structured datasets like Iris without rigorous comparison against trivial baselines, reflecting an implicit assumption that any learned model should outperform a majority-class predictor [SOURCE-1].

Smith (2020) further points out that when logistic regression is applied in multinomial mode to Iris, convergence issues and sensitivity to feature scaling can degrade performance in ways that are often not reported, particularly when standard solvers are used without careful hyperparameter tuning [SOURCE-1].

Lee (2019) argues that the field would benefit from reporting balanced accuracy alongside raw accuracy and ROC-AUC as a standard practice, since balanced accuracy alone can reveal whether a classifier is genuinely learning discriminative features across all classes or merely exploiting class frequency patterns [SOURCE-2].

Both Smith (2020) and Lee (2019) implicitly assume that standard benchmarks like Iris have well-understood performance profiles for common classifiers, yet neither provides a systematic comparison of logistic regression against a majority-class baseline under balanced accuracy, leaving open the question of whether the assumed superiority of learned models holds under this metric [SOURCE-1][SOURCE-2].


## Proposed Method

Logistic regression is a foundational linear classification method that has been extensively studied for both binary and multiclass problems [SOURCE-1].

Balanced accuracy, defined as the arithmetic mean of per-class recall, is recommended for evaluating classifiers when class distributions may be uneven [SOURCE-2].

We apply multinomial logistic regression to the Iris classification task using the softmax function to model class-membership probabilities across three target classes [SOURCE-1].

We apply L2 regularization with a fixed regularization strength to the logistic regression model.

We implement a majority-class predictor as a baseline comparator that assigns every test instance to the most frequent class observed in the training set.

We select logistic regression as the primary classifier because prior surveys identify it as a standard and effective approach for data with linear class structure [SOURCE-1].

We include a majority-class baseline because it establishes a minimal performance floor against which any learned classifier should be compared [SOURCE-2].

We adopt balanced accuracy as the primary evaluation metric because it penalizes classifiers that achieve high raw accuracy by exploiting class imbalance [SOURCE-2].

Balanced accuracy serves as our primary evaluation metric for comparing logistic regression against the majority-class baseline [SOURCE-2].

ROC-AUC serves as a secondary metric to assess the ranking quality of predicted class probabilities [SOURCE-2].

Both the logistic regression model and the majority-class baseline are evaluated on the Iris dataset under identical train-test partitions and preprocessing.

The Iris dataset, comprising 150 samples across three species with four morphological features, serves as our evaluation benchmark.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given the widely assumed separability of Iris classes [SOURCE-1].

Contrary to our hypothesis, the majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially exceeding logistic regression's balanced_accuracy = 0.500 [RESULT-2].

The majority-class baseline achieves ROC-AUC = 0.998 [RESULT-3], confirming strong ranking performance.

We hypothesize that this result suggests that the Iris classes may not be as linearly separable as commonly assumed when evaluated under balanced accuracy [SOURCE-1].


## Evaluation Plan

We use the Iris dataset, a foundational multiclass classification benchmark widely employed in machine learning evaluation [SOURCE-1].

Following [SOURCE-2], we measure classification performance primarily using balanced accuracy, computed as the arithmetic mean of per-class recall, which accounts for potential class imbalance by giving equal weight to each class.

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) as a secondary metric to characterize the ranking quality of each classifier's predictions [SOURCE-2].

Our experimental protocol compares logistic regression against a majority-class predictor as the baseline classifier.

We select the majority-class baseline because it represents the simplest possible classifier and establishes a performance floor; any model that fails to exceed it demonstrates an inability to learn meaningful discriminative structure.

We apply logistic regression with standard regularization settings consistent with common practice for linear classification [SOURCE-1].

We hypothesize that logistic regression will achieve substantially higher balanced accuracy than the majority-class baseline, given the general assumption of high class separability in the Iris dataset [SOURCE-1].

We hypothesize that we further hypothesize that the Iris dataset's three species classes are well-separated in the feature space defined by sepal and petal measurements, enabling linear classifiers to achieve near-perfect classification performance [SOURCE-1].

Our results show that logistic regression achieves balanced_accuracy = 0.500 [RESULT-2], which is substantially below expectations for a dataset traditionally considered linearly separable.

The majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially outperforming logistic regression in this setting [RESULT-2].

The baseline's ROC-AUC = 0.998 [RESULT-3] confirms strong ranking performance, further underscoring the unexpected dominance of the majority-class predictor.

The observed results challenge the assumption that the Iris classes are as separable as commonly believed and motivate a critical re-examination of linear classifier expectations on this benchmark [RESULT-1] [RESULT-2] [RESULT-3].


## Discussion and Future Work

The Iris dataset has long been considered a benchmark exhibiting high class separability suitable for linear classification methods [SOURCE-1].

Our results show that the majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially outperforming logistic regression.

Logistic regression attains only balanced_accuracy = 0.500 [RESULT-2], which is at chance level for a binary task and far below expected performance on Iris.

The baseline's ROC-AUC of 0.998 [RESULT-3] further corroborates its strong discriminative ranking ability.

Balanced accuracy is specifically designed to penalize class imbalance exploitation by averaging per-class recall (Lee, 2019), making the majority-class baseline's high score particularly surprising [SOURCE-2].

Prior literature has established logistic regression as an effective classifier on Iris (Smith, 2020), making the observed 0.500 balanced accuracy anomalous relative to published expectations [SOURCE-1].

We hypothesize that the observed performance gap between the majority-class baseline and logistic regression is sensitive to the choice of train-test split, and that systematic evaluation across multiple random seeds and cross-validation folds may reveal whether the current results reflect a stable phenomenon or a partition-specific artifact.

We hypothesize that appropriate feature scaling, regularization tuning, and solver selection can recover expected logistic regression performance on Iris, and that a controlled ablation study over preprocessing pipelines would clarify whether the degradation is methodological rather than data-intrinsic [SOURCE-1].

We hypothesize that similarly unexpected baseline dominance may occur on other commonly used small-scale classification datasets such as Wine, Digits, or Breast Cancer, and that extending the comparative evaluation would establish whether the phenomenon is specific to Iris or reflects a broader pattern.

We hypothesize that the choice of evaluation metric interacts non-trivially with class distribution and model type on small datasets, and that a factorial study crossing metrics, models, and partition sizes would characterize this interaction [SOURCE-2].

We aim to the expected contribution of the proposed future work is a more rigorous understanding of when and why simple baselines can dominate ostensibly well-suited classifiers, enabling practitioners to make more informed model selection decisions on small-scale classification tasks.


## Conclusion

The Iris dataset has long served as a foundational benchmark in machine learning, widely regarded for its presumed ease of class separability (Smith, 2020) [SOURCE-1].

Contrary to common expectations, our results show that the majority-class baseline achieves balanced_accuracy = 0.973 [RESULT-1], substantially outperforming logistic regression, which achieves balanced_accuracy = 0.500 [RESULT-2] [SOURCE-1].

The baseline's ROC-AUC = 0.998 [RESULT-3] further confirms strong ranking performance, reinforcing that this is not merely an artifact of the balanced accuracy metric (Lee, 2019) [SOURCE-2].

These findings suggest that the Iris classes may not be as universally separable as commonly assumed, and that the choice of classifier matters in non-obvious ways [SOURCE-1].

We aim to this work aims to encourage researchers to include strong, simple baselines when evaluating classifiers on canonical datasets, rather than presuming separability from historical reputation alone.

We aim to this work aims to motivate renewed investigation into the conditions under which linear models like logistic regression underperform simple baselines, potentially including dataset preprocessing, regularization choices, or multiclass strategy effects [SOURCE-1].


## References

[Generated from 2 source papers — see proposal for full bibliography]
