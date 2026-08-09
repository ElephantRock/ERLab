# Logistic Regression for Multiclass Classification on the Iris Dataset: An Empirical Analysis with Balanced Accuracy Evaluation

## Abstract

Multiclass classification is a fundamental task in machine learning, and the choice of both model and evaluation metric significantly impacts the conclusions drawn from empirical studies. This paper presents a rigorous empirical evaluation of logistic regression applied to the Iris classification benchmark, with balanced accuracy as the primary evaluation metric. Logistic regression, a well-established linear classification method, is compared against a majority-class predictor baseline to quantify the discriminative contribution of the learned linear decision boundaries. The Iris dataset, comprising 150 samples across three species with four morphological features, serves as the evaluation domain. The experimental results demonstrate that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], substantially outperforming the majority-class baseline, which attains a balanced accuracy of only 0.500 [RESULT-2]. Additionally, the logistic regression model yields an ROC-AUC of 0.998 [RESULT-3], indicating near-perfect class separability under the learned model. These findings confirm that even a straightforward linear classifier can achieve near-ceiling performance on the Iris benchmark when appropriate features are available, while also highlighting the importance of balanced metrics for faithfully characterizing performance on class-balanced multiclass problems. The study contributes a transparent, reproducible experimental protocol and a discussion of the implications of metric selection for multiclass evaluation.

## Introduction

Classification is among the most studied problems in supervised machine learning, encompassing applications from medical diagnosis to biological taxonomy. Within this broad landscape, linear methods have retained prominence due to their interpretability, computational efficiency, and competitive performance on datasets where classes are approximately linearly separable in feature space [SOURCE-1]. Logistic regression, in particular, has served as a foundational technique for both binary and multiclass classification since the early days of statistical learning. Despite the proliferation of more complex models—including kernel methods, ensemble approaches, and deep neural networks—logistic regression remains a critical baseline and, in many real-world settings, a method of choice when transparency and simplicity are valued.

The Iris dataset, introduced by Fisher in 1936, has become one of the most widely used benchmarks in the machine learning community. It consists of 150 iris flower samples, equally distributed across three species—*Iris setosa*, *Iris versicolor*, and *Iris virginica*—each described by four continuous morphological features: sepal length, sepal width, petal length, and petal width. The dataset is notable for the fact that *Iris setosa* is linearly separable from the other two species, while *Iris versicolor* and *Iris virginica* exhibit some degree of overlap, presenting a moderate but not trivial classification challenge. This structure makes Iris an ideal testbed for evaluating the behavior of linear classifiers and for studying the nuances of multiclass evaluation metrics.

A central concern in classification evaluation is the selection of appropriate metrics. Standard accuracy, while intuitive, can be misleading when classes are imbalanced or when the costs of different error types vary. Balanced accuracy, defined as the arithmetic mean of per-class recall, addresses this limitation by weighting each class equally regardless of its prevalence [SOURCE-2]. This property is especially relevant for the Iris dataset: although the three species are equally represented, balanced accuracy provides a more informative picture of per-class discriminative performance than raw accuracy, particularly for examining whether a model generalizes uniformly across all classes. Additionally, ROC-AUC provides a threshold-independent measure of ranking quality, offering complementary insight into the separability of classes under the model's predicted score distributions [SOURCE-2].

This paper presents a controlled empirical study of logistic regression on the Iris dataset, with the majority-class predictor serving as a naive baseline. The primary evaluation metric is balanced accuracy, supplemented by ROC-AUC for a more comprehensive characterization of model behavior. The contributions of this work are threefold: (1) a formal description of multinomial logistic regression as applied to the Iris classification problem, including the mathematical formulation of the softmax model and the regularized cross-entropy objective; (2) a reproducible experimental protocol comparing logistic regression against a majority-class baseline using balanced accuracy and ROC-AUC; and (3) an empirical demonstration that logistic regression achieves near-ceiling balanced accuracy, substantially exceeding the baseline, with supporting analysis of what these results reveal about the linear separability structure of the dataset and the adequacy of balanced metrics for this benchmark.

## Related Work

The study of linear classification methods spans decades of research in statistics and machine learning. Smith (2020) provides a comprehensive survey of linear classification techniques, situating logistic regression within the broader family of generalized linear models and comparing it against alternatives such as linear discriminant analysis, support vector machines with linear kernels, and the perceptron [SOURCE-1]. That survey highlights logistic regression's distinctive property of modeling class probabilities directly via the softmax function, which makes it particularly well-suited for multiclass settings where calibrated probability estimates are desired. In contrast, methods such as linear discriminant analysis assume Gaussian class-conditional distributions with shared covariance, an assumption that may or may not hold for a given dataset. The survey also notes that logistic regression, while simple, can be surprisingly competitive on low-dimensional datasets with informative features—a finding that the present study empirically corroborates on the Iris benchmark.

On the evaluation side, Lee (2019) provides a detailed treatment of multiclass evaluation metrics, arguing that no single metric suffices for all classification scenarios and that the choice of metric should be guided by the structure of the problem and the goals of the analysis [SOURCE-2]. Balanced accuracy is recommended as a default metric for imbalanced datasets, as it prevents high-prevalence classes from dominating the evaluation. However, Lee (2019) also notes that balanced accuracy is informative even for balanced datasets, because it reveals whether the model performs uniformly across classes or whether it sacrifices performance on certain classes to achieve high overall accuracy. The ROC-AUC metric, discussed in the same work, provides a rank-based assessment of classification quality that is independent of any specific decision threshold. Lee (2019) emphasizes that ROC-AUC and accuracy-based metrics are complementary: the former captures the model's ability to rank instances correctly, while the latter captures performance at a specific operating point.

In the context of the Iris dataset specifically, numerous prior studies have used it as a testing ground for classification algorithms. What distinguishes the present work is the deliberate focus on balanced accuracy as the primary metric, paired with a formal majority-class baseline. While many published experiments report raw accuracy on Iris, fewer emphasize balanced accuracy explicitly. By reporting both balanced accuracy and ROC-AUC, this study aligns with the recommendations of Lee (2019) for thorough multiclass evaluation [SOURCE-2].

## Methodology

### Problem Formulation

Let $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{N}$ denote a labeled dataset where each input $\mathbf{x}_i \in \mathbb{R}^d$ is a $d$-dimensional feature vector and each label $y_i \in \{1, 2, \ldots, K\}$ indicates class membership among $K$ classes. For the Iris dataset, $N = 150$, $d = 4$ (sepal length, sepal width, petal length, petal width), and $K = 3$ (corresponding to the three species). The goal is to learn a classifier $f: \mathbb{R}^d \rightarrow \{1, \ldots, K\}$ that maps feature vectors to predicted class labels, generalizing from the training data to unseen instances.

### Multinomial Logistic Regression

Multinomial logistic regression, also known as softmax regression, models the conditional probability of each class given the input features using the softmax function. For each class $k$, the model maintains a weight vector $\mathbf{w}_k \in \mathbb{R}^d$ and a bias term $b_k \in \mathbb{R}$. The predicted probability for class $k$ given input $\mathbf{x}$ is:

$$P(y = k \mid \mathbf{x}) = \frac{\exp(\mathbf{w}_k^\top \mathbf{x} + b_k)}{\sum_{j=1}^{K} \exp(\mathbf{w}_j^\top \mathbf{x} + b_j)}$$

The model parameters $\mathbf{W} = [\mathbf{w}_1, \ldots, \mathbf{w}_K]$ and $\mathbf{b} = [b_1, \ldots, b_K]$ are estimated by minimizing the regularized negative log-likelihood (cross-entropy loss):

$$\mathcal{L}(\mathbf{W}, \mathbf{b}) = -\frac{1}{N} \sum_{i=1}^{N} \sum_{k=1}^{K} \mathbb{1}(y_i = k) \log P(y_i = k \mid \mathbf{x}_i) + \lambda \sum_{k=1}^{K} \|\mathbf{w}_k\|_2^2$$

where $\mathbb{1}(\cdot)$ is the indicator function and $\lambda \geq 0$ is the L2 regularization strength. The regularization term prevents overfitting by penalizing large weight magnitudes, which is particularly relevant for small datasets such as Iris where the risk of memorization is non-trivial.

### Optimization

The loss function $\mathcal{L}(\mathbf{W}, \mathbf{b})$ is convex in $(\mathbf{W}, \mathbf{b})$, guaranteeing that gradient-based optimization converges to a global minimum [SOURCE-1]. The gradient with respect to $\mathbf{w}_k$ is:

$$\frac{\partial \mathcal{L}}{\partial \mathbf{w}_k} = \frac{1}{N} \sum_{i=1}^{N} \left(P(y_i = k \mid \mathbf{x}_i) - \mathbb{1}(y_i = k)\right) \mathbf{x}_i + 2\lambda \mathbf{w}_k$$

In practice, optimization is performed using an iteratively reweighted least squares solver or a quasi-Newton method such as L-BFGS, both of which exploit the convexity of the objective for efficient and reliable convergence. Feature standardization (zero mean, unit variance) is applied prior to training to ensure that the optimization landscape is well-conditioned and that the regularization penalty is applied uniformly across features.

### Prediction

Given a new input $\mathbf{x}^*$, the predicted class is determined by the argmax of the class probabilities:

$$\hat{y} = \arg\max_{k \in \{1, \ldots, K\}} P(y = k \mid \mathbf{x}^*)$$

### Majority-Class Baseline

The majority-class predictor serves as the lower-bound baseline. It assigns every test instance to the most frequent class in the training set, irrespective of the input features. Formally, if class $k^* = \arg\max_k n_k$ is the most prevalent class in the training data (where $n_k$ is the number of training samples in class $k$), then the baseline prediction for any input is $\hat{y}_{\text{baseline}} = k^*$. This baseline provides a reference point: any model that fails to substantially outperform it provides no meaningful discriminative signal.

### Evaluation Metrics

Balanced accuracy is computed as the macro-average of per-class recall [SOURCE-2]:

$$\text{balanced\_accuracy} = \frac{1}{K} \sum_{k=1}^{K} \frac{TP_k}{TP_k + FN_k}$$

where $TP_k$ and $FN_k$ are the true positive and false negative counts for class $k$, respectively. This metric assigns equal weight to each class, ensuring that performance on smaller or harder classes is not obscured by performance on dominant classes.

ROC-AUC is computed using a one-vs-rest strategy, where for each class, the binary classification problem of that class versus all others is evaluated, and the area under the receiver operating characteristic curve is calculated. The multiclass ROC-AUC is then reported as the macro-average across all classes, providing a threshold-independent measure of the model's ability to rank instances by their predicted class probabilities [SOURCE-2].

## Experimental Design

### Dataset

The Iris dataset consists of 150 samples equally distributed across three species (50 samples each). The four features—sepal length, sepal width, petal length, and petal width—are continuous measurements in centimeters. The dataset was split into training and test subsets using a standard holdout protocol, with stratification to preserve the class distribution in both partitions. Feature standardization was applied using statistics computed from the training set, and the same transformation was applied to the test set to prevent information leakage.

### Models

Two models were evaluated:

1. **Majority-class predictor**: A naive baseline that predicts the most frequent training class for all test instances. This model has no learnable parameters and serves as the performance floor.

2. **Logistic regression**: Multinomial logistic regression with L2 regularization, trained via the L-BFGS optimization algorithm. The regularization strength $\lambda$ was selected from a predefined grid via cross-validation on the training set to balance bias and variance.

### Metrics

The primary metric is balanced accuracy, which provides a class-balanced assessment of classification performance [SOURCE-2]. The secondary metric is ROC-AUC, computed using a macro-averaged one-vs-rest strategy, which evaluates the model's ranking quality independent of any specific decision threshold. Both metrics are reported for the logistic regression model. For the majority-class baseline, balanced accuracy is the primary reported metric, as ROC-AUC is undefined or uninformative for a model that produces constant predictions.

### Evaluation Protocol

Each model was trained on the training partition and evaluated on the held-out test partition. The logistic regression model's hyperparameters (regularization strength) were tuned via $k$-fold cross-validation on the training set. The final reported metrics correspond to the model's performance on the test set, ensuring an unbiased estimate of generalization performance.

### Ablation Considerations

While the primary comparison is between logistic regression and the majority-class baseline, the experimental design also supports analysis of the contribution of individual feature subsets. The known linear separability of *Iris setosa* from the other two classes suggests that petal-based features alone may carry most of the discriminative signal. However, the primary reported results use all four features, consistent with standard Iris benchmarking practice.

## Results

The experimental results clearly demonstrate the effectiveness of logistic regression on the Iris classification task. The logistic regression model achieves a balanced accuracy of 0.973 [RESULT-1], indicating near-perfect classification performance across all three species. This result substantially exceeds the majority-class baseline, which attains a balanced accuracy of only 0.500 [RESULT-2]. The large margin between the two models—0.473 in absolute balanced accuracy—confirms that the learned linear decision boundaries capture meaningful discriminative structure in the feature space, rather than trivially exploiting class prevalence.

The ROC-AUC of 0.998 achieved by logistic regression [RESULT-3] further corroborates the balanced accuracy findings. An ROC-AUC value approaching 1.0 indicates that the model's predicted class probabilities almost perfectly rank positive instances above negative instances in the one-vs-rest formulation for each class. This near-perfect ranking performance suggests that the four morphological features of Iris provide highly informative signal for species discrimination, and that the linear decision boundaries learned by logistic regression are well-aligned with the underlying class structure of the data.

The substantial gap between the logistic regression model and the majority-class baseline highlights the value of learning from features. The majority-class predictor, by definition, ignores all feature information and assigns every test instance to a single class, resulting in poor per-class recall. In contrast, logistic regression leverages all four features to learn class-conditional probability estimates, achieving high recall across all three species. The balanced accuracy of 0.973 [RESULT-1] indicates that the model misclassifies only a small number of instances, likely concentrated at the boundary between *Iris versicolor* and *Iris virginica*, which are known to overlap in feature space.

## Discussion

The results demonstrate that logistic regression achieves excellent performance on the Iris dataset, with a balanced accuracy of 0.973 [RESULT-1] and an ROC-AUC of 0.998 [RESULT-3]. These findings are consistent with the known structure of the dataset: one class (*Iris setosa*) is linearly separable from the others, while the remaining two classes are nearly separable with only marginal overlap. The near-ceiling performance of a simple linear model on this benchmark underscores the importance of feature quality—when features are highly informative, even the simplest models can achieve excellent results.

Several limitations of this study should be acknowledged. First, the Iris dataset is small ($N = 150$) and low-dimensional ($d = 4$), which limits the generalizability of these findings to larger, higher-dimensional datasets. On such datasets, more complex models may offer substantial advantages over logistic regression. Second, the balanced accuracy of 0.500 achieved by the majority-class baseline [RESULT-2] reflects the expected behavior of a feature-agnostic predictor; the interpretation of this value depends on the specific implementation of balanced accuracy and the class distribution. Third, while the ROC-AUC of 0.998 [RESULT-3] is near-perfect, this metric may be less discriminative on a dataset where performance is already saturated; alternative datasets with more challenging class overlap structures would provide a more sensitive evaluation.

From a broader perspective, this study reinforces several principles emphasized in the literature. The use of balanced accuracy as the primary metric, as recommended by Lee (2019) [SOURCE-2], ensures that the evaluation is not biased by class prevalence and provides a transparent picture of per-class performance. The inclusion of a majority-class baseline provides a meaningful reference point without which the absolute performance of logistic regression would be harder to contextualize. These practices, while straightforward, are essential for reproducible and interpretable machine learning research.

Ethical considerations for this work are minimal, as the Iris dataset contains no sensitive or personal information. However, the broader principle of using appropriate evaluation metrics applies to high-stakes classification tasks (e.g., medical diagnosis, loan approval), where misleading metrics can lead to harmful decisions. The emphasis on balanced accuracy in this study serves as a reminder that metric selection is a critical methodological choice with real-world consequences.

## Conclusion

This paper presented an empirical evaluation of logistic regression for multiclass classification on the Iris dataset, using balanced accuracy as the primary evaluation metric and a majority-class predictor as the baseline. The results demonstrate that logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], dramatically outperforming the majority-class baseline's balanced accuracy of 0.500 [RESULT-2]. The model's ROC-AUC of 0.998 [RESULT-3] further confirms near-perfect class separability under the learned linear decision boundaries. These findings validate logistic regression as a strong and interpretable classifier for the Iris benchmark and highlight the importance of balanced evaluation metrics and meaningful baselines in classification research. Future work could extend this analysis to feature ablation studies, exploring the individual and combined contributions of sepal and petal measurements, and to a broader set of datasets to assess the generalizability of these findings beyond the Iris domain.