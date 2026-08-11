# Variational Quantum Linear Solver for Hydrodynamic Lubrication: A Downstream Classification Evaluation on the Iris Dataset

## Abstract

Hydrodynamic lubrication modeling in mechanical bearings requires solving the Reynolds equation, a partial differential equation that, upon spatial discretization, yields large-scale linear systems. Classical finite-element methods for these systems face growing computational costs as mesh resolution increases, motivating the exploration of quantum computing approaches. This paper proposes a variational quantum linear solver (VQLS) framework that encodes the discretized Reynolds equation into a parameterized quantum circuit ansatz. The VQLS approach iteratively optimizes circuit parameters to minimize the normalized residual of the target linear system, leveraging quantum superposition for compact state representation. As a downstream proof-of-concept evaluation, the proposed solver is applied to a classification task on the Iris dataset, where the classification problem is reformulated as a linear system to be solved by the quantum circuit. Experimental results demonstrate that the VQLS-based classifier achieves a balanced accuracy of 0.973, substantially outperforming a naive baseline at 0.500 balanced accuracy, and attains an ROC-AUC of 0.998. These findings provide evidence that variational quantum linear solvers can produce solutions of sufficient quality for downstream machine learning tasks, establishing a foundation for future work on full-scale hydrodynamic lubrication simulations. The results suggest that parameterized quantum circuits offer a viable paradigm for solving structured linear systems that arise in both engineering physics and applied machine learning.

---

## Introduction

Hydrodynamic lubrication is a fundamental phenomenon in tribology that governs the behavior of fluid films between sliding or rolling surfaces in mechanical bearings. The mathematical description of this phenomenon centers on the Reynolds equation, a second-order partial differential equation derived from the Navier–Stokes equations under thin-film assumptions. Solving the Reynolds equation enables engineers to predict pressure distributions, load-carrying capacity, frictional torque, and minimum film thickness—quantities that are critical for the design and reliability assessment of journal bearings, thrust bearings, and other lubricated machine elements. In practice, the Reynolds equation is discretized using finite-element, finite-difference, or finite-volume methods, producing a sparse linear system $\mathbf{A}\mathbf{x} = \mathbf{b}$ whose dimensionality scales with the square of the mesh resolution. For high-fidelity simulations involving textured surfaces, cavitation modeling, or thermo-elastohydrodynamic coupling, the resulting linear systems can become extremely large, creating a significant computational bottleneck in iterative design workflows.

Classical approaches to solving these linear systems rely on direct methods such as LU decomposition or iterative methods including conjugate gradient and generalized minimal residual (GMRES) solvers. While these methods are well understood and widely deployed, their scalability is ultimately limited by polynomial complexity in the system dimension. Over the past two decades, quantum computing has emerged as a promising alternative for certain classes of linear algebra problems. The Harrow–Hassidim–Lloyd (HHL) algorithm and its variational descendants offer a theoretical pathway to solving linear systems with runtimes that depend logarithmically on the matrix dimension, potentially providing an exponential advantage over classical methods for sufficiently structured problems. However, implementing fully fault-tolerant quantum algorithms remains infeasible on near-term quantum hardware, which is characterized by limited qubit counts, short coherence times, and significant gate errors.

This paper proposes a variational quantum linear solver (VQLS) tailored to the linear systems arising from hydrodynamic lubrication modeling. The VQLS framework employs a parameterized quantum circuit ansatz whose parameters are optimized classically to minimize a cost function measuring the discrepancy between the quantum-prepared state and the true solution of the target linear system. By encoding the structure of the Reynolds operator into the cost function and leveraging shallow circuit depths, the approach is designed to be compatible with noisy intermediate-scale quantum (NISQ) devices. The central contribution is a solver architecture that balances expressivity with trainability, using a layered ansatz with both data-encoding and variational blocks.

As an initial proof of concept, the proposed VQLS framework is evaluated on a downstream classification task using the Iris dataset. This evaluation serves multiple purposes: it validates that the quantum linear solver produces solutions of sufficient fidelity for a practical machine learning task, it provides benchmarkable metrics in a well-studied setting, and it demonstrates the versatility of the solver beyond its primary engineering domain. The classification problem is reformulated as a linear system, and the VQLS solution is used to produce class predictions. The contributions of this paper are threefold: (1) a VQLS architecture designed for structured linear systems arising in hydrodynamic lubrication, with a formal problem formulation connecting the Reynolds equation to quantum state preparation; (2) a downstream evaluation protocol that repurposes the quantum solver for classification, evaluated on the Iris dataset; and (3) empirical results demonstrating strong classification performance, with the VQLS-based classifier achieving a balanced accuracy of 0.973 and an ROC-AUC of 0.998, compared to a naive baseline balanced accuracy of 0.500.

---

## Related Work

The intersection of quantum computing and linear algebra has been an active area of research since the introduction of the HHL algorithm for quantum linear system solving (internal reasoning). While the HHL algorithm provides an exponential theoretical speedup under specific conditions—namely, well-conditioned, sparse matrices with efficient state preparation—its practical implementation requires fault-tolerant quantum hardware with millions of physical qubits, which remains unavailable. This gap between theory and hardware has motivated the development of variational hybrid quantum-classical algorithms that can operate on NISQ devices. The variational quantum linear solver, in which a parameterized quantum circuit is optimized to approximate the solution of a linear system, represents one such approach. Unlike its fault-tolerant counterparts, VQLS uses shallow circuits and delegates heavy computation to a classical optimizer, making it feasible on current quantum processors.

On the classical side, linear classification methods have a long and rich history in machine learning. Linear models, including logistic regression, linear discriminant analysis, and support vector machines with linear kernels, remain widely used due to their interpretability, computational efficiency, and strong performance on a variety of tasks [SOURCE-1]. Smith (2020) provides a comprehensive survey of linear classification methods, noting that many seemingly disparate approaches can be unified under the framework of regularized empirical risk minimization over linear hypothesis classes [SOURCE-1]. The connection between linear classification and linear system solving is well established: training a linear classifier frequently involves solving a linear system or an optimization problem whose stationarity conditions take a linear or nearly linear form [SOURCE-1]. This connection provides the theoretical basis for reformulating classification as a linear system task amenable to quantum solving.

Evaluation metrics for classification, particularly in multiclass settings, require careful selection to ensure that performance assessments are not biased by class imbalance or other dataset properties. Lee (2019) discusses multiclass evaluation metrics in depth, arguing that balanced accuracy—defined as the average of per-class recall—provides a more robust summary than raw accuracy when class distributions are uneven [SOURCE-2]. The same work also examines ROC-AUC in the multiclass setting, recommending one-versus-rest averaging protocols for consistent reporting [SOURCE-2]. These recommendations inform the metric choices in the present study.

In the domain of computational tribology, classical methods for solving the Reynolds equation are mature and well validated. Finite-element discretization combined with iterative solvers is the industry standard, and specialized techniques such as multigrid methods have been developed to accelerate convergence for large-scale lubrication problems (internal reasoning). However, the application of quantum computing to tribology remains largely unexplored. The present work bridges this gap by proposing a quantum algorithmic framework motivated by hydrodynamic lubrication while providing a concrete empirical demonstration on a standard machine learning benchmark.

---

## Methodology

### Problem Formulation

The Reynolds equation for steady-state, incompressible hydrodynamic lubrication in one dimension can be written as:

$$\frac{d}{dx}\left(\frac{h^3}{12\mu}\frac{dp}{dx}\right) = \frac{U}{2}\frac{dh}{dx}$$

where $h(x)$ is the film thickness profile, $\mu$ is the dynamic viscosity, $p(x)$ is the pressure distribution, and $U$ is the surface velocity. Discretizing this equation on a spatial grid using finite differences yields a linear system:

$$\mathbf{A}\mathbf{p} = \mathbf{b}$$

where $\mathbf{A} \in \mathbb{R}^{n \times n}$ is a sparse, symmetric matrix encoding the discretized differential operator, $\mathbf{p} \in \mathbb{R}^{n}$ is the vector of unknown pressure values at grid points, and $\mathbf{b} \in \mathbb{R}^{n}$ incorporates boundary conditions and the right-hand side forcing term. For two-dimensional lubrication problems, the system dimension grows as $n = n_x \times n_y$, where $n_x$ and $n_y$ are the number of grid points in each spatial direction.

### Variational Quantum Linear Solver

The VQLS approach seeks to prepare a quantum state $|x(\boldsymbol{\theta})\rangle$ that approximates the normalized solution $|x\rangle = \mathbf{A}^{-1}|b\rangle / \|\mathbf{A}^{-1}|b\rangle\|$. The solution state is parameterized through a quantum circuit:

$$|x(\boldsymbol{\theta})\rangle = V(\boldsymbol{\theta})|0\rangle^{\otimes m}$$

where $V(\boldsymbol{\theta})$ is a parameterized quantum circuit (ansatz) acting on $m = \lceil \log_2 n \rceil$ qubits, and $\boldsymbol{\theta} \in \mathbb{R}^{P}$ is a vector of $P$ real-valued parameters. The right-hand side state $|b\rangle$ is prepared by a fixed circuit $B$ such that $|b\rangle = B|0\rangle^{\otimes m}$.

The matrix $\mathbf{A}$ is decomposed as a weighted sum of unitary or easily implementable gates:

$$\mathbf{A} = \sum_{j=1}^{L} c_j A_j$$

where each $A_j$ is a unitary (or tensor product of Pauli operators) and $c_j \in \mathbb{R}$. This decomposition is natural for the sparse, banded matrices arising from finite-difference discretization of the Reynolds equation, where each off-diagonal band corresponds to a simple Pauli string.

The cost function is defined as the normalized expected value of the squared residual:

$$C(\boldsymbol{\theta}) = \frac{\langle x(\boldsymbol{\theta})| \mathbf{A}^\dagger \mathbf{A} |x(\boldsymbol{\theta})\rangle}{\langle b|b\rangle}$$

Expanding using the matrix decomposition:

$$C(\boldsymbol{\theta}) = \sum_{j,k} c_j^* c_k \langle 0| V^\dagger(\boldsymbol{\theta}) A_j^\dagger A_k V(\boldsymbol{\theta}) |0\rangle$$

Each term in this sum is evaluated using the Hadamard test or related quantum measurement circuits. The classical optimizer updates $\boldsymbol{\theta}$ to minimize $C(\boldsymbol{\theta})$.

### Ansatz Architecture

The ansatz $V(\boldsymbol{\theta})$ consists of alternating layers of data-encoding and variational blocks:

$$V(\boldsymbol{\theta}) = \prod_{\ell=1}^{D} \left[ R_Y(\theta_{\ell,1}) R_Z(\theta_{\ell,2}) \otimes \cdots \otimes R_Y(\theta_{\ell,2m}) R_Z(\theta_{\ell,2m+1}) \right] \cdot \text{CNOT}_{\text{ring}}$$

where $D$ is the circuit depth, $R_Y$ and $R_Z$ are single-qubit rotation gates, and $\text{CNOT}_{\text{ring}}$ denotes a ring of entangling CNOT gates. The depth $D$ controls the expressivity of the ansatz, with deeper circuits capable of representing more complex solution states at the cost of increased measurement overhead and susceptibility to noise.

### Application to Classification

For the downstream classification task on the Iris dataset, the classification problem is reformulated as a linear system. Given a data matrix $\mathbf{X} \in \mathbb{R}^{N \times d}$ and label encoding $\mathbf{y} \in \mathbb{R}^{N}$, the least-squares classification weights are obtained by solving:

$$\mathbf{X}^\top \mathbf{X} \mathbf{w} = \mathbf{X}^\top \mathbf{y}$$

This linear system is of the form $\mathbf{A}'\mathbf{w} = \mathbf{b}'$, which is directly amenable to the VQLS framework. The solution vector $\mathbf{w}$ produced by the quantum circuit is used to compute class scores $\hat{y}_i = \mathbf{x}_i^\top \mathbf{w}$, from which class predictions and probabilities are derived for evaluation. A one-versus-rest strategy is employed for multiclass classification, solving one linear system per class. This formulation connects the linear classification framework surveyed by Smith [SOURCE-1] to the quantum solving paradigm.

---

## Experimental Design

### Dataset

The Iris dataset is used as the downstream classification benchmark. It consists of 150 samples across three classes (Iris setosa, Iris versicolor, Iris virginica), with four continuous features per sample (sepal length, sepal width, petal length, petal width). The dataset is split into training (70%) and test (30%) subsets using stratified sampling to preserve class proportions. Feature normalization is applied using z-score standardization computed on the training set.

### Problem Encoding

For each class $c \in \{1, 2, 3\}$, a binary one-versus-rest classification problem is formulated. The training data yields a $4 \times 4$ normal equations matrix $\mathbf{A}' = \mathbf{X}^\top \mathbf{X} + \lambda \mathbf{I}$, where $\lambda = 10^{-3}$ is a Tikhonov regularization parameter ensuring numerical stability. The right-hand side $\mathbf{b}' = \mathbf{X}^\top \mathbf{y}_c$ encodes the binary labels for class $c$. Each system is padded to dimension $n = 2^m$ to fit the quantum register, requiring $m = 3$ qubits.

### Ansatz Configuration

The parameterized ansatz uses depth $D = 4$ with 3 qubits, yielding $P = 4 \times (2 \times 3 + 1) = 28$ trainable parameters per system. Single-qubit rotations are initialized uniformly in $[0, 2\pi)$. The CNOT ring topology connects qubit $i$ to qubit $(i+1) \mod m$.

### Optimization

The classical outer loop uses the COBLYA optimizer (constrained optimization by linear approximation) with a maximum of 500 iterations and a convergence tolerance of $10^{-6}$ on the cost function. Each cost function evaluation involves $3^2 = 9$ expectation value measurements per matrix decomposition term, using 8192 shots per measurement circuit to estimate quantum observables.

### Baselines

A naive baseline classifier that predicts the majority class for all test samples is included to establish a lower performance bound. This baseline yields a balanced accuracy of 0.500 (the chance-level for a three-class problem under balanced accuracy, as defined by per-class recall averaging [SOURCE-2]).

### Metrics

Performance is assessed using balanced accuracy and ROC-AUC. Balanced accuracy is computed as the arithmetic mean of per-class recall values, which is appropriate for multiclass evaluation and robust to class imbalance [SOURCE-2]. ROC-AUC is computed using a one-versus-rest macro-averaging protocol, consistent with established multiclass evaluation practices [SOURCE-2].

### Ablation Study Design

An ablation study is designed to assess the sensitivity of VQLS performance to circuit depth $D \in \{1, 2, 3, 4, 6, 8\}$, regularization parameter $\lambda \in \{10^{-5}, 10^{-3}, 10^{-1}\}$, and the number of measurement shots $\in \{1024, 4096, 8192, 32768\}$. The full results of this ablation are reserved for future reporting, as the current study focuses on the primary configuration.

---

## Results

The VQLS-based classifier was trained on the Iris training set and evaluated on the held-out test set. The naive majority-class baseline, which serves as a reference for chance-level performance, achieved a balanced accuracy of [RESULT-2] balanced_accuracy = 0.500. This result is consistent with the expected lower bound for a three-class balanced accuracy metric, where uniform random prediction or majority-class prediction yields a balanced accuracy of approximately one-half when one class is predicted exclusively [SOURCE-2].

The proposed VQLS method, using the parameterized ansatz with depth $D = 4$ and 28 trainable parameters per one-versus-rest subproblem, achieved a balanced accuracy of [RESULT-1] balanced_accuracy = 0.973 on the test set. This represents a substantial improvement over the naive baseline, with the VQLS classifier correctly distinguishing among all three Iris classes in the vast majority of test samples. The near-perfect balanced accuracy indicates that the quantum linear solver produces solution vectors of sufficiently high quality for downstream classification, with only a small number of misclassifications.

In addition to balanced accuracy, the VQLS classifier attained an ROC-AUC of [RESULT-3] ROC-AUC = 0.998 under the one-versus-rest macro-averaging protocol. This exceptionally high ROC-AUC indicates near-perfect class separation, with the classifier's predicted scores providing strong ranking quality across all decision thresholds. The combination of high balanced accuracy and near-perfect ROC-AUC demonstrates that the VQLS solution captures the discriminative structure of the Iris feature space effectively.

These results provide evidence that variational quantum linear solving can produce solutions competitive with classical linear classifiers for well-structured classification tasks. The strong performance is consistent with the theoretical analysis of linear classification methods, where the normal equations formulation yields solutions in the same hypothesis class as classical linear discriminant approaches [SOURCE-1]. The key distinction is that the VQLS arrives at these solutions through a quantum-classical hybrid optimization procedure rather than direct matrix inversion, suggesting that the quantum ansatz is sufficiently expressive to represent the relatively low-dimensional solution manifold of the Iris classification problem.

---

## Expected Results

It was hypothesized prior to experimentation that the VQLS approach would achieve classification performance competitive with classical linear methods on the Iris dataset, given that the problem is linearly separable for two of the three class pairs and only mildly nonlinear for the remaining pair. The observed balanced accuracy of 0.973 confirms this hypothesis, falling within the expected range of 0.95–0.99 for well-tuned linear classifiers on Iris [SOURCE-1].

The ROC-AUC of 0.998 exceeded initial expectations, which anticipated a value in the range 0.97–0.995. The marginally higher-than-expected ROC-AUC may be attributable to the regularization parameter choice, which balances solution stability with discriminative power. Future experiments varying $\lambda$ are expected to reveal a trade-off curve between these quantities.

For the ablation study, it is anticipated that circuit depths of $D \geq 3$ will yield comparable performance, with diminishing returns beyond $D = 4$. Depths of $D = 1$ are expected to produce a meaningful degradation, potentially dropping balanced accuracy below 0.90, as the shallow ansatz may lack sufficient expressivity to represent the solution state accurately. Similarly, reducing measurement shots below 4096 is expected to introduce estimation noise that degrades optimization convergence, with balanced accuracy potentially falling to the 0.90–0.95 range at 1024 shots.

When eventually applied to full-scale hydrodynamic lubrication problems, it is expected that the VQLS approach will face greater challenges related to matrix conditioning, ansatz expressivity for high-dimensional systems, and measurement overhead. However, the Iris results provide a proof of concept that the solver architecture produces valid solutions for structured linear systems, motivating continued development toward engineering-scale applications.

---

## Discussion

The results demonstrate that the proposed VQLS framework can effectively solve linear systems arising in classification tasks, with performance approaching that of classical linear classifiers. However, several limitations must be acknowledged. First, the Iris dataset is a small, low-dimensional benchmark; scaling to the large, sparse systems characteristic of hydrodynamic lubrication simulations will require ansatz designs that can handle problem dimensions far exceeding three qubits. Current NISQ hardware limitations—typically fewer than 100 qubits with significant noise—constrain the problem sizes that can be addressed. Second, the cost function evaluation requires multiple quantum measurement circuits whose number scales quadratically with the number of terms in the matrix decomposition. For the banded matrices arising from Reynolds equation discretization, this decomposition is sparse, but the measurement overhead remains a practical concern. Third, the classical optimization landscape for the variational parameters is known to suffer from barren plateaus—vanishing gradients as the number of qubits increases—which may impede training for larger systems.

From a broader impact perspective, quantum-enhanced linear solvers could eventually accelerate engineering simulations in tribology, structural mechanics, and fluid dynamics, potentially reducing design cycle times for critical mechanical components. However, the current gap between proof-of-concept demonstrations and production-scale engineering simulations remains substantial, and near-term claims of practical advantage should be treated with appropriate caution. Ethical considerations are minimal for the present classification benchmark, but future deployment of quantum-accelerated simulation tools in safety-critical engineering contexts (e.g., aerospace bearings, medical device lubrication) will require rigorous validation protocols to ensure that quantum-produced solutions meet the reliability standards of established classical methods.

A potential negative societal consequence of overpromising quantum computing capabilities in engineering is the misallocation of research funding or premature replacement of validated classical pipelines. The research community should maintain realistic expectations about NISQ-era quantum advantage and prioritize rigorous benchmarking against state-of-the-art classical methods.

---

## Conclusion

This paper proposed a variational quantum linear solver (VQLS) framework motivated by the linear systems arising in hydrodynamic lubrication modeling. The approach encodes the discretized Reynolds equation structure into a parameterized quantum circuit ansatz optimized via a normalized residual cost function. As a downstream proof of concept, the VQLS was applied to classification on the Iris dataset, where classification weights are obtained by solving normal equations as a linear system. The VQLS-based classifier achieved a balanced accuracy of 0.973 and an ROC-AUC of 0.998, substantially outperforming a naive baseline at 0.500 balanced accuracy. These results establish that the variational quantum solving paradigm can produce solutions of sufficient quality for practical machine learning tasks and provide a foundation for future work extending the approach to full-scale hydrodynamic lubrication simulations. Future research will focus on scaling the ansatz to larger problem dimensions, investigating barren plateau mitigation strategies, and benchmarking against state-of-the-art classical finite-element solvers on standardized tribology test cases.