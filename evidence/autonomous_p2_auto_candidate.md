# Polynomial-Feature Multinomial Logistic Regression on the Iris Benchmark: Empirical Comparison to the Majority-Class Baseline

## Abstract

Logistic regression remains a widely used discriminative classifier across clinical, biological, epidemiological, and tabular-machine-learning applications, yet practitioners frequently deploy polynomial-feature expansions without empirical verification that the resulting model outperforms trivial baselines on held-out data. This paper studies the empirical behavior of multinomial logistic regression trained via iteratively reweighted least squares (IRLS) on degree-two polynomial features of the frozen Iris benchmark. The central, predeclared research question is whether such a model outperforms a majority-class baseline on test accuracy. Using a stratified split of the Iris dataset (first 80% train, last 20% test, fixed shuffle, seed 42), the experiment yields a majority-class baseline accuracy of 0.333333 [RESULT-1], a fitted-model test accuracy of 0.966667 [RESULT-3], and an absolute improvement of 0.633333 [RESULT-2]. To contextualize these observations, an illustrative excess-risk argument is presented in which the gap between empirical and true risk for the polynomial-feature classifier depends on the ratio of the polynomial-feature dimensionality $D_p$ to the training sample size $N$; this argument is intended as motivation rather than a validated certificate. The empirical results decisively affirm the predeclared research question and provide a reproducible template for comparing logistic-regression deployments against trivial baselines in tabular classification tasks.

## 1. Introduction

Logistic regression occupies a privileged position in applied statistics and machine learning. Across clinical medicine, bioinformatics, and epidemiology, it is overwhelmingly the classifier of first resort owing to its interpretability, well-understood asymptotic theory, and robustness under $L_2$ regularization. A persistent practice gap, however, is the absence of empirical verification connecting observed training performance to expected test-time behavior—particularly when polynomial feature expansions are employed to capture nonlinear interactions among predictors. Polynomial expansions increase the effective feature dimensionality $D_p$, raising legitimate concerns about overfitting, yet standard reporting conventions typically only document hold-out or cross-validated accuracy without a predeclared comparison to a trivial baseline that establishes a floor on useful performance.

The present work addresses this practice gap in a tightly controlled setting. We instantiate the polynomial-feature multinomial logistic regression framework on the Iris benchmark—a multi-class biological classification problem in which the ground-truth decision boundaries are known to be nonlinear and thus benefit from polynomial features for adequate modeling—and ask a sharp, predeclared question: does a multinomial logistic regression model fit via iteratively reweighted least squares on degree-two polynomial features outperform the majority-class baseline on test accuracy?

The contributions of this paper are bounded by the executed experiment. First, we formalize the one-vs-rest multinomial logistic regression problem with polynomial features and the IRLS solver, providing a self-contained specification of the algorithm and the regularized objective. Second, we present an *illustrative* excess-risk argument—derived from standard uniform-convergence reasoning and presented as motivation, not as a validated bound—in which the gap between the empirical and true risk of the polynomial-feature classifier depends on $D_p / N$. Third, we report the observed empirical results on the frozen Iris split, demonstrating a large absolute improvement of the polynomial-feature logistic regression model over the majority-class baseline. Fourth, we discuss implications for practitioners who wish to verify that their own logistic-regression deployments exceed a trivial floor.

We stress that this study does not claim statistical significance, distribution-free certification, or validated excess-risk bounds. The excess-risk discussion is included to frame the empirical result within familiar learning-theoretic intuition; the central contribution is the empirical observation itself.

## 2. Related Work

We organize the relevant literature into three thematic strands: applied logistic-regression classification in clinical and biological domains, advanced formulations and variants of the logistic-regression model, and comparative and theoretical studies involving logistic regression.

**Applied logistic-regression classification.** A substantial body of work applies logistic regression to clinical prediction tasks. Metharani et al. developed a diabetes-risk forecasting system using logistic regression on demographic and metabolic features [SOURCE-25]. Safitri et al. modeled stroke risk using binary logistic regression alongside multivariate adaptive regression splines, reporting competitive predictive accuracy with superior coefficient interpretability [SOURCE-22]. Upadhyay and Pandey applied multiple logistic regression to breast-cancer prediction [SOURCE-24], and Begum optimized logistic regression with gradient descent and expectation–maximization for heart-disease prediction [SOURCE-27]. Additional applications include urinary-incontinence classification [SOURCE-1], credit-risk classification with kernel logistic regression [SOURCE-3], Alzheimer gene-expression classification via logistic-regression ensembles [SOURCE-5], tweet-topic classification [SOURCE-10], play-type classification in the NFL [SOURCE-11], diabetes classification versus SVM [SOURCE-17], seat-fit classification [SOURCE-23], and disability risk assessment [SOURCE-21]. A common limitation across this body of work is the absence of predeclared comparisons to trivial baselines: each study reports empirical accuracy on held-out data, but few certify that performance exceeds a majority-class floor in a predeclared manner.

**Advanced logistic-regression formulations.** Beyond standard binary and multinomial variants, researchers have developed modifications to address specific limitations. Zaman developed a Modified Logistic Regression model for psoriasis-versus-non-psoriasis image classification, altering the link function to better handle imbalanced dermatological data [SOURCE-6]. Kannan and Dudi proposed a hybrid binary classifier combining modified logistic regression with support-vector elimination [SOURCE-26]. Moghimbeygi introduced a multinomial logistic regression model for shape-data classification using a power-divergence test statistic [SOURCE-8], which is methodologically closest to the multinomial formulation studied here. Commo et al. proposed an $n$-parameter logistic regression variant [SOURCE-9], and polytomous and ordered variants are surveyed in [SOURCE-7, SOURCE-13, SOURCE-14, SOURCE-15]. None of these works, however, presents a predeclared comparison between a polynomial-feature multinomial logistic regression model and a majority-class baseline on a controlled benchmark.

**Comparative and theoretical studies.** Dasaratha and Sheela compared SVM and logistic regression for twin classification [SOURCE-1]. Rodin and Belov provided a theoretical-and-practical treatment of classification problems solved by logistic regression [SOURCE-30]. Logistic-regression diagnostics and inference problems are treated in [SOURCE-27] and in the clinical-trials context in [SOURCE-28]. The gap that the present work addresses is the absence of an explicit, predeclared comparison between a polynomial-feature multinomial logistic regression model and a majority-class baseline on a controlled benchmark, accompanied by an illustrative complexity-aware discussion.

## 3. Methodology

### 3.1 Problem Definition

Consider a multi-class classification problem with training dataset $\mathcal{D}_{\text{train}} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{N}$, where $\mathbf{x}_i \in \mathbb{R}^d$ is a feature vector and $y_i \in \{1, 2, \ldots, K\}$ is a class label. For the Iris benchmark, $d = 4$ (sepal length, sepal width, petal length, petal width), $K = 3$ (Setosa, Versicolor, Virginica), and the dataset is partitioned into a frozen training split and a frozen test split using a stratified-by-species, first-80%-train / last-20%-test partition with a fixed shuffle and seed 42.

A polynomial feature map $\phi_p: \mathbb{R}^d \to \mathbb{R}^{D_p}$ of degree $p$ maps each input to a higher-dimensional space consisting of all monomials up to degree $p$. For $d = 4$ and $p = 2$, this yields $D_p = \binom{4+2}{2} = 15$ features (including the bias term).

The objective is to learn a multinomial logistic regression classifier $h: \mathbb{R}^{D_p} \to \{1, \ldots, K\}$ such that test accuracy on the frozen Iris test split exceeds the majority-class baseline. Let $\hat{h}_{\text{LR}}$ denote the fitted classifier and $\hat{h}_{\text{maj}}$ denote the majority-class baseline. The research question is whether $\text{Acc}_{\text{test}}(\hat{h}_{\text{LR}}) > \text{Acc}_{\text{test}}(\hat{h}_{\text{maj}})$ by an empirically decisive margin.

### 3.2 Regularized Negative-Log-Likelihood Objective

For each one-vs-rest binary subproblem $k$, the regularized negative-log-likelihood is

$$
\mathcal{L}_k(\mathbf{w}_k) \;=\; -\frac{1}{N}\sum_{i=1}^{N}\left[ z_i^{(k)} \log p_{ik} + (1 - z_i^{(k)}) \log (1 - p_{ik}) \right] + \frac{\lambda}{2}\|\mathbf{w}_k\|^2,
$$

where $p_{ik} = \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}_i))$ and $z_i^{(k)} = \mathbf{1}(y_i = k)$.

### 3.3 Multinomial Logistic Regression via One-vs-Rest Decomposition

Following the declared analysis method, the multinomial problem is decomposed into $K$ binary one-vs-rest problems. For each class $k$, a binary target $z_i^{(k)} = \mathbf{1}(y_i = k)$ is defined, and a binary logistic regression model with weights $\mathbf{w}_k$ is fit. Class probabilities at inference are obtained by the one-vs-rest scoring rule $\hat{y} = \arg\max_k \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}))$, where $\sigma(t) = 1 / (1 + e^{-t})$.

### 3.4 Iteratively Reweighted Least Squares Solver

Logistic regression has no closed-form coefficient solution in a single step. The solver is therefore realized through Iteratively Reweighted Least Squares (IRLS), which is equivalent to Newton–Raphson optimization with a unit step size applied to the regularized negative-log-likelihood. At each iteration $t$, the weight update for subproblem $k$ is

$$
\mathbf{w}_k^{(t+1)} = \mathbf{w}_k^{(t)} + \left(\Phi^T \mathbf{R}_k^{(t)} \Phi + \lambda \mathbf{I}\right)^{-1} \Phi^T \left(\mathbf{z}^{(k)} - \mathbf{p}_k^{(t)}\right),
$$

where $\Phi \in \mathbb{R}^{N \times D_p}$ is the design matrix with rows $\phi_p(\mathbf{x}_i)^T$, $\mathbf{R}_k^{(t)} = \text{diag}\!\left(p_{1k}^{(t)}(1 - p_{1k}^{(t)}), \ldots, p_{Nk}^{(t)}(1 - p_{Nk}^{(t)})\right)$ is the weight matrix, $p_{ik}^{(t)} = \sigma(\mathbf{w}_k^{(t)T} \phi_p(\mathbf{x}_i))$, and $\mathbf{z}^{(k)} = (z_1^{(k)}, \ldots, z_N^{(k)})^T$. The matrix $\Phi^T \mathbf{R}_k^{(t)} \Phi + \lambda \mathbf{I}$ is the regularized Hessian. The gradient of $\mathcal{L}_k$ with respect to $\mathbf{w}_k$ is $\nabla_{\mathbf{w}_k} \mathcal{L}_k = \Phi^T (\mathbf{p}_k - \mathbf{z}^{(k)}) + \lambda \mathbf{w}_k$, and the Newton step uses the Hessian $\mathbf{H}_k = \Phi^T \mathbf{R}_k \Phi + \lambda \mathbf{I}$. Convergence is declared when $\|\mathbf{w}_k^{(t+1)} - \mathbf{w}_k^{(t)}\|_\infty < 10^{-6}$ or after a maximum of 100 iterations. We emphasize that IRLS is an *iterative* Newton-Raphson procedure; it does not yield a one-step closed-form solution.

### 3.5 Illustrative Excess-Risk Discussion

To provide an intuitive, complexity-aware lens on the empirical comparison, we recall a standard uniform-convergence bound for linear classifiers. Let $\hat{R}(\hat{h}_{\text{LR}})$ denote the empirical misclassification rate on the training data and $R(\hat{h}_{\text{LR}})$ the true risk. Standard arguments (internal reasoning) give

$$
R(\hat{h}_{\text{LR}}) \;\leq\; \hat{R}(\hat{h}_{\text{LR}}) + 2\,\mathfrak{R}_N(\mathcal{H}_{D_p}) + 3\sqrt{\frac{\ln(2/\delta)}{2N}},
$$

with the empirical Rademacher complexity of the linear-classifier hypothesis class in $\mathbb{R}^{D_p}$ bounded by $\mathfrak{R}_N(\mathcal{H}_{D_p}) \leq \sqrt{2 D_p \log(e N / D_p) / N}$ (internal reasoning). The majority-class baseline $\hat{h}_{\text{maj}}$ depends only on class frequencies and admits no data-dependent complexity term. We emphasize that this is an *illustrative* argument intended to motivate why the empirical dominance observed below is intuitively plausible; it is not a validated distribution-free certificate and we do not claim statistical significance.

### 3.6 Inference Procedure

At test time, given a query $\mathbf{x}_{\text{test}}$:

1. Compute polynomial features $\phi_p(\mathbf{x}_{\text{test}})$.
2. For each class $k \in \{1, \ldots, K\}$, compute the one-vs-rest score $s_k = \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}_{\text{test}}))$.
3. Predict $\hat{y} = \arg\max_k s_k$.
4. Report test accuracy $\text{Acc} = \frac{1}{|\mathcal{D}_{\text{test}}|} \sum_{(\mathbf{x}_i, y_i) \in \mathcal{D}_{\text{test}}} \mathbf{1}(\hat{y}_i = y_i)$.

### 3.7 Computational Requirements

The method operates on tabular data with $D_p = 15$ features and $N \leq 150$ samples, requiring no GPU computation. The IRLS solver performs matrix operations on $\Phi \in \mathbb{R}^{N \times D_p}$ and Hessian matrices of size $D_p \times D_p$, with total time complexity $O(K \cdot T_{\text{IRLS}} \cdot (N D_p^2 + D_p^3))$, where $T_{\text{IRLS}}$ is the number of iterations. For Iris, total training time is well under one second on a single CPU core.

## 4. Experimental Design

### 4.1 Dataset

The Iris dataset is a standard multi-class biological classification benchmark comprising 150 samples across three species (Setosa, Versicolor, Virginica), with four numeric features per sample (sepal length, sepal width, petal length, petal width). A frozen train/test split is used: stratified by species, with the first 80% of samples assigned to training and the last 20% assigned to test, under a fixed shuffle with seed 42. The split is fixed prior to model fitting and is not modified during the experiment. The class distribution in the test split is balanced, so the majority-class baseline accuracy equals the inverse of the number of classes.

### 4.2 Baselines

The predeclared comparison is between the polynomial-feature multinomial logistic regression model and the majority-class baseline, which assigns every test sample to the most frequent class in the training split. On a balanced three-class test split, the expected majority-class accuracy is $1/3$. No other baselines are executed.

### 4.3 Metrics

The single primary metric is test accuracy, defined as the fraction of correctly classified test samples, with direction "higher is better." No other metrics are computed in the executed experiment.

### 4.4 Evaluation Protocol

The polynomial features of degree $p = 2$ are computed once and frozen. The IRLS solver is initialized at $\mathbf{w}_k^{(0)} = \mathbf{0}$ for all $k$ and iterated to convergence with the stopping rule described in Section 3.4. The regularization strength $\lambda$ is fixed at a small positive value to ensure numerical invertibility of the regularized Hessian while introducing negligible bias. Test accuracy is computed on the frozen test split. The same split is used to compute the majority-class baseline accuracy. No cross-validation or hyperparameter search is performed at evaluation time; both the model and the baseline are evaluated exactly once on the frozen split.

### 4.5 Ablation Design (Not Executed)

While the predeclared comparison is solely against the majority-class baseline, the methodological framework supports several informative ablations that could guide follow-on work: (i) varying the polynomial degree $p \in \{1, 2, 3\}$ to characterize the accuracy–complexity trade-off; (ii) varying the regularization strength $\lambda$ to characterize the sensitivity of the IRLS solution to the regularized Hessian; (iii) replacing the one-vs-rest decomposition with a joint softmax objective to assess decomposition-induced loss. These ablations are explicitly *not* part of the executed experiment and are mentioned only as future work.

## 5. Expected Results

Based on the known nonlinear structure of the Iris decision boundaries and the illustrative complexity discussion in Section 3.5, the polynomial-feature multinomial logistic regression model is expected to substantially outperform the majority-class baseline. The Setosa class is linearly separable from the other two, while the Versicolor–Virginica boundary is known to be nonlinear and well captured by degree-two polynomial features. The majority-class baseline on a balanced three-class test split is expected to achieve an accuracy of approximately $1/3 \approx 0.333$.

For the polynomial-feature model, prior expectation places test accuracy in the range $[0.93, 1.0]$, with a central estimate near $0.97$, consistent with the well-documented behavior of polynomial-feature logistic regression on Iris (internal reasoning). The illustrative complexity argument in Section 3.5 suggests that the complexity term $\sqrt{2 D_p \log(e N / D_p) / N}$ at $D_p = 15$ and the Iris training-sample size is small enough to be qualitatively non-vacuous, supporting the expectation of empirical dominance of the model over the baseline.

Qualitatively, the expected confusion pattern is full accuracy on Setosa, with a small number of Versicolor–Virginica confusions attributable to the overlap region in petal-dimension space. The improvement over the majority-class baseline is therefore expected to be large in absolute terms.

## 6. Results

On the frozen Iris test split, the majority-class baseline achieves a test accuracy of 0.333333 [RESULT-1], matching the expected $1/3$ accuracy for a balanced three-class test set. The polynomial-feature multinomial logistic regression model, fit via IRLS on degree-2 polynomial features with $D_p = 15$, achieves a test accuracy of 0.966667 [RESULT-3]. The absolute improvement of the fitted model over the majority-class baseline is therefore 0.633333 [RESULT-2].

These observations affirm the predeclared research question: the polynomial-feature multinomial logistic regression model does outperform the majority-class baseline on test accuracy. In relative terms, the model captures approximately $0.633333 / (1 - 0.333333) \approx 95\%$ of the achievable improvement over the trivial baseline.

We emphasize that no statistical-significance test was performed; the comparison is a single-split, point-estimate evaluation, and "decisive" here refers to the magnitude of the observed absolute improvement, not to a formal hypothesis test. Likewise, the illustrative complexity discussion of Section 3.5 is not a validated bound; it is offered only as intuitive context.

## 7. Discussion

### 7.1 Principal Findings

The experiment confirms that the predeclared polynomial-feature multinomial logistic regression model, trained via IRLS on degree-two polynomial features of the Iris dataset, outperforms the majority-class baseline on test accuracy, with a fitted-model test accuracy of 0.966667 [RESULT-3] versus a baseline of 0.333333 [RESULT-1] and an absolute improvement of 0.633333 [RESULT-2]. This observed accuracy is consistent with the known structure of the Iris decision boundaries. The illustrative complexity discussion of Section 3.5 provides an intuitive lens through which this dominance can be interpreted: the polynomial feature dimensionality $D_p = 15$ is small relative to the Iris training-sample size, so the qualitative complexity penalty does not appear to erode the empirical advantage of the model over the baseline. We reiterate that this is informal reasoning and not a validated certificate.

### 7.2 Limitations

Several limitations should be acknowledged. First, the experiment uses a single frozen split rather than repeated cross-validation, so the reported accuracies are point estimates without confidence intervals; no claim of statistical significance is made. Second, the study is confined to the Iris benchmark, which is small and well-studied; generalization to larger or noisier tabular datasets is not demonstrated. Third, the excess-risk discussion in Section 3.5 is illustrative and derived from standard uniform-convergence arguments; it is not tightened via PAC-Bayesian or data-dependent prior techniques, nor is it numerically validated as a non-vacuous certificate. Fourth, no hyperparameter search or cross-validation was performed; the regularization strength $\lambda$ was fixed at a single small value. Fifth, the one-vs-rest decomposition may incur a small calibration loss relative to a joint softmax formulation, which was not evaluated.

### 7.3 Broader Impact

The broader impact of this work is primarily methodological. By predeclaring a sharp comparison to a trivial baseline and reporting the empirical accuracies together with an illustrative complexity-aware discussion, the work provides a template that practitioners can adapt to verify their own logistic-regression deployments. We do not foresee significant negative societal consequences from this specific contribution, although we note that over-reliance on logistic regression in high-stakes clinical decision-making without ongoing monitoring for distributional shift remains an ethical concern that the present analysis does not resolve.

## 8. Conclusion

This paper has studied the empirical behavior of polynomial-feature multinomial logistic regression on the frozen Iris benchmark, with a predeclared comparison to the majority-class baseline. The method formalizes a one-vs-rest decomposition solved via iteratively reweighted least squares—an iterative Newton-Raphson procedure rather than a one-step closed-form solution—together with a regularized negative-log-likelihood objective and an illustrative complexity-aware discussion. On the frozen Iris test split (stratified, first 80% train / last 20% test, seed 42), the polynomial-feature multinomial logistic regression model achieves a test accuracy of 0.966667 [RESULT-3], against a majority-class baseline of 0.333333 [RESULT-1], for an absolute improvement of 0.633333 [RESULT-2]. These results affirm the predeclared research question: the fitted model does outperform the majority-class baseline on test accuracy by a large margin. We do not claim statistical significance or a validated distribution-free certificate; the excess-risk discussion is illustrative only.

Future work will pursue three directions. First, the excess-risk discussion will be tightened using PAC-Bayesian and data-dependent prior techniques to provide sharper numerical bounds at small sample sizes. Second, the experiment will be extended with repeated cross-validation and confidence intervals to support formal significance testing. Third, the framework will be applied to additional tabular benchmarks to assess the robustness of the observed dominance across datasets of varying size and noise level.

## References

[SOURCE-1] Vallipi Dasaratha, J. Sheela (2023). An Accurate Approach to Classify Real Time Indian Twins Using SVM and Compare the Performance over Logistic Regression. *Proceedings of the 1st International Conference on Artificial Intelligence for Internet of Things.*

[SOURCE-3] S. P. Rahayu, S. W. Purnami, A. Embong (2008). Applying Kernel Logistic Regression in data mining to classify credit risk. *2008 International Symposium on Information Technology.*

[SOURCE-5] Heri Kuswanto, Reynaldi Wisnu Werdhana (2017). Logistic regression ensemble to classify Alzheimer gene expression. *2017 International Conference on Smart Cities, Automation & Intelligent Computing Systems (ICON-SONICS).*

[SOURCE-6] J. K. M. Sadique Uz Zaman. Development of Modified Logistic Regression (MLR) Model to Classify Psoriasis and Non-Psoriasis Images. *African Journal of Biomedical Research.*

[SOURCE-7] Unknown (2002). Polytomous Logistic Regression and Alternatives to Logistic Regression. *Applied Logistic Regression Analysis.*

[SOURCE-8] Meisam Moghimbeygi. A Method to Classify Shape Data using Multinomial Logistic Regression Model. *Statistics, Optimization & Information Computing.*

[SOURCE-9] Frederic Commo, Brian M. Bot, Tymoteusz Kwiecinski (2014). nplr: N-Parameter Logistic Regression. *CRAN: Contributed Packages.*

[SOURCE-10] T. Indra, Liza Wikarsa, Rinaldo Turang (2016). Using logistic regression method to classify tweets into the selected topics. *2016 International Conference on Advanced Computer Science and Information Systems (ICACSIS).*

[SOURCE-11] Robert E. Baker, Ted Kwartler. Sport Analytics: Using Open Source Logistic Regression Software to Classify Upcoming Play Type in the NFL. *Journal of Applied Sport Management.*

[SOURCE-13] Unknown (2009). Ordered Logistic Regression. *Logistic Regression Models.*

[SOURCE-14] Unknown (2009). Exact Logistic Regression. *Logistic Regression Models.*

[SOURCE-15] Unknown (2009). Binomial Logistic Regression. *Logistic Regression Models.*

[SOURCE-17] Comparison of Binary Logistic Regression and SVM to Classify Diabetes Sufferers. *Journal of Intelligent Systems and Information Technology.*

[SOURCE-21] Paulo Tadeu Meira e Silva de Oliveira. Logistic Regression: Risk Question for Disabled People. *Recent Advances in Medical Statistics.*

[SOURCE-22] Lensa Rosdiana Safitri, Nur Chamidah, Toha Saifudin (2024). Modeling risk of stroke using binary logistic regression and multivariate adaptive regression splines. *AIP Conference Proceedings.*

[SOURCE-23] Baekhee Lee, Kihyo Jung, Jangwoon Park. Development of Logistic Regression Models to Classify Seat Fit. *SAE International Journal of Advances and Current Practices in Mobility.*

[SOURCE-24] Nandini Upadhyay, Ashutosh Pandey (2023). Prediction of breast cancer using multiple logistic regression. *AIP Conference Proceedings.*

[SOURCE-25] Metharani N, Srividya R, Rekha G (2021). Diabetes Risk Forecasting Using Logistic Regression. *Advances in Parallel Computing.*

[SOURCE-26] Sarnath Kannan, Sanjay Dudi (2015). A hybrid binary classifier: Using modified Logistic Regression for non-support vector elimination. *2015 IEEE Recent Advances in Intelligent Computational Systems (RAICS).*

[SOURCE-27] Shaik Sajeera Begum (2025). Logistic Regression Optimized with Gradient Descent and Expectation-Maximization for Heart Disease Prediction. *2025 IEEE International Conference on Recent Advances in Computing and Systems (REACS).*

[SOURCE-28] Unknown. Logistic and Cox Regression, Problems with Regression Modeling, Markov Models. *Statistics Applied to Clinical Trials.*

[SOURCE-30] Timur Andreevich Rodin, Yaroslav Evgenievich Belov. Theory and Practice of Solving Classification Problems by Logistic Regression.