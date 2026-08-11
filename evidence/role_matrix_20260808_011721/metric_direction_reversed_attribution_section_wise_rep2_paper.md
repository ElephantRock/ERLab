# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset is a canonical benchmark in machine learning for evaluating multi-class classification algorithms [SOURCE-1].

Logistic regression models class-conditional probabilities through a linear decision boundary, making it a principled and interpretable approach for multi-class classification tasks [SOURCE-1].

We apply logistic regression to the Iris dataset for multi-class flower species classification, comparing against a majority-class baseline using balanced accuracy as the primary evaluation metric [SOURCE-2].

We aim to logistic regression will substantially outperform the majority-class baseline on balanced accuracy, demonstrating the effectiveness of linear classification on this benchmark.


## Introduction

The Iris dataset, introduced by Fisher, remains one of the most widely used benchmarks for evaluating classification algorithms in machine learning [SOURCE-1].

Logistic regression is a foundational linear classification method that has been extensively studied and applied to multi-class problems through extensions such as multinomial logistic regression [SOURCE-1].

Linear classifiers, including logistic regression, are particularly well suited to problems where classes are approximately linearly separable in the feature space [SOURCE-1].

Balanced accuracy is a preferred evaluation metric for classification tasks because it averages per-class recall and is robust to class imbalance, unlike raw accuracy [SOURCE-2].

In multi-class settings, metrics such as balanced accuracy and ROC-AUC provide complementary views of model performance, capturing both classification correctness and ranking quality [SOURCE-2].

Many prior evaluations of classifiers on benchmark datasets fail to establish an explicit baseline, making it difficult to interpret whether reported accuracy reflects genuine discriminative power or simply class distribution artifacts [SOURCE-1].

Studies on classification evaluation have noted that reporting only aggregate accuracy can obscure per-class failures, particularly when class distributions are skewed [SOURCE-2].

Prior surveys of linear methods indicate that logistic regression is often deployed without systematic comparison to trivial baselines, raising questions about the practical significance of reported performance gains [SOURCE-1].

To contextualize model performance, best practice in classification evaluation recommends comparing against a majority-class predictor, which assigns all instances to the most frequent class and establishes a floor for meaningful performance [SOURCE-2].

The use of balanced accuracy as the primary metric follows established guidelines for fair evaluation across classes, as it penalizes models that perform well only on the majority class [SOURCE-2].

Logistic regression has been previously demonstrated as an effective baseline classifier on structured tabular datasets, making it a natural candidate for systematic evaluation on Iris [SOURCE-1].

The Iris dataset, with its four continuous features and three balanced classes, provides a controlled setting in which to evaluate whether a linear model can exceed the performance of a trivial majority-class predictor under balanced evaluation [SOURCE-1] [SOURCE-2].


## Related Work

The Iris dataset has served as a canonical benchmark for evaluating classification algorithms for decades, with numerous studies reporting near-perfect accuracy across a variety of supervised methods [SOURCE-1].

Linear classification methods, including logistic regression, have been widely applied to multiclass problems due to their simplicity, interpretability, and competitive performance on low-dimensional feature spaces [SOURCE-1].

Prior surveys of linear classification note that logistic regression extends naturally to multiclass settings via softmax (multinomial) formulations, making it suitable for datasets with more than two classes such as Iris [SOURCE-1].

Despite the prevalence of accuracy as a reporting metric, studies have emphasized that accuracy can be misleading under class imbalance, and balanced accuracy has been recommended as a more robust alternative for multiclass evaluation [SOURCE-2].

A majority-class predictor, which assigns all instances to the most frequent class, is commonly employed as a naive baseline in classification studies, yet it is known to achieve low balanced accuracy when classes are roughly equal in size [SOURCE-2].

While many published studies report only raw accuracy on Iris, fewer works systematically report balanced accuracy alongside a majority-class baseline, limiting the ability to assess whether observed performance reflects genuine class discrimination rather than class-frequency artifacts [SOURCE-2].

Prior work on linear classification surveys has noted that logistic regression can struggle when classes are not linearly separable, although the Iris dataset is generally regarded as exhibiting high separability for at least one class boundary [SOURCE-1].

Evaluation metric studies have pointed out that ROC-AUC, while informative for binary settings, requires careful extension to multiclass problems and may not capture per-class performance trade-offs when used in isolation [SOURCE-2].

Comprehensive surveys of linear methods have observed that regularization strength and solver choice can materially affect logistic regression performance on small datasets, yet many experimental reports omit these details, complicating cross-study comparison [SOURCE-1].

Prior evaluations of multiclass metrics have shown that balanced accuracy reduces to standard accuracy when classes are perfectly balanced, but diverges sharply when a classifier systematically mispredicts minority classes, as is the case with a majority-class baseline [SOURCE-2].

Surveys of linear classification methods report that logistic regression consistently ranks among the top-performing linear models on small, well-structured benchmark datasets where feature dimensions are low and classes are reasonably separable [SOURCE-1].

Prior work has noted that the majority-class baseline is often omitted from classification studies on benchmark datasets like Iris, where strong classifier performance is assumed, making it difficult to contextualize whether reported accuracies represent meaningful improvements over trivial prediction strategies [SOURCE-2].


## Proposed Method

The Iris classification task is a multi-class problem in which each instance must be assigned to one of three species—Iris setosa, Iris versicolor, or Iris virginica—based on four continuous morphological features: sepal length, sepal width, petal length, and petal width.

We formalize the task as learning a mapping from feature vectors in R^4 to class labels in {0, 1, 2} from a labeled training set.

We employ multinomial logistic regression (softmax regression) as our comparison model.

For a given input feature vector x, the model computes the probability of each class k using the softmax function: P(y=k | x) = exp(w_k^T x + b_k) / sum_j exp(w_j^T x + b_j), and predicts the class with the highest probability.

The model parameters are estimated by minimizing the L2-regularized cross-entropy loss over the training data, optimized using the L-BFGS algorithm.

Prior surveys of linear classification methods have established that logistic regression produces well-calibrated probability estimates and achieves competitive performance on low-dimensional datasets with near-linear class boundaries [SOURCE-1].

Logistic regression is a convex optimization problem, guaranteeing convergence to a global optimum [SOURCE-1].

We select logistic regression for the Iris task because the dataset's four-feature representation and moderate sample size (150 instances) fall within the regime where linear models are expected to perform well [SOURCE-1].

We establish a majority-class predictor as our baseline, which assigns every test instance to the class most frequently observed in the training data.

The majority-class predictor represents the performance floor for any classifier that has learned class-discriminative features [SOURCE-2].

We adopt balanced accuracy as the primary evaluation metric, defined as the unweighted mean of per-class recall.

Balanced accuracy is preferred over raw accuracy because it equally weights the recall of each class, preventing inflated scores from class imbalance [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC), computed as the one-vs-rest macro-average, as a secondary metric.

ROC-AUC quantifies the model's ability to rank instances by their predicted class probabilities, providing a threshold-independent measure of classification quality [SOURCE-2].

We partition the Iris dataset into training and test sets using a standard holdout protocol, training both the comparison model and the baseline on the training partition.

The logistic regression model is trained with L2 regularization, with the regularization strength selected via cross-validation on the training set.

We hypothesize that logistic regression will achieve substantially higher balanced accuracy than the majority-class baseline on the Iris dataset.

Our results show that the logistic regression comparison model achieves a balanced accuracy of 0.973 [RESULT-1] [SOURCE-2].

The majority-class baseline achieves a balanced accuracy of 0.500 [RESULT-2] [SOURCE-2].

The logistic regression model achieves a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class-ranking performance [SOURCE-2].

Our results demonstrate that the logistic regression comparison model substantially outperforms the majority-class baseline on balanced accuracy (0.973 vs. 0.500) [RESULT-1][RESULT-2] [SOURCE-2].


## Evaluation Plan

We evaluate logistic regression on the Iris dataset [SOURCE-1], a widely recognized multi-class classification benchmark containing 150 flower samples across three Iris species with four morphological features per sample.

Following established practices for multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary metric, defined as the arithmetic mean of per-class recall.

We additionally report the Area Under the Receiver Operating Characteristic Curve (ROC-AUC) to characterize the quality of the model's class probability rankings [SOURCE-2].

Our experimental design centers on a controlled comparison between a multinomial logistic regression model and a majority-class baseline predictor, quantifying the improvement that a learned linear classifier provides over the simplest possible baseline.

The majority-class baseline assigns the single most frequent training-set label to every instance, yielding uniform predictions.

Logistic regression is fit on the Iris dataset using multinomial (softmax) regression with standard L2 regularization, and both models are evaluated under identical conditions using balanced accuracy and ROC-AUC.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, as the Iris dataset is known to exhibit strong linear separability between species [SOURCE-1].

We hypothesize that the majority-class baseline will yield low balanced accuracy, near the level expected from a single-class predictor on a roughly balanced three-class problem.

We hypothesize that logistic regression will achieve a high ROC-AUC, reflecting well-separated class probability estimates.

The logistic regression model attains a balanced accuracy of [RESULT-1], substantially exceeding the majority-class baseline.

The majority-class baseline achieves a balanced accuracy of only [RESULT-2].

Logistic regression demonstrates excellent ranking quality with an ROC-AUC of [RESULT-3].


## Discussion and Future Work

The Iris dataset has long served as a foundational benchmark for evaluating linear classification methods, offering a compact yet ecologically meaningful feature space for multi-class discrimination [SOURCE-1].

Our experimental results demonstrate that logistic regression achieves a balanced accuracy of [RESULT-1], nearly doubling the majority-class baseline's balanced accuracy of [RESULT-2], which underscores the model's ability to exploit genuine discriminative structure in the Iris feature space.

The comparison model achieves an ROC-AUC of [RESULT-3], indicating near-perfect ranking performance across the three Iris species and suggesting that the model's predicted class probabilities are well-calibrated [SOURCE-2].

Balanced accuracy provides a fairer assessment than raw accuracy for multi-class settings because it averages per-class recall, which is important when class distributions may be uneven [SOURCE-2].

The majority-class baseline's balanced accuracy of [RESULT-2] represents the expected performance ceiling of a trivial classifier in a three-class setting with approximately equal class frequencies, serving as a meaningful lower bound [SOURCE-2].

These findings are consistent with the broader literature establishing that linear models are well-suited to the Iris dataset due to the natural separation provided by sepal and petal measurements [SOURCE-1] [RESULT-1].

Despite the strong overall performance, the residual 2.7% classification error suggests that complete linear separability is not achieved, likely due to morphometric overlap between species such as Iris versicolor and Iris virginica [RESULT-1].

We hypothesize that incorporating polynomial feature interactions could improve classification performance beyond what is achievable with purely linear features, particularly for borderline specimens near class boundaries where species overlap is most pronounced [RESULT-1].

We hypothesize that the near-perfect ROC-AUC observed in this evaluation may transfer to other botanical classification tasks with similar morphometric feature spaces, though this remains untested and would require empirical validation across diverse taxonomic groups [RESULT-3].

We hypothesize that a systematic per-class error analysis could reveal whether specific Iris species pairs contribute disproportionately to the residual classification error, thereby informing targeted feature engineering [RESULT-1].

We aim to extending this evaluation framework to include regularization path analysis will yield deeper insight into the trade-offs between model complexity and generalization, particularly on small datasets where overfitting risk is elevated [SOURCE-1].

We aim to we anticipate that comparative studies involving kernel methods, random forests, and gradient-boosted classifiers on the same benchmark will help contextualize logistic regression's strong performance and clarify whether added model complexity is justified for this task [SOURCE-1] [RESULT-1].


## Conclusion

The Iris dataset remains a canonical benchmark for evaluating classification methods in machine learning [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming the majority-class baseline, which achieves a balanced accuracy of 0.500 [RESULT-2].

The logistic regression model also demonstrates strong discriminative ranking performance, achieving an ROC-AUC of 0.998 [RESULT-3].

We aim to this work aims to reinforce the suitability of logistic regression as an effective and interpretable classifier for multi-class Iris classification, with near-perfect balanced accuracy and ROC-AUC [RESULT-1] [RESULT-3].

We aim to this work aims to highlight the importance of balanced evaluation metrics in multi-class settings, as the majority-class predictor's balanced accuracy of 0.500 [RESULT-2] illustrates the inadequacy of naive baselines for fair class-level assessment [SOURCE-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
