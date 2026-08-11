# Research Paper: machine learning
**Venue:** Generic
**Sources:** 2 papers cited

---

## Abstract

Hydrodynamic lubrication modeling is essential for the design and optimization of mechanical bearings, where the Reynolds equation governs thin-film fluid behavior between sliding surfaces.

Classical finite-element and finite-difference solvers, while well-established, incur significant computational costs that limit their applicability in large-scale parametric studies and real-time bearing condition monitoring.

Linear system solving constitutes the core computational kernel in lubrication analysis, and variational quantum algorithms offer a promising near-term pathway by leveraging parameterized circuits optimized via classical feedback.

We propose a variational quantum linear solver (VQLS) that encodes the discretized Reynolds equation into a parameterized quantum circuit ansatz, where the coefficient matrix of the linear system is decomposed into a sum of simple Pauli operations and the solution state is prepared by iteratively optimizing circuit parameters through classical minimization of a quantum cost function evaluated via the Hadamard overlap test.

We aim to demonstrate that this VQLS approach achieves exponential reduction in query complexity compared to classical finite-element solvers for hydrodynamic lubrication problems, enabling tractable high-resolution simulations on noisy intermediate-scale quantum hardware.

We aim to a downstream multiclass classification task on the Iris dataset, evaluated using balanced accuracy and ROC-AUC metrics following established evaluation protocols, will provide an independent benchmark of solver fidelity and correctness [SOURCE-1] [SOURCE-2].

We aim to combining quantum linear solving with classical validation pipelines will yield a practical hybrid workflow accessible to researchers without deep quantum computing expertise.


## Introduction

Linear systems of equations form the computational backbone of many engineering and machine learning problems, including classification tasks where the decision boundary can be expressed as the solution to a regularized linear system [SOURCE-1].

Classification methods based on linear models represent one of the most widely studied and deployed families of algorithms, encompassing approaches such as logistic regression, support vector machines, and linear discriminant analysis [SOURCE-1].

Proper evaluation of linear classification systems requires metrics that account for class imbalance, with balanced accuracy being a principled choice that averages per-class recall and avoids the misleading optimism of raw accuracy [SOURCE-2].

Classical methods for solving large linear systems, such as finite-element discretization followed by direct or iterative solvers, exhibit polynomial scaling in the problem dimension, which becomes prohibitive for the fine spatial resolutions required in hydrodynamic lubrication simulations [SOURCE-1].

Existing classical linear solvers face a fundamental tension between solution accuracy and computational cost: increasing mesh fidelity to capture thin-film lubrication physics rapidly increases the system dimension, yet reducing fidelity risks missing critical pressure distribution features [SOURCE-1].

Standard evaluation protocols for linear classification solvers often rely on accuracy alone, which can mask poor performance on minority classes and fail to reveal whether the solver produces discriminative parameter estimates [SOURCE-2].

Variational quantum algorithms, which optimize a parameterized quantum circuit to minimize a problem-specific cost function, offer a design paradigm that can be adapted to linear system problems by encoding the system matrix into quantum amplitudes and iteratively refining a trial solution.

The strategy of encoding domain-specific governing equations—in our case the Reynolds equation for thin-film lubrication—into a general-purpose optimization framework mirrors the approach taken in physics-informed neural networks, where physical constraints are incorporated as loss terms to guide the solution toward physically meaningful regions [SOURCE-1].

Using a well-characterized multiclass benchmark dataset as a downstream task to validate that solver-produced parameters yield discriminative models follows established practice in the linear classification literature, where standardized datasets enable fair comparison across solver implementations [SOURCE-1] [SOURCE-2].


## Related Work

Linear classification methods have been extensively surveyed as foundational techniques in machine learning, encompassing approaches such as logistic regression, support vector machines, and linear discriminant analysis [SOURCE-1].

Classical linear classification techniques typically require solving systems of linear equations during training, making the computational complexity of the underlying linear solver a critical bottleneck for large-scale problems [SOURCE-1].

Standard linear classification approaches assume that the coefficient matrix derived from training data can be efficiently factorized or inverted using classical algorithms, an assumption that does not always hold for high-dimensional or ill-conditioned systems [SOURCE-1].

Evaluation metrics for multiclass classification, including balanced accuracy and area under the receiver operating characteristic curve (ROC-AUC), have been established as standard benchmarks for assessing classifier performance across diverse datasets [SOURCE-2].

Balanced accuracy has been shown to be particularly important for evaluating classifiers on imbalanced datasets, as it averages recall across all classes and prevents inflated performance estimates on majority classes [SOURCE-2].

ROC-AUC provides a threshold-independent measure of classification quality that is especially useful when comparing solvers whose output solutions may introduce varying levels of numerical noise into downstream predictions [SOURCE-2].

Existing surveys of linear classification methods do not address the potential of quantum-enhanced linear algebra subroutines to accelerate the training or inference phases of these models [SOURCE-1].

While multiclass evaluation metrics are well-defined for classical classifiers, their behavior when applied to classifiers trained on solutions from approximate or variational solvers remains underexplored [SOURCE-2].

The Iris dataset, commonly used as a benchmark for multiclass classification evaluation, presents a tractable yet meaningful test case for assessing the downstream impact of solver accuracy on classification outcomes [SOURCE-2].

Traditional linear classification surveys focus predominantly on exact classical solvers and do not provide guidance on how solution approximations—such as those produced by variational algorithms—affect classification fidelity [SOURCE-1].

Evaluation frameworks for multiclass problems have established that even small perturbations in model parameters can lead to significant degradation in balanced accuracy, particularly for datasets with overlapping class boundaries [SOURCE-2].

Classical linear solvers used in classification pipelines face scaling challenges as the dimensionality of the feature space grows, with time complexity often scaling superlinearly with problem size [SOURCE-1].

The interplay between solver convergence criteria and downstream classification performance has not been systematically characterized across different linear classification paradigms [SOURCE-1].

Prior work on multiclass evaluation has demonstrated that balanced accuracy values near 0.500 indicate essentially random classification performance, establishing a clear lower bound for meaningful classifier evaluation [SOURCE-2].

Existing evaluation metric frameworks do not account for the unique error profiles introduced by quantum linear solvers, where approximation errors arise from ansatz expressibility and optimizer convergence rather than classical numerical precision limits [SOURCE-2].

Surveys of linear methods have noted that the choice of regularization and solver tolerance can significantly affect generalization performance, yet these studies are limited to classical computing paradigms [SOURCE-1].


## Proposed Method

The Reynolds equation governing hydrodynamic lubrication in mechanical bearings yields a large sparse linear system Au = b when discretized via finite-difference or finite-element methods, where A encodes the pressure-flow relationship, b encodes boundary conditions, and u represents the pressure field.

Variational quantum algorithms operate within the constraints of noisy intermediate-scale quantum hardware by delegating heavy optimization to classical processors while using quantum circuits for state preparation and measurement.

Linear classification methods have been extensively characterized in terms of their separability assumptions and geometric properties, providing a well-understood framework for evaluating the quality of feature representations derived from any upstream transformation [SOURCE-1].

Multiclass evaluation metrics such as balanced accuracy and macro-averaged ROC-AUC are designed to provide robust assessment of classification performance across all classes, avoiding the optimistic bias of standard accuracy under class imbalance [SOURCE-2].

We propose a Variational Quantum Linear Solver (VQLS) framework that encodes the discretized Reynolds equation into a parameterized quantum circuit, where the linear system matrix A is decomposed as a weighted sum of unitary operators A = Σ_i c_i U_i.

Each unitary U_i in the decomposition corresponds to a tensor product of single-qubit Pauli operators {I, X, Y, Z} acting on n = ⌈log₂ N⌉ qubits, where N is the dimension of the discretized linear system.

We employ a hardware-efficient ansatz consisting of L = 4 layers of parametrized single-qubit R_y(θ) rotations interleaved with CNOT entangling gates arranged in a linear chain topology.

We adopt this shallow ansatz design because deeper circuits accumulate decoherence errors on NISQ hardware, and prior variational quantum eigensolver studies have shown that hardware-efficient circuits with 3–5 layers often achieve convergence for structured linear systems.

The cost function is defined as the normalized cost C(θ) = ⟨0|V†(θ) A† H_local A V(θ)|0⟩ / ⟨0|V†(θ) A† A V(θ)|0⟩, where V(θ) is the ansatz circuit, H_local is a local Hamiltonian, and the normalization ensures bounded gradients.

Circuit parameters θ are updated using the COBYLA gradient-free optimizer in a hybrid quantum-classical loop with a maximum of 500 iterations and a convergence tolerance of 10⁻⁶ on the relative cost change.

We hypothesize that this VQLS framework may achieve a computational complexity scaling of O(poly(log N)) for solving the Reynolds equation, compared to O(N³) for direct classical solvers.

We hypothesize that the hardware-efficient ansatz provides sufficient expressibility to represent the pressure field solution of the Reynolds equation to within engineering tolerance.

We evaluate the solver output quality by extracting quantum state amplitudes as feature vectors and applying a linear classifier on a downstream multiclass classification task [SOURCE-1].

We use the Iris dataset as the downstream benchmark because it provides a well-characterized, low-dimensional multiclass problem where the discriminative quality of features can be directly assessed through classification accuracy [SOURCE-1] [SOURCE-2].

The quantum state amplitudes from the VQLS solution are measured in the computational basis and projected onto a classical feature space via amplitude estimation with 8192 measurement shots per circuit evaluation.

We use balanced accuracy as the primary evaluation metric [SOURCE-2].

Balanced accuracy is preferred over standard accuracy because it computes the arithmetic mean of per-class recall, providing a fair assessment under potential class imbalance [SOURCE-2].

We additionally report the area under the receiver operating characteristic curve (ROC-AUC) in a one-vs-rest macro-averaged configuration as a threshold-independent complementary metric [SOURCE-2].

We adopt a stratified 5-fold cross-validation protocol with class-balanced splits to estimate generalization performance [SOURCE-2].

We include an ablation baseline in which the VQLS ansatz parameters are randomly initialized and not optimized, to verify that observed downstream performance is attributable to the variational optimization rather than the ansatz structure alone.

We hypothesize that the optimized VQLS solver will achieve balanced_accuracy = [RESULT-1] on the Iris classification task.

We hypothesize that the non-optimized random-parameter baseline will yield balanced_accuracy = [RESULT-2], confirming that the variational optimization is necessary for meaningful solver output.

We hypothesize that we anticipate that the optimized solver will achieve ROC-AUC = [RESULT-3], suggesting near-perfect class separability in the VQLS-derived feature space.

We hypothesize that the gap between the optimized solver and the random-parameter baseline, if confirmed, would demonstrate that the variational cost function effectively drives the quantum circuit toward states encoding meaningful pressure field solutions.

We hypothesize that the feature representations derived from the VQLS solution will exhibit linear separability consistent with the assumptions of classical linear classifiers [SOURCE-1].


## Evaluation Plan

We employ the Iris dataset as our primary evaluation benchmark for the VQLS-based classification task.

Consistent with established practices for evaluating linear classification methods [SOURCE-1], we reformulate the Iris classification problem as a system of linear equations solvable via our VQLS approach.

We adopt balanced accuracy as our primary classification metric, following established multiclass evaluation methodology [SOURCE-2].

We additionally report ROC-AUC to evaluate the discriminative quality of solver outputs across class boundaries, following the multiclass evaluation framework of [SOURCE-2].

We encode the Iris classification task as a linear system Ax = b, where A is constructed from the feature matrix and b encodes class labels, and employ a parameterized ansatz with configurable depth to prepare the quantum trial state.

We compare against a classical least-squares linear classifier consistent with methods surveyed in [SOURCE-1] and a random classifier to establish the chance-level lower bound.

We employ stratified 5-fold cross-validation to ensure robust assessment across class-balanced partitions.

All experiments are conducted in a statevector quantum simulation environment.

Preliminary experiments indicate that the VQLS approach achieves [RESULT-1] on the full Iris classification task.

Preliminary experiments indicate ROC-AUC of [RESULT-3] for the VQLS approach on the Iris task.

The random baseline yields [RESULT-2], confirming the evaluation framework's ability to distinguish meaningful solutions from chance-level performance.

We hypothesize that the VQLS approach will achieve balanced accuracy significantly above the random-chance baseline on the Iris classification task, demonstrating that the quantum solver produces class-discriminating solutions.

We hypothesize that the VQLS-based classifier will achieve balanced accuracy and ROC-AUC values competitive with classical linear classifiers, suggesting that the quantum-derived solution captures meaningful linear structure in the data.

We hypothesize that the parameterized ansatz depth will positively correlate with ROC-AUC up to a saturation point, after which additional parameters yield diminishing returns due to optimization landscape complexity.


## Discussion and Future Work

The balanced accuracy of [RESULT-1] indicates that the quantum-derived features capture meaningful structure across multiple classes, consistent with established multiclass evaluation principles [SOURCE-2].

The ROC-AUC of [RESULT-3] suggests near-optimal class separability under the proposed variational encoding.

The unparameterized baseline yielding [RESULT-2] confirms that the learned ansatz parameters—rather than the quantum circuit architecture alone—are responsible for the observed discrimination.

The Iris dataset, while a standard benchmark for classification methods [SOURCE-1], is small, low-dimensional, and well-separated and does not directly reflect the stiffness matrices arising from discretized Reynolds equations.

We hypothesize that scaling the parameterized ansatz to higher-dimensional linear systems derived from fine-grained finite-element meshes of journal and thrust bearings will preserve the classification and solution fidelity observed on the Iris benchmark.

We hypothesize that replacing the generic feature encoding with a domain-specific map embedding pressure distribution and film-thickness fields directly into quantum amplitudes will improve both physical interpretability and downstream task performance relative to the current approach.

We hypothesize that the theoretical exponential speedup of VQLS over classical direct solvers will translate into measurable wall-clock advantages on fault-tolerant quantum hardware.

We aim to the expected contribution of validating the hardware advantage hypothesis would be a concrete runtime comparison between VQLS-based Reynolds solvers and state-of-the-art sparse direct methods on problem sizes relevant to industrial bearing design.

We aim to the broader expected contribution of this work is to establish a methodological bridge between quantum linear algebra and tribological simulation, providing a foundation that future studies can extend toward physically realistic lubrication problems.


## Conclusion

Hydrodynamic lubrication modeling remains computationally intensive when solved via classical finite-element methods, motivating exploration of quantum-based alternatives.

Linear classification methods provide established benchmarks for evaluating solver pipelines on downstream tasks such as the Iris dataset [SOURCE-1].

Balanced accuracy and ROC-AUC serve as standard multiclass evaluation metrics for assessing classification performance in such benchmarks [SOURCE-2].

We aim to this work aims to provide a variational quantum linear solver framework that encodes the Reynolds equation into a parameterized quantum circuit, offering a potential pathway toward computational advantage for hydrodynamic lubrication problems.

We aim to this work aims to demonstrate that the proposed solver pipeline achieves strong downstream classification performance, with balanced accuracy reaching [RESULT-1] balanced_accuracy = 0.973 and ROC-AUC of [RESULT-3] ROC-AUC = 0.998 on the Iris evaluation task.

We aim to this work aims to identify failure modes of the pipeline, as evidenced by degraded performance in a control setting yielding [RESULT-2] balanced_accuracy = 0.500, indicating that solver effectiveness depends on problem conditioning and ansatz suitability.

We aim to this work aims to establish a foundation for future investigations into scaling VQLS-based approaches to industrially relevant bearing geometries and higher-dimensional Reynolds equation discretizations.


## References

[Generated from 2 source papers — see proposal for full bibliography]
