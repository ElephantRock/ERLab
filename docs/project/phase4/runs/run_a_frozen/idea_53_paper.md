This paper presents IntrinsicProv, a novel neuro-symbolic framework designed to embed explainability directly into the diagnostic reasoning process. By integrating a symbolic logic layer that constrains the neural generation path, IntrinsicProv mandates the retrieval and verification of intermediate evidence from a medical Knowledge Graph (KG) before a diagnosis can be output.  We formalize the framework as a constrained optimization problem where the likelihood of a generated token is conditioned upon its logical consistency with ontological facts. Through a proposed evaluation on multi-modal oncology datasets, we demonstrate that IntrinsicProv is expected to significantly outperform standard LLM baselines in diagnostic accuracy while providing granular, human-interpretable provenance for every clinical decision. ## Introduction

The rapid advancement of Artificial Intelligence has catalyzed a paradigm shift in healthcare, particularly in the domain of oncology, where the complexity of multi-modal patient data necessitates sophisticated decision support systems. While deep learning architectures have achieved remarkable success in perception and pattern recognition tasks, they often fall short in providing the interpretable and structured reasoning required for clinical trust .  This limitation manifests as "hallucinations"—plausible but factually incorrect assertions—which are unacceptable in high-stakes environments such as personalized treatment recommendation [SOURCE-8].
 While early symbolic systems suffered from brittleness and poor scalability, and modern neural systems lack transparency, neuro-symbolic approaches offer a middle ground . However, existing neuro-symbolic methods often treat the symbolic and neural components as separate stages—retrieving knowledge *a priori* or post-hoc explaining the output—which fails to intrinsically constrain the generation process.  This paper proposes IntrinsicProv, a framework where the symbolic logic layer is not merely an add-on but a fundamental constraint on the neural generation path. Specifically, we require the model to retrieve intermediate evidence from a medical KG before outputting a diagnosis, thereby enforcing a chain of thought that is verifiable against clinical ontologies.

Our contributions are threefold:
1.  We introduce a constrained decoding mechanism that forces the LLM to align its generation with symbolic logic paths derived from medical ontologies.
2. 
3.  We propose a rigorous evaluation protocol to assess not only the accuracy of treatment recommendations but also the faithfulness and validity of the generated explanations.

## Related Work

### Neuro-Symbolic Integration in AI

The integration of neural and symbolic components represents a concerted effort to combine the generalization capabilities of deep learning with the interpretability of logic programming. As noted in recent historical analyses, the pursuit of Artificial General Intelligence (AGI) demands systems that can reason in a human-like manner, a feat purely neural systems struggle to achieve . [SOURCE-28] Contemporary approaches often view LLMs as "Stochastic Mimicry Engines" and propose architectures that induce System 2 reasoning—slow, logical deliberation—into these quantized models . [SOURCE-11] This aligns with the broader goal of enhancing foundation model-based reasoning through neuro-symbolic cognitive methods, which attempt to replicate human-like thought processes . [SOURCE-12] Furthermore, the concept of putting "reasons back into reasoning" emphasizes that genuine inference might be the basis of generation, a principle central to our proposed architecture [SOURCE-6].

### Knowledge Graphs and Logical Reasoning

Knowledge Graphs serve as the backbone for symbolic reasoning, providing structured representations of entities and relations.  Additionally, graph-based neuro-symbolic logic reasoning has been identified as a key method for improving AI applications by enabling the traversal of complex logical paths [SOURCE-2]. The reciprocal relationship between LLMs and KGs is well-documented, suggesting that KGs can ground LLM knowledge while LLMs can complete KGs . [SOURCE-26]

### Medical AI and Explainability

In the medical domain, the need for explainability is paramount.  In oncology specifically, knowledge-driven neuro-symbolic reasoning has been applied to personalized treatment recommendations using multi-modal medical knowledge graphs, demonstrating the viability of this hybrid approach [SOURCE-8].  However, many existing systems still rely on post-hoc explanations rather than intrinsic, embedded provability. Our work builds upon these foundations by enforcing that the explanation (the symbolic path) is a prerequisite for the conclusion (the diagnosis), rather than a retrospective justification.

## Methodology

### Problem Formulation

We define the task of personalized oncology diagnosis as a reasoning problem over a patient record $P$ and a medical Knowledge Graph $\mathcal{G}$. The patient record consists of structured data (demographics, lab results) and unstructured clinical notes. g., diseases, symptoms, drugs), relations $\mathcal{R}$ (e.g., *indicates*, *treats*, *contraindicates*), and ontological types $\mathcal{T}$ derived from medical standards [SOURCE-9].

The objective is to generate a diagnosis $D$ and a treatment plan $T$, accompanied by a proof trace $\Pi$. Standard LLMs maximize the probability $P(D, T | P)$. In contrast, IntrinsicProv maximizes the joint probability of the output and a valid logical proof path within $\mathcal{G}$:

$$ \max_{D, T, \Pi} P(D, T | P, \mathcal{G}) \quad \text{s.t.} \quad \text{Valid}(\Pi, \mathcal{G}) = \text{True} $$

Where $\text{Valid}(\Pi, \mathcal{G})$ is a symbolic verifier that ensures every step in the generation process is supported by a triple $(h, r, t) \in \mathcal{G}$ or a logical inference rule over $\mathcal{G}$.

### Architecture

The IntrinsicProv architecture consists of three primary components: the Neural Encoder, the Symbolic Logic Layer, and the Constrained Decoder.

**1.  This component handles the perception and understanding of natural language and unstructured modalities.

**2. Symbolic Logic Layer (The Constrainer):** This layer interacts with the Knowledge Graph $\mathcal{G}$. We utilize a hyperbolic graph neural network to encode the symbolic paths, leveraging the ability of hyperbolic space to represent hierarchical medical taxonomies efficiently [SOURCE-7]. Given the current state of generation (partial sequence), this layer retrieves a set of candidate reasoning paths $\mathcal{C} = \{c_1, c_2, \dots, c_k\}$ from $\mathcal{G}$ that are logically consistent with the context $H_P$.

**3. Constrained Decoder:** The decoder generates the output token-by-token. At each step $t$, the distribution over the vocabulary $V$ is modified by the Symbolic Logic Layer. Instead of sampling purely from the neural distribution $P_{neural}(y_t | y_{<t}, P)$, we compute a constrained distribution:

$$ P_{final}(y_t) = \text{Softmax}\left(\log P_{neural}(y_t) + \lambda \cdot \mathbb{I}(y_t \in \text{Entities}(\mathcal{C}))\right) $$

Here, $\mathbb{I}$ is an indicator function that boosts the probability of tokens appearing in the valid symbolic paths $\mathcal{C}$, and $\lambda$ is a hyperparameter controlling the strength of the symbolic constraint. This mechanism ensures that the generation "follows" the logic of the KG, similar to program execution for hybrid reasoning . g., TransE or RotatE) [SOURCE-16]. ### Algorithm: Logic-Guided Generation

The inference algorithm proceeds as follows:
1.  **Query Formulation:** The Neural Encoder identifies key clinical entities in $P$.
2.  **Symbolic Retrieval:** The Symbolic Logic Layer traverses $\mathcal{G}$ starting from these entities to find connected diagnostic nodes.
3.  **Path Ranking:** Candidate paths are ranked based on ontological relevance and embedding similarity.
4.  **Constrained Decoding:** The Decoder generates the diagnosis, constrained to use entities and relations found in the top-ranked paths.
5.  **Provenance Extraction:** The specific path used during generation is stored as the explanation. ## Experimental Design

### Datasets

We propose evaluating IntrinsicProv on a personalized oncology dataset, inspired by the multi-modal knowledge graphs utilized in recent treatment recommendation studies [SOURCE-8]. The dataset will consist of:
* **Synthetic Oncology Records:** Generated using LLMs to simulate diverse patient profiles while ensuring privacy, following protocols for LLM-based data synthesis [SOURCE-24].
* **Real-World De-identified Data:** If available, de-identified clinical notes from public oncology corpora.
* **Medical Knowledge Graph:** We will construct a KG using established medical ontologies (e.g., SNOMED CT, DrugBank) and literature-derived relationships, incorporating ontology to enhance reasoning [SOURCE-4].

### Baselines

We will compare IntrinsicProv against the following state-of-the-art baselines:
1.  **Standard LLM:** A generative model (e.g., GPT-4 or LLaMA) prompted with few-shot examples for diagnosis without explicit symbolic grounding.
2.  **Retrieval-Augmented Generation (RAG):** An LLM augmented with a standard retrieval mechanism (dense vector search) over medical literature, lacking the explicit symbolic constraint layer.
3.  **Pure Symbolic Reasoner:** A logic programming system (e.g., Prolog based) operating on the KG, to test the upper bound of logical consistency but potentially lower linguistic fluency.
4.  **HyperKGR:** A hyperbolic knowledge graph reasoning method used for link prediction tasks, adapted for diagnosis classification [SOURCE-7].

### Metrics

Evaluation will focus on two dimensions:
1.  **Task Performance:** Accuracy, F1-score, and BLEU/ROUGE for the generated treatment plans against the ground truth.
2.  **Explainability and Faithfulness:** * **Hallucination Rate:** The percentage of generated statements that cannot be verified in $\mathcal{G}$. * **Proof Validity:** The percentage of generated outputs where the accompanying proof trace $\Pi$ is logically sound (derivable from $\mathcal{G}$). * **Entailment Tree Accuracy:** Measuring the structural validity of the reasoning tree, similar to metrics used in multimodal entailment tasks [SOURCE-14].

### Ablation Study

To understand the contribution of individual components, we will conduct ablation studies by:
* Removing the hyperbolic embedding and using standard Euclidean space for the KG [SOURCE-7].
* Setting $\lambda = 0$ to remove the symbolic constraint during decoding.
* Removing the consistency loss $\mathcal{L}_{consistency}$ from the training objective.

## Expected Results

We hypothesize that IntrinsicProv will significantly outperform standard LLM and RAG baselines in terms of factual accuracy and hallucination reduction. Quantitatively, we expect a 10-15% improvement in diagnostic accuracy on complex cases requiring multi-hop reasoning (e.g., ruling out contraindications) compared to unconstrained LLMs. Furthermore, we anticipate that the "Proof Validity" metric will be substantially higher, approaching the performance of pure symbolic reasoners while maintaining the fluency of neural models.

Qualitatively, the outputs of IntrinsicProv should provide distinct advantages in clinical utility. Unlike standard LLMs which may provide a generic explanation, IntrinsicProv may produce a traceable chain of evidence—e.g., *“Drug A is recommended because Symptom X implies Disease Y, and Disease Y is treated by Drug A, provided Patient Z does not have Condition C.”* This level of granularity aligns with the goals of neuro-symbolic program generation, where the execution trace is as important as the result [SOURCE-13]. We also expect that the use of hyperbolic embeddings [SOURCE-7] may improve the handling of hierarchical medical classifications (e.g., differentiating between specific types of lymphoma) compared to standard graph embeddings.

## Discussion

### Limitations

While IntrinsicProv offers a robust framework for embedded explainability, it is not without limitations. The performance of the system is intrinsically bounded by the completeness and accuracy of the underlying Knowledge Graph $\mathcal{G}$.  Furthermore, the computational overhead of traversing the graph and enforcing constraints at every decoding step may increase inference latency compared to standard generation, potentially limiting real-time applications without hardware acceleration.

### Broader Impact and Ethical Considerations

The integration of AI into clinical decision support raises significant ethical questions.  However, there is a risk of automation bias, where clinicians may over-rely on the system's seemingly logical proofs without critical scrutiny. It is crucial to emphasize that the system acts as a support tool, not a replacement for human judgment.

Moreover, the use of LLMs in healthcare necessitates careful consideration of data privacy and bias. While our use of a symbolic logic layer mitigates some hallucinations, biases present in the training data of the neural encoder or the construction of the KG could propagate into the recommendations.  The framework of "Cognitive State Engineering" might be applied responsibly to ensure that the reasoning states induced in the model align with ethical medical practices [SOURCE-20].

### Potential Negative Consequences

A potential negative consequence is the rigidity introduced by symbolic constraints. In cases where clinical guidelines are ambiguous or rapidly evolving (e.g., experimental oncology trials), a hard constraint based on existing ontologies might prevent the model from suggesting innovative or off-label treatments that a human doctor might consider. Balancing the safety of constraint-based reasoning with the flexibility required for edge-case clinical scenarios remains a challenge for future research.

## Conclusion

This paper presents IntrinsicProv, a novel neuro-symbolic framework designed to bring genuine, inference-based reasoning to large language models in the context of oncology. By embedding a symbolic logic layer that constrains the neural generation path through mandatory Knowledge Graph retrieval, we address the critical limitations of current LLMs regarding hallucinations and lack of interpretability. The formalization of our constrained decoding objective and the proposed evaluation protocol provide a pathway toward more reliable and trustworthy AI in healthcare.

The expected results suggest that enforcing logical consistency does not come at the cost of fluency, but rather enhances the factual accuracy of the generated diagnoses. Future work will focus on scaling the Knowledge Graph coverage to include rare diseases and optimizing the inference speed for clinical deployment.