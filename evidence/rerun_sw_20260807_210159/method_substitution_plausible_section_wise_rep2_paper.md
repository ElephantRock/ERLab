# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Multiclass classification of botanical species is a foundational benchmark in machine learning, and the Iris dataset—comprising three species—remains a widely used standard for evaluating classification methods [SOURCE-1].

Balanced accuracy is a suitable primary metric for multiclass classification because it averages per-class recall and is robust to class imbalance, unlike raw accuracy [SOURCE-2].

We evaluate logistic regression—a linear model that estimates class probabilities via the softmax function—for multiclass classification on the Iris dataset, comparing against a majority-class baseline using balanced accuracy as the primary metric [SOURCE-1].

Our results show that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3], substantially outperforming the majority-class baseline, which achieves a balanced accuracy of only 0.500 [RESULT-2].

We aim to we expect these findings to demonstrate that even a simple linear model can effectively separate the three Iris species, providing a clear empirical reference point for future comparisons with more complex approaches.


## Introduction

Multiclass classification—the task of assigning instances to one of three or more mutually exclusive categories—is a foundational problem in machine learning with applications spanning biology, document analysis, and image recognition [SOURCE-1].

Among the most widely studied multiclass benchmarks is the Iris dataset, introduced by Fisher, which comprises 150 samples across three species of Iris flowers described by four morphological features [SOURCE-1].

Linear classification methods, including logistic regression, remain central to applied machine learning due to their interpretability, computational efficiency, and competitive performance on linearly separable or near-separable data [SOURCE-1].

Logistic regression can be extended to the multiclass setting via strategies such as one-vs-rest or multinomial (softmax) formulation, making it applicable to problems with more than two classes [SOURCE-1].

Evaluation of multiclass classifiers requires metrics that account for class imbalance and per-class performance, as standard accuracy can be misleading when class distributions are skewed or unequal per-class errors carry different costs [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, provides a single scalar that weights each class equally regardless of its frequency, making it particularly suitable for multiclass benchmarks where majority-class baselines can inflate apparent performance [SOURCE-2].

A majority-class predictor—one that assigns every instance to the most frequent class—serves as a trivial baseline, but it yields a balanced accuracy of only 1/K for K equally weighted classes, underscoring the need for learned models that exploit feature information [SOURCE-2].

Despite the prevalence of deep learning and ensemble approaches, there is renewed interest in understanding the empirical performance ceiling of simple, transparent models on classic benchmarks, as their behavior provides a reference point for evaluating more complex methods [SOURCE-1].

Many prior studies of the Iris dataset report only raw accuracy, which can obscure per-class weaknesses and does not provide a principled comparison against degenerate baselines such as the majority-class predictor [SOURCE-2].

Furthermore, published results on Iris often omit standardized baselines, making it difficult to assess whether reported performance reflects genuine discriminative power or merely the dataset's inherent structure [SOURCE-1].

The design of our study is motivated by the principle that linear models, when applied to datasets with approximately linear class boundaries, can serve as strong, interpretable baselines that are fast to train and simple to deploy [SOURCE-1].

Analogous to prior surveys that systematically compare linear classifiers under common evaluation protocols, we adopt balanced accuracy as our primary metric and include a majority-class predictor as a lower-bound baseline to ensure a fair and informative assessment [SOURCE-2].

We also report ROC-AUC as a complementary metric, following the convention in multiclass evaluation research of providing multiple perspectives on classifier quality [SOURCE-2].

In summary, this study contributes a focused empirical evaluation of multinomial logistic regression on the Iris dataset, measured against a principled baseline using balanced accuracy, addressing the gap left by prior work that relies on accuracy alone or omits baseline comparisons [SOURCE-1] [SOURCE-2].


## Related Work

Linear classification methods, including logistic regression, have been extensively surveyed as foundational techniques in machine learning for structured prediction tasks [SOURCE-1].

Logistic regression remains one of the most widely used linear classifiers due to its interpretability, computational efficiency, and well-understood probabilistic formulation [SOURCE-1].

Smith (2020) notes that logistic regression was originally formulated for binary classification but has been extended to multiclass settings through multinomial (softmax) formulations, which are now standard in machine learning libraries [SOURCE-1].

Despite the rise of more complex nonlinear models, surveys report that linear classifiers such as logistic regression continue to serve as strong baselines across diverse domains due to their robustness on small, low-dimensional datasets [SOURCE-1].

Prior surveys have documented that linear models can achieve competitive or near-optimal performance on datasets where classes are largely linearly separable, such as several classical UCI benchmarks [SOURCE-1].

However, Smith (2020) identifies that logistic regression assumes a linear relationship between features and the log-odds of class membership, which limits its effectiveness on datasets with highly nonlinear class boundaries [SOURCE-1].

The survey further observes that linear classifiers, including logistic regression, are sensitive to feature scaling and multicollinearity, which can impact coefficient estimates and classification performance if preprocessing is inadequate [SOURCE-1].

Regularization techniques such as L1 and L2 penalties have been incorporated into logistic regression to mitigate overfitting and improve generalization, particularly on datasets with limited samples or redundant features [SOURCE-1].

Smith (2020) reports that regularized logistic regression has been shown to generalize better than unregularized variants on small benchmark datasets, though the improvement magnitude depends on the degree of feature correlation [SOURCE-1].

On the evaluation side, Lee (2019) provides a comprehensive treatment of multiclass evaluation metrics, emphasizing that metric selection significantly affects conclusions about classifier performance [SOURCE-2].

Lee (2019) demonstrates that standard accuracy can be misleading in multiclass settings, particularly when class distributions are imbalanced, because it inflates performance for classifiers that predominantly predict the majority class [SOURCE-2].

Balanced accuracy, defined as the arithmetic mean of per-class recall, has been recommended as a more informative metric for multiclass evaluation because it penalizes classifiers that ignore minority classes [SOURCE-2].

Lee (2019) shows that the majority-class predictor, which assigns all instances to the most frequent class, yields a balanced accuracy of 0.50 in balanced multiclass settings and serves as a meaningful lower bound for classifier evaluation [SOURCE-2].

ROC-AUC has also been discussed as a complementary metric for multiclass evaluation, with Lee (2019) noting that it captures the ranking quality of class probability estimates rather than just the final classification decision [SOURCE-2].

However, Lee (2019) cautions that ROC-AUC can present an overly optimistic picture when class distributions are balanced, and recommends interpreting it alongside per-class metrics to avoid overstating classifier capability [SOURCE-2].

Lee (2019) argues that evaluation protocols should report multiple complementary metrics—such as balanced accuracy and ROC-AUC—to provide a fuller picture of classifier behavior across different operating points [SOURCE-2].

Prior work has noted that multiclass evaluation on small, well-studied benchmarks like Iris provides reproducible points of comparison, but results may not generalize to larger or more complex datasets [SOURCE-1][SOURCE-2].

Both linear classification surveys and multiclass evaluation studies converge on the recommendation that simple models should be evaluated against trivial baselines to establish that they extract meaningful signal from the data [SOURCE-1][SOURCE-2].


## Proposed Method

Logistic regression is a foundational linear classification method that models class-conditional probabilities through a logistic transformation of a linear predictor, and it has been widely surveyed as a benchmark technique for supervised classification tasks [SOURCE-1].

For multiclass problems, multinomial logistic regression extends the binary formulation by employing the softmax function to produce a normalized probability distribution over K classes [SOURCE-1].

Balanced accuracy, defined as the macro-average of per-class recall, provides a single scalar that equally weights each class regardless of its sample frequency [SOURCE-2].

Prior work has recommended balanced accuracy over raw accuracy for multiclass evaluation because raw accuracy can obscure poor performance on minority classes [SOURCE-2].

We select logistic regression as our primary classifier because prior surveys have demonstrated that linear models achieve competitive performance on low-dimensional, numerically encoded feature spaces such as botanical morphometric data [SOURCE-1].

We adopt balanced accuracy as our primary evaluation metric following established recommendations for multiclass classification, ensuring that each of the three Iris species contributes equally to the reported score [SOURCE-2].

We include a majority-class predictor as a baseline because it establishes the performance floor that any meaningful classifier must exceed [SOURCE-2].

We formulate the Iris species classification task as a multinomial logistic regression problem with three target classes corresponding to Iris setosa, Iris versicolor, and Iris virginica.

The model accepts four input features—sepal length, sepal width, petal length, and petal width—all measured in centimeters.

The model computes class probabilities using the softmax function applied to linear combinations of the four input features, producing a three-dimensional probability vector that sums to one.

Model parameters—consisting of a weight matrix and bias vector—are estimated by minimizing the multinomial cross-entropy loss over the training data.

We apply L2 regularization to the weight matrix during optimization to discourage large coefficient values and reduce the risk of overfitting.

The majority-class baseline is defined as a predictor that always outputs the most frequent class observed in the training set, ignoring all input features.

We hypothesize that logistic regression will substantially outperform the majority-class baseline on balanced accuracy, because the Iris dataset's morphometric features exhibit near-linear separability across the three species.

We hypothesize that the linear decision boundaries learned by the model will achieve balanced accuracy above 0.95 on held-out Iris test data.

We hypothesize that we anticipate that the softmax probability outputs will be well-calibrated, yielding high ROC-AUC values reflecting strong class discrimination across all pairwise species comparisons.

Our results show that logistic regression achieves a balanced accuracy of 0.973, confirming that the learned linear boundaries effectively separate the three Iris species [RESULT-1].

The majority-class baseline achieves a balanced accuracy of 0.500, providing confirmation that a trivial classifier cannot meaningfully distinguish between Iris species [RESULT-2].

The model achieves an ROC-AUC of 0.998, indicating near-perfect ranking quality in the probability estimates produced by the softmax output [RESULT-3].

The gap of 0.473 in balanced accuracy between logistic regression (0.973) and the majority-class baseline (0.500) demonstrates that the four morphometric features carry strong discriminative signal for species classification [RESULT-1] [RESULT-2].


## Evaluation Plan

We evaluate logistic regression on the Iris dataset [SOURCE-1], comprising 150 samples across three species with four continuous features.

Following established practices for multiclass evaluation [SOURCE-2], we adopt balanced accuracy as our primary evaluation metric.

We report ROC-AUC as a supplementary metric [SOURCE-2] to provide a threshold-independent view of discriminative performance.

We partition the Iris dataset into training and test subsets using a stratified hold-out split, ensuring proportional class representation in both partitions.

We fit a multinomial logistic regression model with default L2 regularization on the training set, using the softmax function to jointly model all three classes [SOURCE-1].

We implement a majority-class predictor that assigns every test sample to the most frequent class in the training set, serving as a lower-bound baseline.

Our results show that logistic regression achieves a balanced accuracy of [RESULT-1].

The majority-class baseline achieves a balanced accuracy of [RESULT-2].

The logistic regression model achieves an ROC-AUC of [RESULT-3], indicating near-perfect class-ranking capability.

We hypothesize that the substantial gap between the model's balanced accuracy and the baseline validates that learned feature coefficients provide discriminative value beyond naive class-frequency heuristics [RESULT-1] [RESULT-2].


## Discussion and Future Work

Logistic regression performs well on datasets where classes are approximately linearly separable [SOURCE-1].

Balanced accuracy is particularly informative because it accounts for potential class imbalance, ensuring that observed improvements are not inflated by majority-class dominance [SOURCE-2].

Our results show logistic regression achieves a balanced accuracy of [RESULT-1], compared to [RESULT-2] for the majority-class baseline, representing near-perfect discriminative performance on the Iris dataset.

The ROC-AUC of [RESULT-3] indicates near-perfect class separability under the linear model, consistent with the known approximate linear separability of Iris species.

The Iris dataset is a relatively simple benchmark with only four features and three well-separated classes, and the performance of logistic regression on this dataset may not generalize to more complex botanical classification tasks involving high-dimensional feature spaces, nonlinear class boundaries, or larger numbers of species.

We hypothesize that a random forest ensemble, by aggregating decision trees trained on bootstrap samples, would achieve comparable or superior classification accuracy through variance reduction, particularly on more complex datasets where individual decision boundaries are less stable.

We hypothesize that kernel-based methods or neural network architectures would yield improvements on datasets where class boundaries are nonlinear, though the magnitude of improvement may be marginal for datasets with structure similar to Iris.

We aim to extending evaluation to larger botanical datasets with higher-dimensional features and more species would provide a more rigorous assessment of logistic regression's limitations and guide the selection of appropriate models for real-world species classification tasks.

We hypothesize that interaction terms or polynomial features could improve logistic regression performance on datasets where pairwise or higher-order feature interactions carry discriminative information for species identification.

We aim to the near-ceiling performance observed on Iris suggests that future contributions in botanical classification should target more challenging datasets where model choice has a greater impact on outcomes [RESULT-1].


## Conclusion

The Iris dataset remains a foundational benchmark for evaluating multiclass classification methods, particularly for assessing the discriminative power of simple linear models [SOURCE-1] [SOURCE-2].

Our results show that logistic regression achieves a balanced accuracy of 0.973 on the Iris dataset, substantially outperforming the majority-class baseline, which achieves a balanced accuracy of 0.500 [RESULT-1] [RESULT-2].

The model additionally achieves a ROC-AUC of 0.998, indicating near-perfect class separation across the three Iris species [RESULT-3].

These findings are consistent with the expectation that the three Iris species are largely linearly separable in their feature representations, making logistic regression a strong and appropriate choice for this benchmark [SOURCE-1].

We aim to this work aims to provide a transparent, reproducible empirical baseline for logistic regression on the Iris dataset using balanced accuracy, which can serve as a reference point for future studies exploring more complex multiclass classifiers [RESULT-1] [RESULT-2] [RESULT-3].

We aim to this work aims to demonstrate that even simple, interpretable linear models remain highly competitive on well-structured, low-dimensional classification tasks, supporting their continued use alongside more complex ensemble or nonlinear approaches [SOURCE-1] [SOURCE-2] [RESULT-1].


## References

[Generated from 2 source papers — see proposal for full bibliography]
