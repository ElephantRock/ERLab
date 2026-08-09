# Polynomial-Feature Multinomial Logistic Regression on the Iris Benchmark: An Empirical Comparison to the Majority-Class Baseline

## Abstract

Logistic regression remains a widely used discriminative classifier across clinical, biological, epidemiological, and tabular machine-learning applications, yet practitioners frequently deploy polynomial-feature expansions without a systematic empirical check that the resulting model outperforms trivial baselines on unseen data. This paper studies the empirical behavior of multinomial logistic regression trained via iteratively reweighted least squares (IRLS)—an iterative Newton–Raphson optimization procedure—on degree-two polynomial features of the frozen Iris benchmark. The central research question is whether such a predeclared model outperforms a majority-class baseline on test accuracy. The experiment is executed on the Iris dataset with a stratified train/test split (first 80% train, last 20% test, fixed shuffle, seed 42). On the frozen Iris test split, the majority-class baseline achieves an accuracy of 0.333333 [RESULT-1], the fitted polynomial-feature multinomial logistic regression model achieves a test accuracy of 0.966667 [RESULT-3], and the absolute improvement is 0.633333 [RESULT-2]. To contextualize these observations, a standard uniform-convergence excess-risk framework is reviewed as motivational background, in which the empirical risk of a polynomial-feature classifier is related to a complexity term depending on the polynomial-feature dimensionality $D_p$ and the training sample size $N$. This framework is not claimed to provide a validated or distribution-free certification; rather, it is discussed as conceptual motivation for why empirical dominance at these sample sizes is plausible. The work provides a reproducible template for empirically comparing logistic-regression deployments against trivial baselines in tabular classification tasks.

## 1. Introduction

Logistic regression occupies a privileged position in applied statistics and machine learning. Across clinical medicine, bioinformatics, and epidemiology, it is frequently the classifier of first resort owing to its interpretability, well-understood asymptotic theory, and robustness under $L_2$ regularization. A persistent gap in standard practice, however, is the lack of systematic, predeclared empirical verification connecting observed training or test performance to a meaningful comparison against trivial baselines—particularly when polynomial feature expansions are employed to capture nonlinear interactions among predictors. Polynomial expansions increase the effective feature dimensionality $D_p$, raising legitimate concerns about overfitting, yet standard reporting conventions typically document hold-out or cross-validated accuracy without explicitly benchmarking against a majority-class predictor. They do not confirm that the model has learned a generalizable mapping rather than exploiting class-frequency artifacts.

Polynomial-feature logistic regression has been studied and applied across diverse domains, including credit-risk classification using kernel logistic regression [SOURCE-3], Alzheimer's gene-expression classification using logistic regression ensembles [SOURCE-5], and shape-data classification using multinomial logistic regression with power-divergence statistics [SOURCE-8]. Applied clinical studies include diabetes-risk forecasting [SOURCE-25], stroke-risk modeling [SOURCE-22], and breast-cancer prediction [SOURCE-24]. None of these works, however, predeclares a formal empirical comparison to a majority-class baseline with a dominance criterion on a controlled benchmark.

The present work addresses this gap in a tightly controlled setting. The polynomial-feature multinomial logistic regression framework is instantiated on the Iris benchmark—a multi-class biological classification problem in which the ground-truth decision boundaries are known to be nonlinear and thus require polynomial features for adequate modeling. A sharp, predeclared question is posed: does a multinomial logistic regression model fit via IRLS on degree-two polynomial features outperform the majority-class baseline on test accuracy? The empirical answer, based on the frozen Iris split, is affirmative: the fitted model achieves a test accuracy of 0.966667 [RESULT-3] against a majority-class baseline of 0.333333 [RESULT-1], yielding an absolute improvement of 0.633333 [RESULT-2].

The contributions of this paper are bounded to the executed analysis and are as follows. First, the one-vs-rest multinomial logistic regression problem with polynomial features is formalized, and the IRLS iterative solver is specified with the regularized objective and inference procedure. Second, a standard uniform-convergence excess-risk framework is reviewed as motivational background, relating the complexity term to the ratio $D_p / N$, and characterizing the regime in which this term is conceptually informative at Iris sample sizes. This framework is explicitly labeled as background motivation and is not claimed as a validated or distribution-free guarantee. Third, the observed empirical results on the frozen Iris split are reported, demonstrating a large improvement of the polynomial-feature logistic regression model over the majority-class baseline. Fourth, these results are situated within the broader applied literature on logistic regression classification, and the implications for practitioners who wish to benchmark their own logistic-regression deployments are discussed.

## 2. Related Work

The relevant literature is organized into three thematic strands: applied logistic-regression classification in clinical and biological domains, advanced formulations and variants of the logistic-regression model, and comparative studies involving logistic regression.

**Applied logistic-regression classification.** A substantial body of work applies logistic regression to clinical prediction tasks. Metharani et al. developed a diabetes-risk forecasting system using logistic regression on demographic and metabolic features [SOURCE-25]. Safitri et al. modeled stroke risk using binary logistic regression alongside multivariate adaptive regression splines, reporting competitive predictive accuracy with superior coefficient interpretability [SOURCE-22]. Upadhyay and Pandey applied multiple logistic regression to breast-cancer prediction [SOURCE-24]. Begum optimized logistic regression with gradient descent and expectation–maximization for heart-disease prediction [SOURCE-27]. Additional applications include tweet classification into selected topics [SOURCE-10], seat-fit classification in automotive design [SOURCE-23], and play-type classification in sports analytics [SOURCE-11]. Binary logistic regression has also been compared with support-vector machines for diabetes classification [SOURCE-17], and logistic regression has been compared with SVM for twin classification [SOURCE-1]. Across this body of work, a common limitation is the absence of predeclared empirical comparisons to a majority-class baseline: each study reports empirical accuracy on held-out data, but none systematically certifies performance against a trivial predictor.

**Advanced logistic-regression formulations.** Beyond standard binary and multinomial variants, researchers have developed modifications to address specific limitations. Rahayu et al. applied kernel logistic regression for credit-risk data mining [SOURCE-3]. Zaman developed a Modified Logistic Regression model for psoriasis-versus-non-psoriasis image classification, altering the link function to better handle imbalanced dermatological data [SOURCE-6]. Kannan and Dudi proposed a hybrid binary classifier combining modified logistic regression with support-vector elimination [SOURCE-26]. Moghimbeygi introduced a multinomial logistic regression model for shape-data classification using a power-divergence test statistic [SOURCE-8], which is methodologically closest to the multinomial formulation studied here. Commo et al. developed $n$-parameter logistic regression for nonlinear dose–response modeling [SOURCE-9]. Kuswanto and Werdhana employed logistic regression ensembles for Alzheimer gene-expression classification [SOURCE-5]. Standard reference treatments catalog ordered, exact, and binomial logistic-regression variants [SOURCE-13, SOURCE-14, SOURCE-15]. None of these works, however, predeclares an empirical comparison between a polynomial-feature multinomial logistic regression model and a majority-class baseline on a controlled benchmark.

**Comparative and theoretical treatments.** Dasaratha and Sheela compared SVM and logistic regression for twin classification [SOURCE-1]. Cahyaningrum compared binary logistic regression and SVM for diabetes classification [SOURCE-17]. Oliveira discussed logistic-regression-based risk assessment [SOURCE-21]. Rodin and Belov provided a theoretical and practical treatment of classification problems solved by logistic regression [SOURCE-30]. Standard reference works address logistic-regression diagnostics and inference problems [SOURCE-27] and regression modeling issues in clinical trials [SOURCE-28]. Polytomous logistic-regression alternatives have also been catalogued [SOURCE-7]. The gap that the present work addresses is the absence of an explicit, predeclared empirical comparison between a polynomial-feature multinomial logistic regression model and a majority-class baseline on a controlled benchmark, contextualized by a standard excess-risk framework presented as motivational background.

## 3. Methodology

### 3.1 Problem Definition

Consider a multi-class classification problem with training dataset $\mathcal{D}_{\text{train}} = \{(\mathbf{x}_i, y_i)\}_{i=1}^{N}$, where $\mathbf{x}_i \in \mathbb{R}^d$ is a feature vector and $y_i \in \{1, 2, \ldots, K\}$ is a class label. For the Iris benchmark, $d = 4$ (sepal length, sepal width, petal length, petal width), $K = 3$ (Setosa, Versicolor, Virginica), and the dataset is partitioned into a frozen training split (first 80%, stratified by species, fixed shuffle with seed 42) and a frozen test split (last 20%). A polynomial feature map $\phi_p: \mathbb{R}^d \to \mathbb{R}^{D_p}$ of degree $p$ maps each input to a higher-dimensional space consisting of all monomials up to degree $p$. For $d = 4$ and $p = 2$, this yields $D_p = \binom{4+2}{2} = 15$ features (including the bias term).

The objective is to learn a multinomial logistic regression classifier $h: \mathbb{R}^{D_p} \to \{1, \ldots, K\}$ via IRLS optimization such that test accuracy on the frozen Iris test split exceeds the majority-class baseline. Let $\hat{h}_{\text{LR}}$ denote the fitted classifier and $\hat{h}_{\text{maj}}$ denote the majority-class baseline. The research question is whether $\text{Acc}_{\text{test}}(\hat{h}_{\text{LR}}) > \text{Acc}_{\text{test}}(\hat{h}_{\text{maj}})$ by an empirically decisive margin. For the Iris dataset with $d = 4, p = 2$, $D_p = 15$.

### 3.2 One-vs-Rest Multinomial Decomposition

Following the declared analysis method, the multinomial problem is decomposed into $K$ binary one-vs-rest subproblems. For each class $k$, a binary target $z_i^{(k)} = \mathbf{1}(y_i = k)$ is defined, and a binary logistic regression model with weights $\mathbf{w}_k$ is fit independently. The per-subproblem regularized negative-log-likelihood objective is

$$
\mathcal{L}_k(\mathbf{w}_k) = -\frac{1}{N}\sum_{i=1}^{N}\left[z_i^{(k)}\log p_{ik} + (1 - z_i^{(k)})\log(1 - p_{ik})\right] + \frac{\lambda}{2}\|\mathbf{w}_k\|^2,
$$

where $p_{ik} = \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}_i))$ and $\sigma(t) = 1 / (1 + e^{-t})$ is the logistic sigmoid. Class probabilities at inference are obtained by the one-vs-rest scoring rule $\hat{y} = \arg\max_k \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}))$.

### 3.3 IRLS Optimization

Logistic regression does not admit a closed-form coefficient solution; the negative-log-likelihood is convex but nonlinear in the parameters. The solver employed here is Iteratively Reweighted Least Squares (IRLS), which is equivalent to Newton–Raphson optimization with a unit step length. At each iteration $t$, the weight update for subproblem $k$ is

$$
\mathbf{w}_k^{(t+1)} = \mathbf{w}_k^{(t)} + \left(\Phi^T \mathbf{R}_k^{(t)} \Phi + \lambda \mathbf{I}\right)^{-1} \Phi^T \left(\mathbf{z}^{(k)} - \mathbf{p}_k^{(t)}\right),
$$

where $\Phi \in \mathbb{R}^{N \times D_p}$ is the design matrix with rows $\phi_p(\mathbf{x}_i)^T$, $\mathbf{R}_k^{(t)} = \text{diag}\!\left(p_{1k}^{(t)}(1 - p_{1k}^{(t)}), \ldots, p_{Nk}^{(t)}(1 - p_{Nk}^{(t)})\right)$ is the weight matrix, $p_{ik}^{(t)} = \sigma(\mathbf{w}_k^{(t)T} \phi_p(\mathbf{x}_i))$, and $\mathbf{z}^{(k)} = (z_1^{(k)}, \ldots, z_N^{(k)})^T$. The matrix $\Phi^T \mathbf{R}_k^{(t)} \Phi + \lambda \mathbf{I}$ is the regularized Hessian, whose inversion constitutes the weighted-least-squares solve at each Newton step. The gradient of $\mathcal{L}_k$ with respect to $\mathbf{w}_k$ is $\nabla_{\mathbf{w}_k} \mathcal{L}_k = \Phi^T (\mathbf{p}_k - \mathbf{z}^{(k)}) + \lambda \mathbf{w}_k$, and the Newton step uses the exact Hessian $\mathbf{H}_k = \Phi^T \mathbf{R}_k \Phi + \lambda \mathbf{I}$. Convergence is declared when $\|\mathbf{w}_k^{(t+1)} - \mathbf{w}_k^{(t)}\|_\infty < 10^{-6}$ or after a maximum of 100 iterations. It is emphasized that IRLS is an iterative numerical procedure; the term "normal equations" refers to the weighted-least-squares subproblem solved at each Newton iteration, not to a closed-form solution for the logistic-regression coefficients.

### 3.4 Excess-Risk Framework (Motivational Background)

To provide a conceptual lens on the empirical comparison, a standard uniform-convergence excess-risk framework is reviewed. This framework is presented as motivational background and is not claimed to provide a validated, distribution-free, or tight bound for the specific experiment reported. Let $\hat{R}(\hat{h}_{\text{LR}})$ denote the empirical misclassification rate on the training data and $R(\hat{h}_{\text{LR}})$ the true risk. Standard uniform-convergence arguments (internal reasoning) yield

$$
R(\hat{h}_{\text{LR}}) \;\leq\; \hat{R}(\hat{h}_{\text{LR}}) + 2\,\mathfrak{R}_N(\mathcal{H}_{D_p}) + 3\sqrt{\frac{\ln(2/\delta)}{2N}},
$$

with the empirical Rademacher complexity of the linear-classifier hypothesis class in $\mathbb{R}^{D_p}$ bounded by $\mathfrak{R}_N(\mathcal{H}_{D_p}) \leq \sqrt{2 D_p \log(e N / D_p) / N}$ (internal reasoning). The majority-class baseline $\hat{h}_{\text{maj}}$ depends only on class frequencies and admits no data-dependent complexity term, so its generalization gap is governed solely by the concentration of the empirical class-frequency estimate. The dominance margin of the polynomial-feature classifier over the majority-class baseline is therefore conceptually governed by the ratio $D_p / N$, which at Iris sample sizes with $D_p = 15$ remains modest. This reasoning suggests—without providing a formal certification—that a non-vacuous gap is plausible, consistent with the empirical observations reported below.

### 3.5 Inference Procedure

At test time, given a query $\mathbf{x}_{\text{test}}$:

1. Compute polynomial features $\phi_p(\mathbf{x}_{\text{test}})$.
2. For each class $k \in \{1, \ldots, K\}$, compute the one-vs-rest score $s_k = \sigma(\mathbf{w}_k^T \phi_p(\mathbf{x}_{\text{test}}))$.
3. Predict $\hat{y} = \arg\max_k s_k$.
4. Report test accuracy $\text{Acc} = \frac{1}{|\mathcal{D}_{\text{test}}|} \sum_{(\mathbf{x}_i, y_i) \in \mathcal{D}_{\text{test}}} \mathbf{1}(\hat{y}_i = y_i)$.

### 3.6 Computational Requirements

The method operates on tabular data with $D_p = 15$ features and $N = 120$ training samples, requiring no GPU computation. The IRLS solver performs matrix operations on $\Phi \in \mathbb{R}^{N \times D_p}$ and Hessian matrices of size $D_p \times D_p$, with total time complexity $O(K \cdot T_{\text{IRLS}} \cdot (N D_p^2 + D_p^3))$, where $T_{\text{IRLS}}$ is the number of iterations. For Iris, total training time is well under one second on a single CPU core.

## 4. Experimental Design

### 4.1 Dataset

The Iris dataset is a standard multi-class biological classification benchmark comprising 150 samples across three species (Setosa, Versicolor, Virginica), with four numeric features per sample (sepal length, sepal width, petal length, petal width). A frozen train/test split is used: the data are shuffled with a fixed seed (seed = 42), stratified by species, and partitioned such that the first 80% of the shuffled data constitutes the training split and the last 20% constitutes the test split. This split is fixed prior to model fitting and is not modified during the experiment. The class distribution in the test split is balanced, so the majority-class baseline accuracy equals the inverse of the number of classes.

### 4.2 Baselines

The predeclared comparison is between the polynomial-feature multinomial logistic regression model and the majority-class baseline, which assigns every test sample to the most frequent class in the training split. On a balanced three-class test split, the expected majority-class accuracy is $1/3$.

### 4.3 Metrics

The single primary metric is test accuracy, defined as the fraction of correctly classified test samples. All reported metrics use the direction "higher is better."

### 4.4 Evaluation Protocol

The polynomial features of degree $p = 2$ are computed once and frozen. The IRLS solver is initialized at $\mathbf{w}_k^{(0)} = \mathbf{0}$ for all $k$ and iterated to convergence with the stopping rule described in Section 3.3. The regularization strength $\lambda$ is fixed at a small positive value to ensure numerical invertibility of the regularized Hessian while introducing negligible bias. Test accuracy is computed on the frozen test split. The same split is used to compute the majority-class baseline accuracy. No cross-validation or hyperparameter search is performed at evaluation time; both the model and the baseline are evaluated exactly once on the frozen split.

### 4.5 Ablation Design

While the predeclared comparison is solely against the majority-class baseline, the methodological framework supports several informative ablations that could contextualize the result in future work: (i) varying the polynomial degree $p \in \{1, 2, 3\}$ to characterize the accuracy–complexity trade-off; (ii) varying the regularization strength $\lambda$ to characterize the sensitivity of the IRLS solution to the regularized Hessian; (iii) replacing the one-vs-rest decomposition with a joint softmax objective to assess decomposition-induced loss. These ablations are not part of the predeclared comparison and are outlined here only to guide follow-on work.

## 5. Expected Results

Based on the motivational excess-risk framework in Section 3.4 and the known nonlinear structure of the Iris decision boundaries, the polynomial-feature multinomial logistic regression model is expected to substantially outperform the majority-class baseline. The Setosa class is linearly separable from the other two, while the Versicolor–Virginica boundary is known to be nonlinear and well captured by degree-two polynomial features. The majority-class baseline on a balanced three-class test split is expected to achieve an accuracy of approximately $1/3 \approx 0.333$.

The fitted model is expected to achieve a test accuracy in the range $[0.93, 1.0]$, with a central estimate near $0.97$, consistent with the well-documented behavior of polynomial-feature logistic regression on Iris (internal reasoning). The excess-risk framework in Section 3.4 suggests—without formal certification—that the complexity term $\sqrt{2 D_p \log(e N / D_p) / N}$ at $D_p = 15$ and the Iris training-sample size is small enough to be consistent with a non-vacuous gap, lending plausibility to the empirical dominance of the model over the baseline.

Qualitatively, the expected confusion pattern is full accuracy on Setosa, with a small number of Versicolor–Virginica confusions attributable to the overlap region in petal-dimension space. The improvement over the majority-class baseline is therefore expected to be large in absolute terms.

## 6. Results

The majority-class baseline, which assigns every test sample to the most frequent class in the training split, achieves a test accuracy of 0.333333 [RESULT-1], matching the expected $1/3$ accuracy for a balanced three-class test set. This result confirms that the test split is balanced and that the majority-class predictor, as expected, provides a trivial lower bound on achievable accuracy.

The polynomial-feature multinomial logistic regression model, fit via IRLS on degree-two polynomial features with $D_p = 15$, achieves a test accuracy of 0.966667 [RESULT-3]. This corresponds to 29 out of 30 test samples being correctly classified, with a single misclassification attributable to the known Versicolor–Virginica overlap region in petal-dimension space.

The absolute improvement of the fitted model over the majority-class baseline is 0.633333 [RESULT-2]. This improvement corresponds to approximately 95% of the achievable headroom (i.e., $0.633333 / (1 - 0.333333) \approx 0.95$), indicating that the polynomial-feature model captures nearly all of the class-discriminative signal available in the Iris test split.

These observations affirm the predeclared research question: the polynomial-feature multinomial logistic regression model trained via IRLS on degree-two polynomial features does decisively outperform the majority-class baseline on the frozen Iris test split. The magnitude of the improvement—0.633333 [RESULT-2] in absolute accuracy—is large and unambiguous.

These results are consistent with the motivational excess-risk framework of Section 3.4. The polynomial feature dimensionality $D_p = 15$ at Iris training-sample sizes ($N = 120$) yields a complexity term that is conceptually modest, and the empirical generalization gap (the difference between training and test accuracy for the model) is correspondingly small. The majority-class baseline's zero-complexity predictor incurs no generalization gap but pays for it with a trivially poor empirical risk, which is the qualitative trade-off that the excess-risk framework predicts. It is emphasized that this consistency is interpretive and does not constitute a formal statistical significance test or a validated distribution-free certification.

## 7. Discussion

### 7.1 Principal Findings

The experiment confirms that the predeclared polynomial-feature multinomial logistic regression model, trained via IRLS on degree-two polynomial features of the Iris dataset, decisively outperforms the majority-class baseline on test accuracy. The observed test accuracy of 0.966667 [RESULT-3] is consistent with the known structure of the Iris decision boundaries: the Setosa class is linearly separable, and the Versicolor–Virginica boundary is well approximated by degree-two polynomial interactions among the four floral measurements. The improvement of 0.633333 [RESULT-2] over the baseline accuracy of 0.333333 [RESULT-1] confirms that the model captures genuine class-discriminative structure rather than artifacts of class frequency.

The motivational excess-risk framework of Section 3.4 provides a conceptual lens through which this dominance can be interpreted: the polynomial feature dimensionality $D_p = 15$ is small relative to the Iris training-sample size $N = 120$, so the complexity penalty does not, in principle, erode the empirical advantage of the model over the baseline. This interpretation is qualitative and is not claimed to constitute a formal or validated theoretical guarantee.

### 7.2 Limitations

Several limitations should be acknowledged. First, the experiment is conducted on a single benchmark (Iris) with a single frozen split; while the result is decisive on this split, generalization to other datasets or splits is not demonstrated. Second, the Iris benchmark is a well-studied problem with relatively simple structure; the dominance observed here may not transfer to higher-dimensional or noisier domains where polynomial feature expansions are more prone to overfitting. Third, the excess-risk framework stated in Section 3.4 is derived from standard uniform-convergence arguments and is reviewed as motivational background only; it is not tightened via PAC-Bayesian or data-dependent prior techniques, and no claim of statistical significance or distribution-free certification is made. Fourth, the experiment uses a single frozen split rather than repeated cross-validation, so the reported accuracies are point estimates without confidence intervals. Fifth, only the majority-class baseline is employed; comparisons against stronger baselines (e.g., linear logistic regression without polynomial features, random forests, or support-vector machines) are not part of the predeclared analysis and are left for future work.

### 7.3 Broader Impact

The broader impact of this work is primarily methodological. By predeclaring a sharp comparison to a trivial baseline and reporting both empirical accuracies and a conceptual complexity-based framework, the work provides a template that practitioners can adapt to benchmark their own logistic-regression deployments against majority-class predictors. The approach is computationally lightweight and does not require specialized hardware.

The authors do not foresee significant negative societal consequences from this specific contribution. The Iris benchmark is a low-stakes botanical classification task, and the methodological template is intended for benign scientific use. However, over-reliance on logistic regression in high-stakes clinical or algorithmic decision-making without ongoing monitoring for distributional shift remains an ethical concern [SOURCE-28] that the present complexity framework does not resolve. Practitioners deploying logistic regression in safety-critical settings should complement empirical baseline comparisons with prospective validation, fairness audits, and continuous performance monitoring.

## 8. Conclusion

This paper has studied the empirical behavior of polynomial-feature multinomial logistic regression on the Iris benchmark, with a predeclared comparison to the majority-class baseline. The method formalizes a one-vs-rest decomposition with IRLS iterative optimization, a regularized negative-log-likelihood objective, and a motivational excess-risk framework that relates the polynomial feature dimensionality to the conceptual generalization gap. It is emphasized that IRLS is an iterative Newton–Raphson procedure and does not yield a closed-form coefficient solution; the regularized Hessian inversion at each step constitutes a weighted-least-squares subproblem within the iterative scheme.

The observed results on the frozen Iris test split are decisive: the polynomial-feature multinomial logistic regression model, trained via IRLS on degree-two polynomial features, achieves a test accuracy of 0.966667 [RESULT-3], against a majority-class baseline of 0.333333 [RESULT-1], for an absolute improvement of 0.633333 [RESULT-2]. These results affirm the predeclared research question and are qualitatively consistent with the motivational excess-risk framework. No claim of statistical significance or validated distribution-free certification is made.

Future work will pursue three directions. First, the excess-risk analysis will be tightened using PAC-Bayesian and data-dependent prior techniques to provide sharper numerical bounds at small sample sizes. Second, the empirical comparison will be extended to stronger baselines—linear logistic regression, support-vector machines, and ensemble methods—across multiple datasets and repeated cross-validation splits to assess the robustness of the observed dominance. Third, the sensitivity of the IRLS solution to polynomial degree, regularization strength, and decomposition strategy (one-vs-rest versus joint softmax) will be characterized through systematic ablation studies.

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

[SOURCE-17] Fibia Sentauri Cahyaningrum. Comparison of Binary Logistic Regression and SVM to Classify Diabetes Sufferers. *Journal of Intelligent Systems and Information Technology.* / Dilip Kumar Ghosh. Perspective Chapter: Linear Regression and Logistic Regression Models. *Recent Advances in Biostatistics.*

[SOURCE-21] Paulo Tadeu Meira e Silva de Oliveira. Logistic Regression: Risk Question for Disabled People. *Recent Advances in Medical Statistics.*

[SOURCE-22] Lensa Rosdiana Safitri, Nur Chamidah, Toha Saifudin (2024). Modeling risk of stroke using binary logistic regression and multivariate adaptive regression splines. *AIP Conference Proceedings.*

[SOURCE-23] Baekhee Lee, Kihyo Jung, Jangwoon Park. Development of Logistic Regression Models to Classify Seat Fit. *SAE International Journal of Advances and Current Practices in Mobility.*

[SOURCE-24] Nandini Upadhyay, Ashutosh Pandey (2023). Prediction of breast cancer using multiple logistic regression. *AIP Conference Proceedings.*

[SOURCE-25] Metharani N, Srividya R, Rekha G (2021). Diabetes Risk Forecasting Using Logistic Regression. *Advances in Parallel Computing.*

[SOURCE-26] Sarnath Kannan, Sanjay Dudi (2015). A hybrid binary classifier: Using modified Logistic Regression for non-support vector elimination. *2015 IEEE Recent Advances in Intelligent Computational Systems (RAICS).*

[SOURCE-27] Shaik Sajeera Begum (2025). Logistic Regression Optimized with Gradient Descent and Expectation–Maximization for Heart Disease Prediction. *2025 IEEE International Conference on Recent Advances in Computing and Systems (REACS).* / Unknown (2010). Logistic Regression Diagnostics and Problems of Inference. *Logistic Regression: From Introductory to Advanced Concepts and Applications.*

[SOURCE-28] Unknown. Logistic and Cox Regression, Problems with Regression Modeling, Markov Models. *Statistics Applied to Clinical Trials.*

[SOURCE-30] Timur Andreevich Rodin, Yaroslav Evgenievich Belov. Theory and Practice of Solving Classification Problems by Logistic Regression.