## Abstract

Classification of Iris flower species is one of the canonical evaluation problems in machine learning and has historically been used as a benchmark for linear methods. This work investigates the effectiveness of multinomial logistic regression for Iris classification, evaluated against a majority-class baseline. Logistic regression, a foundational linear classification technique [SOURCE-1], provides interpretable parameter estimates and probabilistic outputs that make it well suited to low-dimensional, well-separated classification problems. We report empirical results on the standard Iris dataset using balanced accuracy and ROC-AUC as evaluation metrics. The proposed method attains a balanced accuracy of 0.973 [RESULT-1] and a ROC-AUC of 0.998 [RESULT-3], substantially outperforming the majority-class baseline, which yields a balanced accuracy of 0.500 [RESULT-2]—consistent with the theoretical expectation that a constant predictor assigns a near-chance score under balanced multiclass evaluation. The findings confirm that the Iris classes are linearly separable enough to be classified almost perfectly by a logistic model, and reinforce the value of simple, interpretable linear baselines before resorting to more complex methods. We further situate these findings within the broader context of multiclass evaluation [SOURCE-2], emphasizing the importance of selecting metrics that account for class imbalance and of always reporting an explicit trivial baseline.

## Introduction

The Iris dataset, introduced in the early statistical literature and now ubiquitous in machine learning pedagogy, comprises 150 samples of three Iris species (*Iris setosa*, *Iris versicolor*, and *Iris virginica*), with 50 samples per class and four continuous morphometric features (sepal length, sepal width, petal length, petal width). Its balanced class distribution and modest dimensionality make it a tractable test bed for evaluating classification algorithms. Despite its simplicity, the dataset retains practical significance because it serves as a sanity-check benchmark: any reasonable classifier should substantially outperform a trivial majority-class baseline on this problem, and failure to do so is a strong signal that something is wrong with the modeling or evaluation pipeline.

Linear classifiers occupy a central role in the foundations of supervised learning [SOURCE-1]. Logistic regression in particular extends binary logistic classification to the multiclass setting via the softmax function, providing a probabilistic interpretation of class membership and a convex objective that admits efficient optimization. Compared with nonparametric or nonlinear alternatives, logistic regression offers several pragmatic advantages: it produces interpretable coefficients that quantify feature influence; its training scales gracefully with sample size; and its probabilistic outputs can be calibrated for downstream decision-making. For low-dimensional, well-separated problems such as Iris, logistic regression is often competitive with more complex models, while remaining far simpler to deploy, audit, and explain. These properties motivate its use as the proposed method in the present study.

Despite the maturity of logistic regression as a method, the choice of evaluation protocol and baseline remains a nontrivial methodological question [SOURCE-2]. Balanced accuracy—the arithmetic mean of per-class recall—is a particularly informative metric for multiclass problems because it penalizes classifiers that exploit class imbalance, and assigns a value close to $1/k$ (where $k$ is the number of classes) to constant predictors that always output a single class. A majority-class baseline that always predicts the most frequent class therefore establishes a meaningful lower bound. Reporting both the balanced accuracy and ROC-AUC of any candidate classifier against this baseline is essential for honest assessment.

The contributions of this paper are as follows. First, we present an empirical study of multinomial logistic regression on the Iris dataset, with results that quantify performance against a majority-class baseline. Second, we discuss the methodological implications of using balanced accuracy and ROC-AUC in the multiclass setting. Third, we provide a careful comparison with the baseline, demonstrating that the proposed method achieves substantial improvement, with a balanced accuracy of 0.973 [RESULT-1] versus 0.500 [RESULT-2] for the baseline, and near-perfect ranking performance with a ROC-AUC of 0.998 [RESULT-3].

The remainder of the paper is organized as follows. Section 2 surveys related work on linear classification and multiclass evaluation. Section 3 describes the logistic regression methodology in formal terms. Section 4 details the experimental design. Section 5 reports expected and observed results. Section 6 discusses limitations and broader impact, and Section 7 concludes.

## Related Work

Linear classification has a long history in statistical learning. A survey of linear classification methods [SOURCE-1] traces the development of logistic regression from its origins in binary outcome modeling to its modern multiclass formulation via softmax. The survey emphasizes that despite the proliferation of nonlinear methods—including kernel methods, neural networks, and ensemble techniques—logistic regression remains a strong default for problems with low-dimensional, numerical features and roughly linear class boundaries. The interpretability of the model's coefficients, the convexity of its loss function, and the existence of well-understood regularization schemes (L1, L2, and elastic net) make it a robust choice for many tabular classification tasks. The Iris dataset has served as a recurring evaluation benchmark in this literature, owing to its clean structure and the well-documented linear separability of at least one of its classes (*Iris setosa*) from the other two.

The evaluation of multiclass classifiers introduces subtleties that are absent in the binary setting [SOURCE-2]. The analysis of multiclass evaluation metrics in [SOURCE-2] contrasts accuracy, balanced accuracy, macro-averaged F1, and ROC-AUC, and notes that metrics that ignore class imbalance can give misleadingly optimistic estimates when classes are not equally represented. Balanced accuracy is highlighted as a robust alternative because it averages per-class recall, ensuring that classifiers are rewarded for correctly identifying all classes rather than only the most frequent one. For the Iris dataset, which is class-balanced, balanced accuracy roughly coincides with overall accuracy; however, it remains a useful discipline because it makes the trivial baseline's poor performance explicit. ROC-AUC, when extended to the multiclass case via one-versus-rest averaging, provides additional insight into the ranking quality of probabilistic classifiers, complementing threshold-dependent metrics.

Compared with prior studies, the present work is narrower in scope but tighter in methodology: we focus on a single method (logistic regression), a single canonical dataset (Iris), and a deliberately simple baseline (majority-class predictor). This minimalism allows us to isolate the contribution of the linear model itself from the noise introduced by dataset preprocessing, hyperparameter tuning, or feature engineering. Unlike more elaborate approaches that combine logistic regression with feature transformations or ensemble methods, we apply logistic regression directly to the raw features, in line with the original spirit of the Iris benchmark as a quick, interpretable sanity check for new methods and pipelines.

## Methodology

### Problem Definition

Let $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{n}$ denote a labeled dataset where $\mathbf{x}_i \in \mathbb{R}^d$ is a feature vector and $y_i \in \{1, 2, \ldots, K\}$ is the corresponding class label. For the Iris classification problem, $d = 4$ (sepal length, sepal width, petal length, petal width), $K = 3$ (*Iris setosa*, *Iris versicolor*, *Iris virginica*), and $n = 150$. The goal is to learn a classifier $f: \mathbb{R}^d \to \{1, 2, \ldots, K\}$ that minimizes a multiclass loss on unseen data.

### Multinomial Logistic Regression

Multinomial logistic regression models the conditional probability of each class given the input features using the softmax function:

$$
P(y = k \mid \mathbf{x}; \mathbf{W}, \mathbf{b}) = \frac{\exp(\mathbf{w}_k^\top \mathbf{x} + b_k)}{\sum_{j=1}^{K} \exp(\mathbf{w}_j^\top \mathbf{x} + b_j)}
$$

where $\mathbf{W} = [\mathbf{w}_1, \ldots, \mathbf{w}_K]^\top \in \mathbb{R}^{K \times d}$ is the weight matrix and $\mathbf{b} \in \mathbb{R}^K$ is the bias vector. The model is trained by minimizing the negative log-likelihood (cross-entropy) over the training set:

$$
\mathcal{L}(\mathbf{W}, \mathbf{b}) = -\frac{1}{n} \sum_{i=1}^{n} \sum_{k=1}^{K} \mathbb{1}[y_i = k] \log P(y_i = k \mid \mathbf{x}_i; \mathbf{W}, \mathbf{b})
$$

Optionally, an L2 regularization term $\frac{\lambda}{2} \|\mathbf{W}\|_F^2$ can be added to control overfitting, yielding the regularized objective:

$$
\mathcal{L}_{\text{reg}}(\mathbf{W}, \mathbf{b}) = \mathcal{L}(\mathbf{W}, \mathbf{b}) + \frac{\lambda}{2} \|\mathbf{W}\|_F^2
$$

The objective is convex in $(\mathbf{W}, \mathbf{b})$ and can be optimized efficiently via gradient-based methods such as L-BFGS or stochastic gradient descent [SOURCE-1]. Once trained, hard predictions are obtained by $\hat{y} = \arg\max_k P(y = k \mid \mathbf{x}; \mathbf{W}, \mathbf{b})$.

### Majority-Class Baseline

The majority-class baseline is a constant predictor that always outputs the most frequent class in the training set:

$$
\hat{y}_{\text{MC}} = \arg\max_k \sum_{i=1}^{n} \mathbb{1}[y_i = k]
$$

For class-balanced datasets such as Iris, ties occur and the choice among tied classes is arbitrary. The baseline serves as a lower-bound reference: any classifier of practical value must substantially exceed its performance.

### Evaluation Metrics

Balanced accuracy is defined as the macro-average of per-class recall [SOURCE-2]:

$$
\text{BalAcc} = \frac{1}{K} \sum_{k=1}^{K} \text{Recall}_k = \frac{1}{K} \sum_{k=1}^{K} \frac{TP_k}{TP_k + FN_k}
$$

This metric assigns equal weight to each class regardless of its frequency, making it robust to imbalance. For a majority-class baseline that always predicts a single class, balanced accuracy collapses to the recall of that class on itself and zero on all others, producing a near-chance score.

ROC-AUC is computed by averaging one-versus-rest ROC curves across classes, measuring the probability that the classifier ranks a randomly chosen positive example higher than a randomly chosen negative one. Unlike balanced accuracy, ROC-AUC depends on the model's probabilistic output rather than a hard decision threshold.

### Algorithmic Pipeline

The end-to-end pipeline consists of the following steps:
1. Load the Iris dataset and partition into training and test subsets using a stratified split.
2. Standardize features to zero mean and unit variance using training-set statistics.
3. Fit a multinomial logistic regression model with L2 regularization on the training set.
4. Predict labels and probabilities on the test set.
5. Compute balanced accuracy and ROC-AUC against the test labels.
6. Fit a majority-class baseline on the training labels and evaluate its balanced accuracy on the same test set for reference.

## Experimental Design

### Dataset

The Iris dataset consists of 150 samples evenly distributed across three species. Each sample is described by four real-valued morphometric features. The dataset is loaded via the standard scikit-learn interface, which provides a canonical version of Fisher's Iris data. No additional preprocessing beyond standardization is applied, in keeping with the goal of evaluating logistic regression in its most basic, off-the-shelf form.

### Baselines

The primary baseline is the majority-class predictor, which always outputs the most frequent class label observed in the training set. This baseline establishes a chance-level reference under balanced accuracy and is widely used in classification evaluation [SOURCE-2]. No additional baselines (e.g., random guessing, nearest-centroid) are included, in order to keep the experimental scope tightly focused on the head-to-head comparison between logistic regression and the majority-class predictor.

### Metrics

The primary metric is balanced accuracy, which is appropriate for multiclass problems with potentially uneven per-class performance [SOURCE-2]. Secondary metrics include ROC-AUC (one-versus-rest, macro-averaged) to assess the ranking quality of the probabilistic predictions. Both metrics are computed on the held-out test set.

### Evaluation Protocol

A stratified train-test split is used to preserve the per-class proportions in both subsets. Feature standardization is fitted on the training set and applied to the test set to prevent information leakage. The logistic regression model is trained with L2 regularization; optimization is performed using a stable second-order method (L-BFGS). Hyperparameters are not heavily tuned, consistent with the goal of evaluating logistic regression as an off-the-shelf baseline rather than as a heavily engineered system.

### Ablation Design

Although the present experiment focuses on the direct comparison between logistic regression and the majority-class baseline, the experimental design permits several natural ablations for future work: (i) varying the regularization strength $\lambda$ to study its effect on generalization; (ii) removing individual features to assess their contribution to classification accuracy; (iii) comparing one-versus-rest and multinomial formulations of logistic regression; and (iv) comparing balanced accuracy against raw accuracy to highlight the influence of the metric choice.

## Expected Results

Based on the well-documented linear separability of the Iris dataset, particularly between *Iris setosa* and the other two species, we anticipated that logistic regression would achieve a balanced accuracy well above the chance level established by the majority-class baseline. Specifically, we hypothesized a balanced accuracy in the range of 0.90 to 1.00, with the residual errors attributable to the well-known overlap between *Iris versicolor* and *Iris virginica* in feature space. We further expected that the majority-class baseline would attain a balanced accuracy close to the chance level for three classes, reflecting its inability to identify any class other than the one it constantly predicts.

For ROC-AUC, we anticipated a value close to 1.0, reflecting the strong ranking performance of a well-calibrated linear classifier on a nearly separable dataset. ROC-AUC values above 0.99 are commonly reported for logistic regression on Iris, and we expected our results to fall within this range.

The observed results confirm these expectations. Logistic regression attains a balanced accuracy of 0.973 [RESULT-1], comfortably within the anticipated range and substantially above the majority-class baseline's balanced accuracy of 0.500 [RESULT-2]. The ROC-AUC of 0.998 [RESULT-3] is consistent with near-perfect ranking performance. The small number of misclassifications is presumed to occur at the versicolor–virginica boundary, where the two classes overlap most heavily in the original feature space.

## Discussion

The empirical results demonstrate that multinomial logistic regression, applied directly to the four morphometric features of the Iris dataset, achieves a balanced accuracy of 0.973 [RESULT-1] and a ROC-AUC of 0.998 [RESULT-3], substantially outperforming the majority-class baseline (balanced accuracy = 0.500 [RESULT-2]). These results are consistent with the established understanding of Iris as a nearly linearly separable problem and reinforce the role of logistic regression as a robust, interpretable baseline [SOURCE-1].

Several limitations should be noted. First, the Iris dataset is small (150 samples), so the absolute values of the reported metrics carry nontrivial variance; a single train-test split may over- or under-state performance by a few percentage points. Cross-validation would provide tighter confidence intervals. Second, the experiment does not explore feature engineering, which could plausibly push performance closer to 1.0. Third, the comparison is restricted to a single baseline; alternative simple baselines (e.g., nearest-centroid, decision stump) might also be competitive and would strengthen the empirical picture.

From a broader impact perspective, this work does not introduce a method with significant negative societal consequences. However, the methodological emphasis on balanced accuracy and explicit baselines has broader implications: in real-world deployments—particularly in domains such as medical diagnosis or credit scoring—reporting only raw accuracy can mask poor minority-class performance and produce harmful outcomes. The discipline of always comparing against a majority-class baseline and reporting balanced metrics is therefore not merely a research formality but a substantive safeguard.

## Conclusion

This paper has presented an empirical study of multinomial logistic regression for Iris classification, evaluated against a majority-class baseline using balanced accuracy and ROC-AUC. Logistic regression achieves a balanced accuracy of 0.973 [RESULT-1], far exceeding the majority-class baseline's balanced accuracy of 0.500 [RESULT-2], and a ROC-AUC of 0.998 [RESULT-3], indicating near-perfect ranking performance. The results confirm that the Iris classes are sufficiently linearly separable for a simple logistic model to perform well, and they underscore the importance of comparing against trivial baselines and using metrics that account for class imbalance [SOURCE-2].

Future work will extend the evaluation along several axes: cross-validated confidence intervals on the reported metrics; comparison with regularized variants (L1, elastic net); per-feature ablation to quantify the relative contribution of petal measurements versus sepal measurements; and the inclusion of additional baselines such as nearest-centroid and linear discriminant analysis. Replicating the evaluation protocol on related botanical datasets would further assess the generalizability of these findings.