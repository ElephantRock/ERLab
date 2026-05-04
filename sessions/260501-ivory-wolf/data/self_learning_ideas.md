# Research Ideas Generated: AI/Self-Learning

**Pipeline Run 24** | **Domain: AI/Self-Learning** | **Date: 2026-05-04**

## Idea 1: Open-CBM: Dirichlet Process Concept Bottleneck Models with Semantic Validation for XAI in Mental Health

- **Overall Score**: 0.81
- **Novelty**: 0.86
- **Feasibility**: 7.55

### Problem Statement

Concept Bottleneck Models (CBMs) in psychological assessments force continuous, overlapping distress signals into discrete, predefined theoretical concepts, losing critical nuance. Furthermore, standard CBMs cannot detect or categorize emergent, unknown indicators of distress without forcing misclassification.

### Proposed Method

We propose Open-CBM, a Dynamic Concept Bottleneck Model strictly focused on open-vocabulary concept discovery. Alongside predefined clinical concepts, the model uses a non-parametric Dirichlet Process to cluster embedding representations of user text, automatically discovering emergent concepts (unexplained variance). To prevent semantically overlapping or nonsensical clusters, we introduce a semantic validation step where an auxiliary LLM verifies the conceptual coherence of the grouped terms before they are established as new concepts. If an emergent concept is activated during inference, the model flags it for human review, preventing forced misclassification.

### Expected Contributions

An interpretable AI framework that adapts to new, unstudied psychological phenomena rather than being constrained by existing theoretical buckets. A rigorous, semantically validated non-parametric method for expanding conceptual vocabulary in CBMs.

---

## Idea 2: CulturalAdapt-BO: Bayesian Optimization for Safe Survey Localization

- **Overall Score**: 0.79
- **Novelty**: 0.82
- **Feasibility**: 7.70

### Problem Statement

Optimizing global diagnostic surveys for specific cultural contexts is labor-intensive. Previous AI attempts to automate this risked generating leading questions that compromise validity. While RL-based approaches have been proposed, they suffer from sample inefficiency and complexity, making them impractical for real-world expert-in-the-loop survey localization.

### Proposed Method

We reframe the system as a Bayesian Optimization (BO) problem over a generative language model, drastically improving sample efficiency: (1) Diverse Simulated Initialization: LLMs parameterized with demographic personas generate an initial, diverse search space of potential question phrasings, using diversity-promoting penalties to avoid stereotypical biases. (2) Human-in-the-Loop Bayesian Optimization: A Gaussian Process (GP) surrogate model guides the selection of top-k question variants. A localized human panel reviews only the most informative variants, scoring them on cultural appropriateness, clarity, and lack of leading bias. (3) Safe Optimization via Contrastive Preference: The GP acquisition function is updated based exclusively on human feedback, explicitly penalizing semantic consistency achieved through leading questions to ensure survey validity.

### Expected Contributions

A highly sample-efficient, participatory AI tool for survey localization that minimizes expert fatigue. A novel application of Bayesian Optimization over LLMs for safe instrument generation, replacing complex RL formulations. A methodology that rigorously enforces survey validity by explicitly penalizing leading phrasing in the acquisition function.

---

## Idea 3: SocioSim-Strategic: Grounded Self-Play Multi-Agent Simulation of Historical Deliberation via Rule-Based Reward

- **Overall Score**: 0.78
- **Novelty**: 0.80
- **Feasibility**: 7.55

### Problem Statement

Simulating complex societal behaviors using LLM multi-agent self-play is highly promising for policy-making, but previous attempts lacked defined reward mechanisms and risked degenerate emergent behaviors due to LLM sycophancy. Evaluating simulation fidelity remains subjective without strict environmental constraints, and existing approaches risk overfitting to historical trajectories rather than simulating underlying strategic constraints.

### Proposed Method

We constrain the multi-agent self-play environment to a well-documented historical event (e.g., a specific UN Security Council vote). The framework consists of: (1) Persona Grounding via Constraint Satisfaction: Agents are instantiated with RAG pipelines retrieving historical mandates and strategic interests, explicitly modeling constraints rather than mimicking speech patterns. (2) Deterministic Rule-Based Reward Design: We eliminate subjective LLM judges. Instead, the reward function is a deterministic, rule-based evaluation derived directly from historical mandates (e.g., exact match on key voting outcomes, budget allocation percentages, keyword presence for policy commitments). (3) Constrained Self-Play: Agents engage in iterative debate. The reward function balances historical plausibility with strategic rationality, rewarding agents for achieving their historically-defined strategic goals regardless of whether they follow the exact historical path.

### Expected Contributions

A rigorously constrained, reward-driven multi-agent framework for societal simulation that eliminates LLM-judge subjectivity. A novel application of deterministic rule-based evaluation to define verifiable reward functions for social agents. An empirically validated methodology for testing counterfactual policy scenarios based on strategic constraints rather than historical mimicry.

---

## Idea 4: CulturalAdapt-TPE: Scalable Bayesian Optimization for Culturally Adaptive Survey Localization

- **Overall Score**: 0.78
- **Novelty**: 0.82
- **Feasibility**: 7.26

### Problem Statement

Translating and adapting global health surveys for local contexts is a manual, costly process. While RL approaches are sample-inefficient, standard Bayesian Optimization struggles with the high-dimensional, discrete combinatorial nature of text generation, risking initialization with cultural stereotypes.

### Proposed Method

We propose CulturalAdapt-TPE, a sample-efficient optimization framework using a Tree-structured Parzen Estimator (TPE) to navigate the high-dimensional discrete search space of survey item phrasing more effectively than Gaussian Processes. The LLM initialization phase includes a debiasing mechanism that enforces lexical and syntactic constraints to penalize stereotypical cultural markers. The optimization operates over specific linguistic features (e.g., formality, lexical complexity) rather than noisy raw embeddings. A human-in-the-loop panel scores a small, optimally selected batch of variants, allowing the TPE surrogate to iteratively update the cultural utility landscape.

### Expected Contributions

A highly sample-efficient, scalable method for survey localization that actively mitigates stereotyping. A practical tool for sociologists and global health workers to rapidly validate survey instruments across new cultural contexts, proven through psychometric equivalence.

---

## Idea 5: LongiSense-CDE: Integral-Gated Neural CDEs with Deep Change-Point Detection for Behavioral Shifts

- **Overall Score**: 0.77
- **Novelty**: 0.82
- **Feasibility**: 7.18

### Problem Statement

Tracking longitudinal behavioral and psychological changes requires continuous, adaptive modeling. Existing approaches lack architectural novelty tailored to irregular time-series drift detection, and defining mathematical thresholds for significant behavioral drift in high-dimensional spaces remains difficult.

### Proposed Method

We introduce LongiSense-CDE, a novel extension of Neural Controlled Differential Equations (Neural CDEs) featuring an integral-gated attention mechanism that attends to specific derivative changes and integral segments of the CDE path, avoiding O(N^2) memory bottlenecks. To formalize drift detection, we replace the univariate Page-Hinkley test with a modern, deep learning-compatible change-point detection method applied to the CDE's high-dimensional hidden states, rigorously controlling false alarm rates.

### Expected Contributions

A novel Neural CDE architecture with a structurally integrated, memory-efficient attention mechanism designed specifically for irregular time-series drift detection. A mathematically rigorous framework for detecting psychological shifts in high-dimensional representation spaces.

---

## Idea 6: Qual2Quant-Reward: Latent-Space Reward Modeling from Qualitative Codes via LLM-Driven Contrastive Generation

- **Overall Score**: 0.76
- **Novelty**: 0.82
- **Feasibility**: 7.05

### Problem Statement

Current RLHF methods rely on scalar human preference data, failing to capture the nuanced, multi-dimensional reasoning behind human choices. While qualitative data (e.g., semi-structured interview transcripts) captures this richness, directly translating it into RL reward signals lacks a mathematically rigorous formulation, risking contradictory or noisy training signals.

### Proposed Method

We propose Qual2Quant-Reward, a framework that converts qualitative interview codes into a continuous reward function using Bayesian latent variable models. First, an existing public RLHF dataset (e.g., Anthropic HH-RLHF) is retroactively mapped to qualitative codes by human experts. To generate contrastive pairs without brittle syntactic manipulations, we use a robust LLM-driven generation step that explicitly prompts the model to flip specific human values while keeping the context stable. To avoid the dimensionality curse and kernel degeneration associated with hundreds of qualitative codes, we map the codes into a dense, low-dimensional embedding space using Principal Component Analysis rather than treating each as an individual kernel parameter. Finally, a Gaussian Process (GP) operates on this latent space to predict a reward distribution, capturing human uncertainty and providing a multi-dimensional reward signal for RL fine-tuning.

### Expected Contributions

A mathematically rigorous pipeline bridging qualitative social science research with deep reinforcement learning. A novel, sample-efficient reward modeling technique that maps high-dimensional qualitative data into a continuous latent reward space, explicitly representing the uncertainty and multidimensionality of human values.

---

## Idea 7: Qual2Reward-V3: Grounded Reward Modeling from Qualitative Interviews via RAG-Augmented Coding and Hierarchical Code Aggregation

- **Overall Score**: 0.74
- **Novelty**: 0.85
- **Feasibility**: 6.35

### Problem Statement

Extracting nuanced reward signals from unstructured qualitative interview data remains a critical bottleneck for aligning AI with complex human values. Existing RLHF methods rely on simple pairwise preferences, failing to capture the depth of semi-structured sociological data. Furthermore, previous attempts to automate qualitative coding suffer from circular LLM dependencies and lack a mathematically rigorous mapping from extracted qualitative codes to scalar reward functions.

### Proposed Method

We propose a four-stage pipeline that resolves circular dependencies and explicitly bridges the qualitative-to-quantitative gap: (1) Structured Human-Anchored Coding: Human experts code a seed set of interviews using established deductive/inductive content analysis. (2) RAG-Augmented Code Extraction: A retrieval-augmented LLM extracts codes from remaining interviews by retrieving similar human-coded segments, forcing citation of specific excerpts. (3) Hierarchical Code Aggregation: Extracted codes are mapped to a scalar reward using a learned, attention-based aggregation network. This network weights codes based on their theoretical category and valence, mapping complex, potentially contradictory codes into a continuous reward space while preserving uncertainty estimates. (4) Contrastive Reward Modeling: The reward model is trained using a contrastive objective. Negative pairs are generated via targeted LLM-based negation and antonym substitution at the code level, ensuring semantically valid inversions for robust training.

### Expected Contributions

A non-circular, methodologically sound framework for converting qualitative data to RL reward signals. A formalized, mathematically rigorous mapping function (Hierarchical Code Aggregation) that translates overlapping qualitative codes into scalar rewards. A psychometrically grounded evaluation metric (Cohen's Kappa/IRR) for qualitative-to-quantitative translation fidelity.

---

## Idea 8: Cite-XAI-V2: Adaptive Concept Bottlenecks with RAG-Grounded Citations for Psychological Assessment

- **Overall Score**: 0.73
- **Novelty**: 0.86
- **Feasibility**: 6.05

### Problem Statement

Using XAI in high-stakes psychological assessments is critical, but forcing Chain-of-Thought explanations risks hallucination. Post-hoc explainability methods fail to reflect true model internals, while standard Concept Bottleneck Models (CBMs) force continuous, overlapping psychological distress signals into rigid predefined concepts, losing critical nuance and failing to capture emergent indicators.

### Proposed Method

We propose Cite-XAI-V2, an inherently interpretable framework combining Adaptive Concept Bottleneck Models (ACBMs) with RAG: (1) Adaptive Concept Bottleneck Architecture: The model predicts a layer of human-interpretable concepts (derived from psychological theory) but includes an explicit 'unexplained variance' node. This allows the model to flag novel, atypical indicators of distress without forcing them into predefined theoretical buckets. (2) RAG-Grounded Citations: The model cannot generate a psychological marker without retrieving an explicit text span supporting that concept. Citation accuracy is enforced via a novel retrieval penalty in the loss function. (3) Theory-Constrained Fine-Tuning: The model is fine-tuned to ensure its concept representations cluster according to established theoretical frameworks, using a multi-objective loss function that balances theoretical coherence with task accuracy.

### Expected Contributions

A highly reliable, anti-hallucination XAI framework for mental health that adapts to novel indicators. An extension of Concept Bottleneck Models to handle 'unexplained variance', preventing information loss in complex psychological data. A transparent system where educators can audit both theoretical and emergent textual evidence driving an AI's assessment.

---

## Idea 9: XAI-Tutor: Concept-Bottlenecked Pedagogical Chain-of-Thought for Educational Assessment

- **Overall Score**: 0.73
- **Novelty**: 0.78
- **Feasibility**: 6.85

### Problem Statement

AI systems in higher education and psychological assessment often operate as black boxes, lacking the transparency required for high-stakes evaluations. Existing XAI methods applied to LLMs, such as LIME or generic Chain-of-Thought, either fail to map accurately to text generation or risk hallucinating plausible but unfaithful justifications, limiting educator trust.

### Proposed Method

We propose XAI-Tutor, a framework that integrates deep learning models with a Concept Bottleneck Model (CBM) specifically designed for educational assessments. The core model uses a fine-tuned LLM to evaluate student responses. To guarantee faithfulness and prevent hallucination, the model is forced to first predict explicit pedagogical concepts (the bottleneck) directly from the student's interaction logs. A Retrieval-Augmented Generation (RAG) mechanism then generates a 'Pedagogical Chain-of-Thought' (PCoT) explanation strictly conditioned on these predicted concepts and grounded by citing specific student quotes.

### Expected Contributions

An interpretable AI assessment tool for educators; a novel XAI methodology that guarantees alignment between model internals and generated explanations via concept bottlenecking; and a framework ensuring fairness and transparency in automated educational evaluations.

---

## Idea 10: LongiSense-Attentive: Predictive Behavioral Shift Detection with Attentive Neural CDEs

- **Overall Score**: 0.71
- **Novelty**: 0.78
- **Feasibility**: 6.35

### Problem Statement

Tracking longitudinal behavioral changes in students using continuous adaptive deep learning is highly promising for mental health interventions. However, existing approaches rely on standard Neural CDEs that fail to capture the contextual history leading up to drift events. Furthermore, deploying these models without formalized divergence metrics or mechanisms to combat automation bias in human-in-the-loop systems poses significant ethical risks.

### Proposed Method

We propose LongiSense-Attentive, a safe behavioral shift prediction framework: (1) Attentive Neural CDEs: We enhance standard Neural CDEs with an attention mechanism over the historical trajectory, allowing the model to weigh specific past events when processing current irregular time-series data (e.g., LMS logs). (2) Formalized Drift Detection: We implement a dual-model architecture (frozen base vs. adaptive). Divergence is mathematically defined using the Page-Hinkley test, providing a statistically rigorous, tunable threshold for detecting concept drift without catastrophic forgetting. (3) Anti-Bias Escalation Protocol: When a shift is detected, the system outputs a confidence score and a RAG-generated summary, but crucially provides an interface for human counselors to view the raw data (actual forum posts) alongside the summary to prevent automation bias.

### Expected Contributions

A novel Attentive Neural CDE architecture that improves context awareness for irregular longitudinal data. A methodologically sound, mathematically formalized approach to concept drift detection using the Page-Hinkley test. An ethical, anti-bias deployment model for AI in educational mental health tracking.

---

## Idea 11: LongiSense: Safe Deep RL for Predicting Longitudinal Behavioral Shifts in Mental Health

- **Overall Score**: 0.70
- **Novelty**: 0.72
- **Feasibility**: 6.67

### Problem Statement

Mental health and academic motivation fluctuate significantly over time. While deep learning and longitudinal behavioral studies exist independently, there is a critical lack of continuous, adaptive deep learning models capable of processing these evolving trajectories. Existing Just-In-Time Adaptive Interventions (JITAIs) struggle with the irregular, sparse nature of real-world student data and the ethical risks of autonomous intervention.

### Proposed Method

We propose LongiSense, a continuous-time recurrent neural network combined with a safe deep reinforcement learning agent. The continuous-time architecture explicitly handles the irregular, sparse, and messy nature of longitudinal multimodal student data. To address ethical and scope concerns, the initial phase of the RL agent focuses purely on the predictive task of detecting behavioral shifts and forecasting optimal intervention timing. The agent operates under strict safety constraints, functioning as a clinical decision support system that recommends interventions to a human-in-the-loop (e.g., a counselor), rather than delivering them autonomously.

### Expected Contributions

A novel continuous-adaptation deep learning architecture for irregular longitudinal psychological data; a safe RL framework for predicting optimal intervention timing; and empirical insights into the trajectory of academic motivation over a semester.

---

## Idea 12: Qual2Reward: Grounded Qualitative-to-Reward Mapping with Expert-Calibrated Validation for RLHF

- **Overall Score**: 0.69
- **Novelty**: 0.75
- **Feasibility**: 6.35

### Problem Statement

Current Reinforcement Learning from Human Feedback (RLHF) pipelines rely on quantitative reward models derived from binary human preferences, stripping away the rich, contextual nuances of qualitative feedback. Existing methods like Contrastive Preference Learning and Semi-Supervised Reward Modeling improve the efficiency of quantitative RLHF but fail to capture the latent themes and emotional valences present in unstructured qualitative data.

### Proposed Method

We propose Qual2Reward, a pipeline that converts semi-structured interview data into continuous, multi-dimensional reward signals while mitigating LLM circularity and bias. First, an LLM performs zero-shot qualitative coding on interview transcripts, generating initial thematic representations. To prevent hallucination and circular dependency, a Retrieval-Augmented Generation (RAG) mechanism forces the LLM to ground its extracted codes in exact text spans from the interviews. Next, a Contrastive Preference Learning (CPL) mechanism maps these grounded qualitative codes into a continuous reward embedding space. Finally, to ensure stability during deep RL fine-tuning, we employ a Zeroth-Order Policy Gradient method, which bypasses the need for a differentiable reward model and stabilizes training over highly subjective, multi-dimensional signals.

### Expected Contributions

A methodological bridge between qualitative social science research and AI alignment; a novel RAG-grounded reward modeling technique that prevents circular dependency; and a stable deep RL framework capable of fine-tuning LLMs on multi-dimensional, subjective reward signals.

---

## Idea 13: AdaptiveSurveyLLM: Human-in-the-Loop RL for Culturally-Grounded Survey Localization

- **Overall Score**: 0.69
- **Novelty**: 0.82
- **Feasibility**: 5.55

### Problem Statement

Global health and sociological surveys require extensive resources to design, validate, and localize across cultures. Static surveys often suffer from cultural misinterpretations. Existing adaptive questioning methods (e.g., Computerized Adaptive Testing) rely on rigid statistical models, while current LLM generation tools lack a mechanism to iteratively test and refine instruments based on dynamic feedback.

### Proposed Method

AdaptiveSurveyLLM uses a deep reinforcement learning agent to dynamically localize and refine semi-structured interview guides. Positioned as an adaptive pre-testing instrument rather than a full replacement for surveys like the WHO CIDI, the agent optimizes question phrasing and ordering for specific cultural contexts. To bridge the sim-to-real gap, the RL agent is trained using a Human-in-the-Loop (HITL) framework. The agent proposes question variants, which are evaluated by a minimal, targeted pool of human respondents from the target culture. The reward function is explicitly penalized for generating leading questions, optimizing instead for a mathematically rigorous information gain metric derived from active learning.

### Expected Contributions

A paradigm shift from static to dynamically localized survey instruments; a methodology for automated evaluation of question phrasing that avoids the sim-to-real gap via human-in-the-loop RL; and tools that significantly enhance the validity, reliability, and cultural adaptability of complex diagnostic surveys.

---

## Idea 14: SocioSim: Constrained Self-Play RL for Simulating Historical Societal Dynamics

- **Overall Score**: 0.69
- **Novelty**: 0.82
- **Feasibility**: 5.58

### Problem Statement

LLM self-play and multi-agent evolution have shown immense success in isolated or mathematical environments, but a significant gap exists in applying these systems to simulate complex societal behaviors for policy-making. Existing multi-agent LLM frameworks for social simulation lack a robust mechanism for evolving agent behaviors based on emergent dynamics, primarily due to the intractability of defining reward functions for subjective societal outcomes.

### Proposed Method

We introduce SocioSim, a multi-agent LLM framework utilizing self-play deep RL constrained to highly specific, well-documented historical events (e.g., local town hall meetings) to simulate societal dynamics. Agents are initialized with diverse demographic profiles and interact in a simulated environment governed by historical context. To solve the reward design problem, the 'Policy Reward Model' is constructed using a Constitutional AI approach, where a panel of LLM judges evaluates emergent behaviors against established sociological indices and historical records. To prevent mode collapse and sycophancy, the self-play RL loop utilizes a minimax objective, forcing agents to explore diverse, realistic strategies rather than converging on degenerate behaviors.

### Expected Contributions

A novel computational framework for social innovation research; a validated methodology for applying self-play RL to qualitative societal simulations using a constitutionally defined reward function; and predictive models capable of evaluating the societal impact of proposed policies.

---

## Idea 15: SocioSim-Struct: Strategic Self-Play for Societal Simulations with Structured Deterministic Rewards

- **Overall Score**: 0.62
- **Novelty**: 0.55
- **Feasibility**: 7.00

### Problem Statement

Applying LLM self-play to simulate complex societal behaviors often results in circular reward designs or overfitting to specific historical outcomes. LLM-based judges introduce sycophancy and bias, while mimicking historical texts fails to capture the underlying strategic constraints of historical actors.

### Proposed Method

We introduce SocioSim-Struct, a multi-agent self-play framework for societal simulations grounded in deterministic, rule-based reward functions. To ensure feasibility, we narrow the scope to bounded, two-party historical trade negotiations with quantifiable outcomes. Instead of evaluating free-form text, agents must output strategic actions in structured JSON formats, which are parsed by a deterministic environment script to calculate exact economic or treaty-based metrics. RAG-augmented personas prioritize strategic constraints, and the self-play mechanism encourages exploration of diverse negotiation paths, rewarding strategic rationality to enable plausible counterfactual discovery.

### Expected Contributions

A robust, bias-mitigated framework for simulating multi-agent societal interactions using structured outputs. A method for generating and evaluating historically plausible counterfactual scenarios without the subjectivity of LLM-based evaluation, demonstrated in a bounded, reproducible testbed.

---

