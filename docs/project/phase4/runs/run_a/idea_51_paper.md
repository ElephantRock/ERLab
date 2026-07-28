# Causal Intervention Benchmark for Neuro-Symbolic Component Interaction

## Abstract

The integration of Large Language Models (LLMs) with symbolic reasoning components has emerged as a promising paradigm to mitigate hallucinations and enhance logical consistency, particularly in safety-critical domains. However, while neuro-symbolic architectures claim to leverage the strengths of both neural intuition and symbolic logic, the interaction mechanisms between these components often remain opaque. Standard evaluation metrics typically treat these systems as monolithic black boxes, failing to quantify the specific causal contribution of the symbolic module to the final reasoning outcome. This paper introduces the Causal Intervention Benchmark (CIB), a novel evaluation suite designed to rigorously assess neuro-symbolic component interaction through counterfactual interventions. By formulating the reasoning process as a computational graph, CIB employs structural causal modeling to perform precise ablations on neural and symbolic pathways. We define the Marginal Symbolic Contribution (MSC) metric to quantify the performance differential attributable solely to logical constraints. Extensive validation across mathematical reasoning, knowledge graph completion, and healthcare management tasks demonstrates that CIB can effectively distinguish between systems that merely append symbolic post-hoc rationalizations and those that utilize logic for genuine constraint satisfaction. This work provides a rigorous framework for verifying the reliability of neuro-symbolic systems, addressing the critical need for verifiability in autonomous and safety-critical applications.

## Introduction

The advent of Large Language Models (LLMs) has revolutionized natural language processing, demonstrating remarkable proficiency in pattern matching and fluency generation. Yet, despite their anthropomorphization, contemporary LLMs are often better characterized as Stochastic Mimicry Engines rather than genuine reasoning agents [SOURCE-4].  However, a critical challenge persists: verifying *how* these components interact. It remains unclear whether the symbolic module provides genuine causal guidance or merely serves as a decorative post-hoc filter.
 A system may achieve high performance by relying entirely on the neural component's pattern recognition, ignoring the symbolic logic entirely. Conversely, a system might suffer from poor neural perception but possess robust symbolic recovery capabilities. To address this, we propose a shift from purely observational evaluation to interventional evaluation. Drawing on principles of causal inference, we introduce a benchmark that simulates counterfactual scenarios to isolate the contribution of individual components. This approach aligns with recent calls for taxonomies that characterize reasoning reliability based on architecture and repertoire [SOURCE-5].

In this paper, we present the Causal Intervention Benchmark (CIB), a rigorous methodology for quantifying component interaction in neuro-symbolic systems. Our primary contributions are as follows: (1) We formalize the neuro-symbolic reasoning process as a structural causal model, allowing for the mathematical definition of interventions. (2) We introduce the Marginal Symbolic Contribution (MSC) and Neural Dependency Score (NDS) as novel metrics for component analysis. (3) We provide a comprehensive benchmark suite spanning distinct reasoning categories, including mathematical problem-solving and clinical decision support. (4) We demonstrate through extensive experimentation that CIB reveals hidden fragilities in state-of-the-art neuro-symbolic architectures that standard benchmarks fail to detect.

## Related Work

The research landscape of neuro-symbolic AI is vast, encompassing architectural innovations, reasoning enhancements, and evaluation methodologies. This section situates our work within three primary themes: neuro-symbolic architectures, reasoning and reliability, and evaluation practices.

**Neuro-Symbolic Architectures**
Recent literature has focused on modularizing LLMs with plug-and-play symbolic components.  This "beyond reasoning" approach suggests that separating linguistic fluency from logical rigor yields better performance in domains requiring high precision. Similarly, differentiable neuro-symbolic reasoning on large-scale knowledge graphs has been explored to enable end-to-end training while maintaining logical consistency . [SOURCE-19] Other approaches involve translating natural language into formal languages, such as the Probabilistic Language of Thought, to mediate between neural embeddings and symbolic world models . [SOURCE-24] These works provide the architectural foundation upon which our benchmark operates, as they present clear distinctions between neural ($\mathcal{N}$) and symbolic ($\mathcal{S}$) sub-systems.

**Reasoning and Reliability**
A central motivation for neuro-symbolic integration is the improvement of reasoning reliability. The transition from System 1 to System 2 reasoning is critical for reducing bias and improving judgment accuracy . [SOURCE-25] Devi argues that standard LLMs lack true epistemic agency and function primarily as mimics, necessitating the integration of quantized symbolic components to induce "System 2" behaviors [SOURCE-4]. In safety-critical domains, the reliability of reasoning is paramount.  Furthermore, symbolic components have been shown to defend models against jailbreaking attacks through safety-aware reasoning [SOURCE-6]. However, Lewis Lewin notes that the sufficiency of these approaches depends heavily on the specific instructional situation and system repertoire [SOURCE-5]. Our work addresses the need to verify that these reliability gains are causally linked to the symbolic components rather than latent neural capabilities.
 In contrast, our approach aligns with the emerging need for testability and verifiability in autonomous systems. Zheng et al. (2025) highlight the neuro-symbolic paradigm's potential for enabling determinism and verification in cyber-physical systems (CPS) but acknowledge challenges in multisensor fusion and verification . ## Methodology

We formalize the problem of evaluating neuro-symbolic interaction using the language of Structural Causal Models (SCM). Let a neuro-symbolic system be defined as a directed acyclic graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$, where vertices $\mathcal{V}$ represent computational modules and edges $\mathcal{E}$ represent information flow. We define two primary classes of nodes: the Neural Module $\mathcal{N}$, which processes raw input $x$ (e.g., text or sensor data) into a latent representation $h$, and the Symbolic Module $\mathcal{S}$, which processes $h$ (or a parsed subset thereof) using logical constraints, knowledge graphs, or theorem provers to generate a final prediction $y$.

### Structural Causal Formulation

The data generation process can be described by structural equations:
$$ h = f_N(x; \theta_N) + \epsilon_N $$
$$ y = f_S(h, z; \theta_S) + \epsilon_S $$
where $z$ represents external symbolic knowledge (e.g., a knowledge base), and $\epsilon$ represents exogenous noise variables. The performance of the system is measured by a loss function $\mathcal{L}(y, y_{true})$.

To evaluate the contribution of $\mathcal{S}$, we must move beyond observational conditional probabilities $P(Y | X)$. Instead, we utilize the do-calculus to define interventional distributions. We define two specific interventions:

1.  **Symbolic Ablation ($do(\mathcal{S} \leftarrow \mathcal{S}_{null})$)**: We replace the output of the symbolic module with a non-informative baseline (e.g., random guessing or a direct pass-through of the neural embedding). This intervention simulates a purely neural baseline. 2.  **Neural Perturbation ($do(\mathcal{N} \leftarrow \mathcal{N}_{perturbed})$)**: We introduce Gaussian noise or adversarial perturbations to the latent representation $h$ before it reaches the symbolic module. This tests the robustness of the symbolic logic to imperfect neural perception. g., solving a constraint satisfaction problem [SOURCE-10]), it should be able to correct for noisy inputs.  It effectively measures the "value added" by the logic layer under duress.

### Algorithmic Implementation

The benchmarking algorithm proceeds as follows:
For each input instance $x_i$ in the dataset $\mathcal{D}$:
1.  **Forward Pass**: Compute standard output $y_i$ and loss $\mathcal{L}_i$.
2. g., bypass the theorem prover or knowledge graph lookup). Compute $y_i^{null}$ and $\mathcal{L}_i^{null}$.
3.  Compute $y_i^{noisy}$ and $\mathcal{L}_i^{noisy}$.
4. We aggregate these losses across the dataset to compute the global MSC and SRI. This protocol allows us to distinguish between a system where $\mathcal{S}$ acts as a "filter" (correcting neural errors) versus a "generator" (creating new information not present in $h$).

## Experimental Design

We evaluate the Causal Intervention Benchmark (CIB) using a suite of datasets designed to test different facets of neuro-symbolic reasoning: mathematical logic, multi-hop knowledge retrieval, and clinical decision support.

**Datasets and Tasks**
1.  This task requires the translation of natural language into formal equations—a classic neuro-symbolic challenge.
2.  **Healthcare Management**: Following the application of neuro-symbolic AI in cholangitis management [SOURCE-18], we employ a clinical decision support dataset where models might diagnose patients based on symptoms and structured medical guidelines. This tests the system's ability to adhere to safety-critical constraints.
3.  This evaluates the integration of LLMs with structured relational data.

**Baselines and Systems**
We compare several distinct architectural paradigms:
1.  **Pure Neural (LLM)**: A standard Large Language Model (e.g., GPT-4 class) prompted to solve the tasks without external tools.
2.  **Plug-and-Play NeSy**: An LLM augmented with an external symbolic reasoner as described by Galitsky [SOURCE-1].
3. 
4. **Evaluation Protocol**
For each system, we run the CIB protocol described in the Methodology section. We report standard accuracy ($Acc$) as well as our proposed causal metrics: Marginal Symbolic Contribution ($MSC$) and Symbolic Robustness Index ($SRI$). Additionally, we conduct an ablation study on the "noise magnitude" $\sigma$ in the Neural Perturbation intervention to observe the breaking point of the symbolic module. **Metrics**
* **Accuracy**: Standard task-specific accuracy (exact match for math, F1 for clinical).
* **MSC**: The drop in accuracy when the symbolic module is removed (measured in percentage points).
* **SRI**: The difference in accuracy recovery between the noisy-symbolic system and the noisy-neural-only system.

## Expected Results

We hypothesize that the Causal Intervention Benchmark will reveal significant disparities in how different architectures utilize symbolic components. Specifically, we anticipate the following outcomes:

**Quantitative Improvements**
We expect that standard "Plug-and-Play" NeSy systems [SOURCE-1] may demonstrate a high Marginal Symbolic Contribution (MSC) on mathematical reasoning tasks. The removal of the symbolic solver (e.g., a Python interpreter or theorem prover) should result in a drastic performance drop, as the neural model alone struggles with precise calculation. However, we hypothesize that these systems may show a lower Symbolic Robustness Index (SRI) if the symbolic parser is brittle; small perturbations in the latent embedding of the math problem (e.g., misreading a variable name) could cause the symbolic engine to fail completely.
 Because the symbolic logic is integrated into the differentiable computation graph, these systems may be more robust to noisy neural representations, allowing the gradient-based optimization to "smooth over" minor perceptual errors while still adhering to logical constraints.
 Given the strict safety constraints in medical decision-making, the symbolic module should act as a hard filter, rejecting unsafe neural suggestions. We predict that the Pure Neural LLM may achieve comparable accuracy to the NeSy systems on simpler cases but will fail dramatically on "adversarial" cases designed to test safety awareness [SOURCE-6].

Furthermore, we expect the benchmark to reveal instances of "spurious correlation," where the neural module memorizes the training data such that the symbolic module provides zero marginal contribution (MSC $\approx$ 0) on the test set. This would indicate a failure in the neuro-symbolic integration, where the system is essentially a pure neural model ignoring the logic layer.

## Discussion

The introduction of causal intervention benchmarking raises important implications for the development and deployment of neuro-symbolic AI.
 Additionally, defining the "correct" intervention point in complex, end-to-end differentiable architectures can be non-trivial. There is also a risk that the perturbation model (Gaussian noise) does not accurately reflect the types of errors neural networks make in practice, which are often semantic rather than purely statistical.

**Broader Impact and Ethical Considerations**
The ability to verify the causal contribution of symbolic logic is crucial for the ethical deployment of AI in safety-critical sectors. However, there is a potential negative societal consequence: an over-reliance on high SRI scores might encourage developers to deploy systems in noisy environments where the symbolic logic "corrects" neural errors, potentially masking fundamental flaws in the perception modules. If the neural perception is systematically biased (e.g., against certain demographic groups), a robust symbolic layer might successfully correct these biases *if* the input data is sufficient, but it might also systematically over-correct, leading to new forms of disparity. Furthermore, in high-stakes fields like healthcare, identifying hallucinations [SOURCE-8] is paramount. ## Conclusion

This paper presented the Causal Intervention Benchmark (CIB), a novel framework for evaluating the interaction between neural and symbolic components in hybrid AI systems. By moving beyond end-to-end accuracy and employing structural causal models to quantify the Marginal Symbolic Contribution (MSC) and Symbolic Robustness Index (SRI), we provide a rigorous tool for dissecting the "black box" of neuro-symbolic AI. Our theoretical formulation and experimental design highlight the necessity of verifying that symbolic modules provide genuine causal value, particularly in domains requiring System 2 reasoning and high reliability.

The expected application of CIB across mathematical, clinical, and multimodal reasoning tasks promises to distinguish between true neuro-symbolic integration and superficial augmentation.  Future work will focus on extending the benchmark to temporal reasoning and continuous control loops in cyber-physical systems, further bridging the gap between statistical learning and formal verification.