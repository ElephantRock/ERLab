# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

The Iris dataset is a widely used benchmark for evaluating classification methods in machine learning [SOURCE-1].

Balanced accuracy and ROC-AUC are standard metrics for assessing multiclass classification performance, particularly when class distributions may be imbalanced [SOURCE-2].

We apply multinomial logistic regression to classify Iris flower species based on four morphological features, leveraging the model's simplicity and interpretability for this foundational benchmark [SOURCE-1].

Our results show that logistic regression achieves balanced accuracy of 0.973 [RESULT-1], substantially outperforming a majority-class baseline at 0.500 [RESULT-2].

The model attains ROC-AUC of 0.998 [RESULT-3], demonstrating near-perfect discriminative ability across the three Iris species.

We aim to we expect this evaluation to serve as a reproducible reference point for logistic regression performance on Iris, facilitating comparisons with more complex methods in future work.


## Introduction

Classification of Iris flower species, originally introduced by Anderson and popularized by Fisher, remains one of the most widely used benchmark tasks for evaluating and comparing classification algorithms in machine learning [SOURCE-1].

Linear classification methods, which learn a linear decision boundary between classes, constitute a foundational family of supervised learning algorithms that includes logistic regression, linear discriminant analysis, and linear support vector machines [SOURCE-1].

Logistic regression, in particular, models class-conditional probabilities using the logistic (softmax) function and has been extensively studied for both binary and multiclass problems, making it a well-understood and widely deployed classifier [SOURCE-1].

When evaluating classifiers on datasets with multiple classes—such as Iris with its three species—standard accuracy can be misleading if class distributions are imbalanced, and balanced accuracy along with ROC-AUC have been recommended as more informative metrics for multiclass settings [SOURCE-2].

Despite the existence of more complex nonlinear classifiers, prior surveys have noted that many such methods introduce additional hyperparameters and computational overhead without guaranteed improvements on low-dimensional, well-separated datasets like Iris, where simpler linear models may be sufficient [SOURCE-1].

Furthermore, prior evaluations of classification methods on Iris have frequently relied on plain accuracy without reporting balanced metrics or comparing against a trivial majority-class baseline, making it difficult to assess whether reported performance reflects genuine discriminative ability rather than class-distribution artifacts [SOURCE-2].

The interpretability of logistic regression—where each coefficient directly indicates the contribution of a feature to the log-odds of class membership—makes it an attractive candidate for the Iris task, where understanding the relationship between morphological measurements (sepal and petal dimensions) and species classification is itself of scientific interest [SOURCE-1].

The relatively low dimensionality of the Iris feature space (four real-valued measurements) and the known partial separability of its classes align with the assumptions underlying logistic regression, namely that a linear combination of input features can provide a useful decision boundary [SOURCE-1].

Prior work on linear classification methods has demonstrated that logistic regression provides well-calibrated probability estimates, which are particularly valuable for ROC-AUC evaluation since they yield meaningful ranking information across classification thresholds [SOURCE-1] [SOURCE-2].


## Related Work

Linear classification methods have served as foundational tools in machine learning for decades, providing interpretable and computationally efficient approaches to pattern recognition [SOURCE-1].

Logistic regression remains one of the most widely adopted linear classification techniques, valued for its probabilistic output, interpretability, and compatibility with both binary and multiclass settings [SOURCE-1].

The Iris dataset has been used as a standard benchmark for evaluating and comparing classification algorithms since the early days of statistical learning [SOURCE-1].

Prior surveys of linear classification methods have noted that simple linear models can achieve competitive accuracy on datasets where class boundaries are approximately linearly separable [SOURCE-1].

Regularization techniques such as L1 and L2 penalties have been integrated into logistic regression formulations to mitigate overfitting and improve generalization on finite training samples [SOURCE-1].

However, simple linear classifiers including logistic regression may underperform when the true class boundaries are highly nonlinear, as they are restricted to linear decision surfaces in the feature space [SOURCE-1].

Although multinomial extensions of logistic regression handle multiclass problems, the selection of appropriate regularization strength and optimization strategy remains dataset-dependent and requires empirical tuning [SOURCE-1].

Complex nonlinear models such as kernel methods and neural networks can overfit on small datasets like Iris, where the limited number of training instances constrains the reliable estimation of model parameters [SOURCE-1].

Multiclass classification presents distinct challenges compared to binary classification, particularly with respect to metric selection, class imbalance handling, and interpretation of per-class performance [SOURCE-2].

Balanced accuracy has been proposed as an evaluation metric that addresses class imbalance by computing the arithmetic mean of per-class recall, thereby penalizing classifiers that perform well only on majority classes [SOURCE-2].

ROC-AUC, extended to the multiclass setting through one-vs-rest or one-vs-one averaging, provides a threshold-independent measure of a classifier's ability to discriminate between classes [SOURCE-2].

Standard accuracy can be misleading in multiclass settings with class imbalance, as it may mask poor performance on minority classes and inflate the apparent quality of trivial baselines [SOURCE-2].

The majority-class predictor, which assigns every test instance to the most frequent training class, is commonly employed as a lower-bound baseline for multiclass classification tasks [SOURCE-2].

Multiclass evaluation frameworks extend binary metrics through macro-averaging, micro-averaging, and weighted averaging strategies, each of which emphasizes different aspects of classifier behavior [SOURCE-2].

A significant limitation of many published classification studies is the lack of balanced accuracy reporting, which can obscure per-class weaknesses and hinder fair comparison across methods [SOURCE-2].

The diversity of available averaging strategies can lead to inconsistent conclusions about classifier quality, as different strategies may favor different models depending on the underlying class distribution [SOURCE-2].

Logistic regression has been compared favorably against more complex nonlinear models on small to medium-sized benchmark datasets, where its lower variance and interpretability provide practical advantages [SOURCE-1].

Prior work has emphasized the importance of proper feature scaling prior to fitting logistic regression models, as gradient-based optimization can be sensitive to features with disparate scales [SOURCE-1].

Despite the prevalence of logistic regression in applied machine learning, comprehensive studies that pair it with rigorous multiclass metrics such as balanced accuracy and ROC-AUC on standardized benchmarks remain comparatively scarce [SOURCE-1], [SOURCE-2].

Surveys of linear classification have noted that reported performance figures can vary substantially depending on train-test split protocols, cross-validation folds, and random seed initialization, limiting reproducibility [SOURCE-1].

In multiclass evaluation, ROC-AUC computed via one-vs-rest averaging can produce optimistic estimates when classes are highly imbalanced, necessitating corroboration with metrics such as balanced accuracy [SOURCE-2].


## Proposed Method

Logistic regression models the log-odds of class membership as a linear function of input features and is among the most widely studied linear classification methods in machine learning [SOURCE-1].

The Iris classification task involves assigning each of 150 flower samples to one of three species—Iris setosa, Iris versicolor, or Iris virginica—based on four continuous morphological features.

We formulate the problem as multinomial logistic regression using a softmax activation over three Iris species classes.

The model is trained by minimizing the multinomial cross-entropy loss over the training set.

We select multinomial logistic regression over a one-vs-rest scheme because the softmax formulation jointly optimizes all class boundaries and produces calibrated probability estimates that sum to one across classes [SOURCE-1].

We standardize all features to zero mean and unit variance, with statistics computed on the training split and applied to both training and test splits.

We choose logistic regression for this task because morphological measurements of Iris species are expected to exhibit approximately linear separability, particularly between Iris setosa and the other two species [SOURCE-1].

Logistic regression offers direct interpretability, as each weight coefficient indicates the relative importance and direction of influence of the corresponding feature for class discrimination [SOURCE-1].

We apply L2 regularization to the model weights.

We hypothesize that l2 regularization will mitigate overfitting on the relatively small Iris dataset.

We compare logistic regression against a majority-class baseline that always predicts the most frequent class in the training set.

The majority-class baseline serves as a lower-bound reference point that any classifier learning meaningful feature–label relationships should substantially exceed.

Balanced accuracy computes the arithmetic mean of per-class recall, making it robust to class imbalance and ensuring fair assessment across all three species [SOURCE-2].

We adopt balanced accuracy as our primary evaluation metric to penalize classifiers that perform well on majority classes while failing on minority classes [SOURCE-2].

We report ROC-AUC in addition to balanced accuracy to capture the model's discriminative ability across all decision thresholds [SOURCE-2].

We hypothesize that logistic regression will achieve high balanced accuracy on Iris classification [SOURCE-1].

We hypothesize that the model will substantially outperform the majority-class baseline in balanced accuracy.

We hypothesize that the model will achieve near-perfect class discrimination as measured by ROC-AUC [SOURCE-1].


## Evaluation Plan

We evaluate our approach on the Iris dataset, a standard multiclass classification benchmark widely used in machine learning [SOURCE-1].

Following [SOURCE-2], we employ balanced accuracy as our primary evaluation metric, defined as the arithmetic mean of per-class recall.

We additionally report ROC-AUC as a threshold-independent measure of discriminative ability, following [SOURCE-2].

We compare logistic regression against a majority-class baseline predictor, which always predicts the most frequent class and thus establishes a meaningful lower bound on performance.

Features are standardized to zero mean and unit variance prior to fitting, ensuring that the L2 regularization penalty is applied uniformly across all coefficients.

Both models are evaluated under identical conditions—same data split, same preprocessing pipeline, and same metric computations—ensuring a fair and reproducible comparison.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, given that Iris features carry strong discriminative information across species [SOURCE-1].

Our results confirm this hypothesis: logistic regression achieves [RESULT-1] balanced_accuracy = 0.973, compared to the majority-class baseline at [RESULT-2] balanced_accuracy = 0.500.

We hypothesize that we further hypothesize that logistic regression will demonstrate near-perfect discriminative ability as measured by ROC-AUC, grounded in the high separability of at least one class and strong feature-class correlations [SOURCE-1].

Our results support this hypothesis, with the model achieving [RESULT-3] ROC-AUC = 0.998.

We hypothesize that the majority-class baseline will perform near chance level on balanced accuracy, as it correctly classifies only one of three species [SOURCE-2].


## Discussion and Future Work

Logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] on the Iris dataset, substantially outperforming the majority-class baseline at 0.500 [RESULT-2] [SOURCE-1].

The ROC-AUC of 0.998 [RESULT-3] further confirms near-perfect class separability under this model configuration [SOURCE-2].

These findings are consistent with prior literature documenting the effectiveness of linear classifiers on well-separated datasets such as Iris [SOURCE-1].

The use of balanced accuracy as the primary metric is appropriate for multiclass evaluation, as it equally weights per-class performance and avoids inflation from class imbalance [SOURCE-2].

The residual misclassifications likely occur near the decision boundary between Iris versicolor and Iris virginica, where morphological measurements overlap [SOURCE-1].

We hypothesize that incorporating polynomial feature interactions—such as products of petal and sepal dimensions—may improve the decision boundary near overlapping class regions [SOURCE-1].

We hypothesize that applying L1 or L2 regularization could yield a more parsimonious model without meaningfully sacrificing predictive performance [SOURCE-1].

We hypothesize that the same logistic regression pipeline could generalize to other botanical species classification tasks that use similarly structured tabular morphological data.

We aim to this work contributes a transparent, reproducible baseline for Iris classification—reporting balanced accuracy, ROC-AUC, and a majority-class comparator—that future studies can reference when evaluating more complex models [SOURCE-2].


## Conclusion

Classification of Iris flower species is a foundational benchmark in machine learning, commonly used to evaluate linear and nonlinear models alike [SOURCE-1].

Our results show that logistic regression achieves balanced_accuracy = 0.973 [RESULT-1] on the Iris dataset, substantially outperforming the majority-class baseline at balanced_accuracy = 0.500 [RESULT-2].

The model also achieves ROC-AUC = 0.998 [RESULT-3], indicating near-perfect discriminative ability across classes.

We aim to this work aims to demonstrate that logistic regression, a simple and interpretable linear model, provides strong multiclass classification performance on the Iris dataset while remaining transparent in its decision boundaries [SOURCE-1].

We aim to this work aims to establish logistic regression as a competitive, lightweight baseline for multiclass classification benchmarks, offering a practical reference point for future model comparisons [SOURCE-1] [SOURCE-2].

Balanced accuracy and ROC-AUC were chosen as primary evaluation metrics because they account for class imbalance and capture discriminative quality beyond simple accuracy [SOURCE-2].

We aim to this work aims to show that the performance gap between logistic regression and a naive majority-class predictor is both large and practically meaningful, as evidenced by the observed difference between [RESULT-1] and [RESULT-2].


## References

[Generated from 2 source papers — see proposal for full bibliography]
