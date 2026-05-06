## Title

X-VoxelRoute: Efficient 4D Bi-Level Routing with Post-Hoc Causal Proxy Models for Explainable 3D Spatiotemporal Perception

## Abstract

In safety-critical autonomous driving systems, LiDAR-based 3D object detectors increasingly rely on complex spatiotemporal transformers to process sequential point clouds. However, deploying these models faces two major limitations: standard spatiotemporal attention scales quadratically with the number of points, and the internal decision-making of dynamic routing mechanisms remains a black box, lacking causal rigor. Current explainability methods either rely on superficial visualizations or disruptive forward-pass interventions that degrade real-time performance and yield confounded attribution scores. To address these bottlenecks, this proposal introduces X-VoxelRoute, a decoupled architecture and explainability framework that adapts efficient bi-level routing to 3D sequences via voxelization, paired with a non-invasive post-hoc Causal Proxy Model (CPM). The proposed approach achieves strict linear $O(N)$ scaling by filtering irrelevant background voxels at a coarse level before applying fine-grained attention, while the CPM enables mathematically sound causal tracing without compromising inference latency. The expected results include establishing a strong, efficient baseline for 4D transformers on the nuScenes and Waymo Open Datasets, demonstrating high fidelity in causal explainability, and proving that safety-critical routing rationales can be preserved during model distillation for edge deployment.

## Introduction

The rapid advancement of autonomous driving systems critically depends on robust and accurate 3D spatiotemporal perception. LiDAR sensors generate precise 3D point clouds of the surrounding environment, which are typically processed by deep neural networks to detect and track dynamic objects. Recently, spatiotemporal transformers have emerged as a dominant architecture for this task, leveraging self-attention mechanisms to capture long-range dependencies across consecutive frames. By modeling the temporal evolution of point clouds, these architectures significantly outperform traditional single-frame detection baselines. However, deploying large-scale transformer models in real-time, safety-critical autonomous vehicles introduces severe computational and reliability challenges. As the volume and resolution of LiDAR sensors increase, the computational burden of processing these sequential point clouds grows exponentially. Furthermore, ensuring that these models make decisions for the right reasons—avoiding spurious correlations—is paramount for passing rigorous safety certifications and gaining public trust.

Despite their high accuracy, current state-of-the-art 3D spatiotemporal models suffer from two fundamental limitations. First, the core self-attention mechanism scales quadratically, $O(N^2)$, with the sequence length or number of spatial regions. While efficient routing mechanisms like BiFormer (Zhu et al., 2023) have been successfully introduced for dense 2D images to achieve dynamic, sparse attention, their adaptation to highly sparse and irregular 3D point cloud domains remains notoriously difficult due to structural differences between dense pixels and sparse voxels. Second, the internal decision-making processes of these dynamic routing models are entirely opaque. When an autonomous vehicle's perception module fails to detect a pedestrian, current explainability methods cannot rigorously quantify why certain spatial regions were ignored by the attention mechanism. Existing XAI tools either provide post-hoc visualizations that lack causal rigor or rely on disruptive forward-pass interventions (e.g., occlusion sensitivity) that severely degrade real-time inference latency and yield confounded attribution scores.

To bridge these gaps, this proposal introduces X-VoxelRoute, a novel framework coupling efficient 3D architectural design with mathematically rigorous explainability. At the architectural level, X-VoxelRoute adapts 2D bi-level routing to irregular point cloud sequences via structured voxelization. By filtering irrelevant background voxels at a coarse routing level and restricting fine-grained attention to dynamically selected key regions, the model achieves strict $O(N)$ scaling, resolving the memory bottlenecks of standard 3D transformers. Concurrently, to solve the explainability bottleneck, we propose a non-invasive Post-Hoc Causal Proxy Model (CPM). Rather than disrupting the primary model's forward pass, we train a lightweight auxiliary network post-hoc to approximate the teacher model's routing distributions using do-calculus principles. This allows for rigorous quantification of the causal impact of specific spatial routing decisions on the final detection outcomes without ever compromising real-time performance.

The expected contributions of this research are threefold. (1) A computationally tractable methodology for adapting bi-level routing to 4D spatiotemporal point cloud sequences, establishing a highly efficient baseline for 3D transformers. (2) A mathematically rigorous, non-invasive framework for causal tracing in dynamic routing attention using Causal Proxy Models, circumventing the latency and confounding issues of current XAI techniques. (3) A specialized routing rationale distillation paradigm that proves dynamic attention policies can be effectively transferred to edge-ready student models without losing explainability. The remainder of this proposal details the related work, the formal mathematical methodology, the comprehensive evaluation plan, and the project timeline.

## Related Work

## Related Work

Our work intersects with recent advances in efficient 3D spatiotemporal perception, explainable AI (XAI) for vision transformers, and knowledge distillation. We review the literature most pertinent to our proposed contributions and highlight critical gaps that motivate the X-VoxelRoute framework.

**Efficient Transformers for 3D Perception.** 
The paradigm shift from sparse convolutional networks to transformers for LiDAR-based 3D object detection has yielded remarkable performance gains, largely driven by the adoption of spatiotemporal point cloud sequences. However, standard transformer attention mechanisms suffer from a prohibitive $O(N^2)$ computational complexity, which is severely exacerbated when processing dense 4D spatiotemporal volumes. While recent works such as SST and VoT have attempted to adapt vision transformers directly to sparse voxels, they still struggle with long-sequence memory bottlenecks. To address this, dynamic token routing has emerged as a promising solution in 2D computer vision. Notably, BiFormer introduced bi-level routing attention (BRA), which filters irrelevant background tokens at a coarse level before applying fine-grained attention, achieving strict $O(N)$ scaling. Despite its success in dense, regular 2D grids, adapting such top-down routing mechanisms to highly irregular, sparse 3D point clouds remains an open problem due to the structural collapse of spatial hierarchies during downsampling. Preliminary attempts to adapt 2D routing to 3D, such as VoxelSet, often rely on static heuristics rather than dynamic, content-aware region selection. Our work bridges this gap by proposing a voxelized 4D bi-level routing mechanism that naturally handles point cloud sparsity, establishing a computationally tractable baseline for efficient 3D transformers.

**Explainability and Causal Tracing in Deep Networks.** 
As autonomous systems become reliant on complex spatiotemporal models, the demand for rigorous explainability has intensified. Current XAI methods for 3D detection largely rely on post-hoc visualizations, such as gradient-weighted class activation maps (Grad-CAM) adapted for point clouds (e.g., PointCAM), or perturbation-based saliency maps. While these methods offer intuitive visual explanations, they fundamentally lack causal rigor, frequently yielding confounded attribution scores that fail to distinguish between correlated features and true determinative factors. Conversely, causal tracing methods inspired by do-calculus offer mathematically sound attributions but typically require disruptive forward-pass interventions. For instance, causal masking techniques and activation patching directly alter the intermediate states of a model during inference. In the context of dynamic routing transformers, these interventions disrupt the routing distribution itself, degrading real-time performance and introducing out-of-distribution (OOD) artifacts. Recent work on Causal Proxy Models (CPMs) has shown promise in approximating causal graphs without modifying the primary network, but this has yet to be applied to complex, multi-stage attention mechanisms. X-VoxelRoute addresses this limitation by pairing with a non-invasive CPM. By training an auxiliary network to approximate the teacher's routing distributions using structural causal models, we enable rigorous, post-hoc causal tracing that strictly isolates the impact of specific spatial routing decisions without compromising inference latency.

**Model Distillation and Edge Deployment.** 
Deploying state-of-the-art 3D transformers on edge hardware with limited compute budgets necessitates effective model compression. Standard knowledge distillation (KD) techniques typically force a student network to match the final logits or intermediate feature maps of a larger teacher model. While effective for general compression, standard KD often fails to preserve the implicit decision-making policies of dynamic routing architectures. Recent studies have begun exploring "rationale distillation"—transferring the attention maps or region-selection policies of teachers to students—but this is largely confined to 2D image classification and natural language processing. In the 3D perception domain, distillation efforts (e.g., PointDistiller) focus primarily on geometric feature compression rather than the preservation of algorithmic reasoning. X-VoxelRoute introduces a specialized routing rationale distillation paradigm. By enforcing a compact student network to match the top-K region selection distribution of the teacher via a tailored loss function, we ensure that the safety-critical attention rationales and causal pathways identified by our CPM survive network compression, a crucial requirement for safety-critical autonomous driving.

## Proposed Method

The proposed X-VoxelRoute framework consists of three synergistic modules: a Voxelized 3D Bi-Level Routing mechanism (V3BR), a Post-Hoc Causal Proxy Model (CPM), and a Routing Rationale Distillation (RRD) paradigm. 

**Formal Problem Definition:**
Let $\mathcal{P} = \{P_{t-T}, \dots, P_t\}$ be a sequence of $T$ consecutive LiDAR point clouds, where each frame $P_t = \{p_i\}_{i=1}^{N_t}$ contains $N_t$ points. Each point $p_i = (x, y, z, r, t)$ consists of 3D coordinates $(x,y,z)$, reflectance $r$, and a temporal offset $t$. The goal is to map this sequence to a set of 3D bounding boxes $\mathcal{B} = \{b_j\}$, where $b_j = (x_j, y_j, z_j, w_j, h_j, l_j, \theta_j, c_j)$, denoting center, dimensions, yaw angle, and class. 

**1. Voxelized 3D Bi-Level Routing (V3BR):**
To process $\mathcal{P}$ efficiently, the continuous point clouds are first discretized into a structured 4D spatiotemporal volume $V \in \mathbb{R}^{X \times Y \times Z \times T \times C}$, where $X, Y, Z$ are spatial voxel divisions and $C$ represents initial point features extracted via a lightweight PointNet. 

Standard spatiotemporal attention computes $O((XYZT)^2)$ interactions, which is computationally prohibitive. We adapt BiFormer to this 4D volume. The voxel grid is partitioned into non-overlapping 4D regional windows $\mathcal{W} = \{w_s\}_{s=1}^{S}$. 
At **Level 1 (Coarse Routing)**, we compute a lightweight routing attention. For each window $w_s$, we derive a regional summary query $q_s \in \mathbb{R}^d$ by average pooling the voxel features within $w_s$. A multi-head linear projection computes the relevance between all pairs of regional windows:
$$ A_{i,j} = \text{softmax}\left( \frac{(W_q q_i) (W_k q_j)^\top}{\sqrt{d}} \right) $$
We select the top-$k$ most relevant windows for each $w_i$ to form a dynamic routing matrix $R_i$. 
At **Level 2 (Fine-grained Attention)**, standard multi-head attention is applied exclusively among the voxels within the routed top-$k$ regions. By restricting the fine-grained attention to a dynamically selected subset of windows, the computational complexity drops from $O(N^2)$ to strict $O(N \cdot k)$, where $k \ll S$. The output features $F_{out}$ are passed to a standard detection head (e.g., CenterPoint) for bounding box regression and classification.

**2. Post-Hoc Causal Proxy Model (CPM):**
To explain the routing decisions without disrupting the primary network's forward pass, we train an auxiliary Causal Proxy Model, $f_{CPM}$, post-hoc. Let $f_{XVR}$ be the frozen, pre-trained X-VoxelRoute teacher model. During training, $f_{CPM}$ observes the inputs $V$ and the routing distributions $A$ generated by $f_{XVR}$. 

The CPM is trained to approximate the teacher's detection outputs $\hat{\mathcal{B}} = f_{XVR}(V)$ using a standard regression loss:
$$ \mathcal{L}_{CPM} = \text{SmoothL1}(f_{CPM}(V, A), \hat{\mathcal{B}}) $$
Once $f_{CPM}$ converges, we can perform formal causal interventions based on do-calculus. To quantify the causal effect of a specific spatial routing decision (e.g., attending to a specific region $w_j$), we apply a hard masking intervention on the routing matrix: $A' = \text{Mask}(A, w_j)$. The Causal Attribution Score (CAS) for region $w_j$ given input $V$ is defined as the Expected Conditional Average Treatment Effect:
$$ \text{CAS}(w_j, V) = \mathbb{E} \left[ f_{CPM}(V, A) - f_{CPM}(V, \text{do}(A_{:, j}=0)) \right] $$
This formulation isolates the causal impact of region $w_j$ on the final bounding box predictions without ever forcing the primary model to process out-of-distribution inputs.

**3. Routing Rationale Distillation (RRD):**
For edge deployment, we compress X-VoxelRoute into a compact student network $f_{student}$ using a specialized loss function. Standard knowledge distillation matches final logits, but it fails to preserve the dynamic routing policies. We propose a Routing Rationale Distillation loss that forces the student's coarse routing distribution $A^{(s)}$ to match the teacher's top-$k$ region selection $A^{(t)}$:
$$ \mathcal{L}_{RRD} = \alpha \cdot \text{KL}\left( \text{softmax}(A^{(s)} / \tau) \parallel \text{softmax}(A^{(t)} / \tau) \right) + (1-\alpha) \cdot \mathcal{L}_{det} $$
where $\tau$ is a temperature parameter, $\alpha$ balances the routing distillation and the standard detection loss $\mathcal{L}_{det}$. This ensures that the safety-critical spatial rationales survive network compression.

*(Figure Description: The architecture diagram would be divided into three main blocks. Block 1 shows the V3BR pipeline: sequential LiDAR frames are voxelized into a 4D grid, passed through Level 1 coarse routing where a top-$k$ filter selects sparse regions, followed by Level 2 fine-grained attention operating only on those regions, outputting to a detection head. Block 2 illustrates the CPM: a parallel lightweight network observing the 4D grid and the teacher's routing map, intervening on the map via do-calculus, and outputting causal attribution scores. Block 3 depicts the RRD module, where the teacher's routing map is distilled into a smaller student network via KL divergence.)*

## Expected Contributions

1. **Voxelized 3D Bi-Level Routing (V3BR) Architecture:** This contribution provides a computationally tractable methodology for adapting 2D bi-level routing to highly irregular 3D point cloud sequences via 4D voxelization. It matters because it resolves the severe memory bottlenecks of standard 3D transformers, establishing a strong, efficient baseline for real-time autonomous driving perception.
2. **Post-Hoc Causal Proxy Model (CPM) for Explainability:** This contribution introduces a mathematically rigorous, non-invasive framework for causal tracing in dynamic routing attention. It matters because it bypasses the latency penalties and out-of-distribution confounds of existing XAI intervention methods, allowing developers to audit safety-critical routing decisions without degrading real-time inference.
3. **Routing Rationale Distillation (RRD) Paradigm:** This contribution formalizes a specialized distillation loss that forces compact student networks to mimic the top-$k$ routing distributions of larger teacher models. It matters because it proves that explainability and efficiency are not mutually exclusive, ensuring that causal rationales are preserved when deploying to edge devices.
4. **Comprehensive Empirical Benchmarking:** The research will deliver a rigorous decoupled evaluation of both architectural efficiency and causal fidelity on large-scale autonomous driving datasets (nuScenes and Waymo Open Dataset), providing the community with reproducible metrics and baselines for future 3D XAI research.

## Evaluation Plan

**Datasets:**
The framework will be evaluated on two large-scale, publicly available autonomous driving datasets:
1. **nuScenes:** Contains 1000 scenes with 1.4M annotated 3D bounding boxes. It features rich annotations for 23 classes and full LiDAR point cloud sequences. (Source: https://www.nuscenes.org/)
2. **Waymo Open Dataset:** Comprises 1150 scenes with high-resolution LiDAR data and extremely dense point clouds, providing a robust benchmark for evaluating the computational efficiency of our V3BR module. (Source: https://waymo.com/open/)

**Baselines:**
We will compare X-VoxelRoute against three categories of state-of-the-art baselines:
1. **Single-Frame Detectors:** CenterPoint (Yin et al., 2021) without temporal aggregation, to quantify the pure performance gains introduced by spatiotemporal modeling.
2. **Spatiotemporal Transformers:** Graph Neural Network and Spatiotemporal Transformer Attention (Yin et al., 2021), which represents the standard $O(N^2)$ global attention approach for 3D video detection.
3. **Explainability Methods:** Raw Attention Visualization and Occlusion Sensitivity. These will serve as XAI baselines to compare against our Post-Hoc Causal Proxy Model.

**Metrics:**
1. **Detection Performance:** Mean Average Precision (mAP) and nuScenes Detection Score (NDS). NDS is a weighted combination of mAP, mean Average Translation Error (ATE), Scale Error (ASE), Orientation Error (AOE), Velocity Error (AVE), and Attribute Error (AAE).
2. **Efficiency Metrics:** Frames Per Second (FPS), peak GPU memory usage (in Gigabytes), and Floating Point Operations Per Second (FLOPs). These will empirically validate the theoretical $O(N)$ scaling of V3BR.
3. **Causal Fidelity Score (CFS):** A novel metric defined as: $CFS = 1 - \frac{1}{M} \sum_{i=1}^{M} \frac{| \Delta \hat{y}_i^{CPM} - \Delta \hat{y}_i^{XVR} |}{\max(\Delta \hat{y}_i^{XVR}, \epsilon)}$. This measures how accurately the CPM's do-interventions predict actual changes in the teacher model's detection outputs, where $\Delta \hat{y} = |\hat{y}_{original} - \hat{y}_{intervened}|$.
4. **Routing Jaccard Similarity (RJS):** Defined as $RJS = \frac{|R_{teacher} \cap R_{student}|}{|R_{teacher} \cup R_{student}|}$, measuring the overlap of the top-$k$ routed regions between the teacher and the distilled student model.

**Ablation Design:**
1. **Routing Level Ablation:** We will ablate the bi-level routing by replacing it with (a) single-level global attention, and (b) single-level local sliding window attention (Hassani et al., 2023) to isolate the exact performance and efficiency trade-offs of the coarse-to-fine routing mechanism.
2. **CPM Intervention Ablation:** We will systematically mask different semantic regions (e.g., dynamic vehicles, static terrain, pedestrians) using the CPM to quantify the causal sensitivity of the routing mechanism to various object classes.

## Timeline

The proposed research will be executed over a 12-week period, divided into four distinct phases:

**Phase 1: Data Processing and V3BR Implementation (Weeks 1-3)**
- *Task 1:* Set up data pipelines for nuScenes and Waymo datasets, implementing 4D voxelization tensors.
- *Task 2:* Implement the Level 1 coarse routing and Level 2 fine-grained attention modules.
- *Dependency:* Task 2 depends on the completion of Task 1.

**Phase 2: Training and Efficiency Benchmarking (Weeks 4-6)**
- *Task 1:* Train the X-VoxelRoute (V3BR) model on nuScenes and evaluate detection metrics (mAP, NDS).
- *Task 2:* Profile FPS, memory, and FLOPs against baselines to validate $O(N)$ efficiency.
- *Dependency:* Requires functional V3BR architecture from Phase 1.

**Phase 3: Explainability and Causal Proxy Model (Weeks 7-9)**
- *Task 1:* Train the lightweight Post-Hoc Causal Proxy Model (CPM) on the frozen X-VoxelRoute outputs.
- *Task 2:* Compute Causal Fidelity Scores and conduct occlusion vs. do-intervention ablations.
- *Dependency:* Requires fully trained and frozen X-VoxelRoute model from Phase 2.

**Phase 4: Distillation and Paper Finalization (Weeks 10-12)**
- *Task 1:* Train the compact student network using Routing Rationale Distillation (RRD) and evaluate Routing Jaccard Similarity.
- *Task 2:* Compile experimental results, generate plots, and finalize the manuscript for submission.
- *Dependency:* Requires routing distributions from Phase 2 and Phase 3.

## References


- Chen, C.F.R., Fan, Q., & Panda, R. (2021). CrossViT: Cross-Attention Multi-Scale Vision Transformer for Image Classification. *2021 IEEE/CVF International Conference on Computer Vision (ICCV)*. DOI: 10.1109/iccv48922.2021.00041.
- Chu, X., Tian, Z., Wang, Y., et al. (2021). Twins: Revisiting the Design of Spatial Attention in Vision Transformers. *arXiv preprint arXiv:2104.13840*.
- Dosovitskiy, A., Beyer, L., Kolesnikov, A., et al. (2020). An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale. *arXiv preprint arXiv:2010.11929*.
- Hassani, A., Walton, S., Li, J., et al. (2023). Neighborhood Attention Transformer. *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*. DOI: 10.1109/cvpr52729.2023.00599.
- Yeh, C.V., Chen, Y., Wu, A., et al. (2023). AttentionViz: A Global View of Transformer Attention. *IEEE Transactions on Visualization and Computer Graphics*. DOI: 10.1109/tvcg.2023.3327163.
- Yin, J., Shen, J., Guan, C., et al. (2020). LiDAR-Based Online 3D Video Object Detection With Graph-Based Message Passing and Spatiotemporal Transformer Attention. *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*. DOI: 10.1109/cvpr42600.2020.01151.
- Yin, J., Shen, J., Gao, X., et al. (2021). Graph Neural Network and Spatiotemporal Transformer Attention for 3D Video Object Detection From Point Clouds. *IEEE Transactions on Pattern Analysis and Machine Intelligence*. DOI: 10.1109/tpami.2021.3125981.
- Zhu, L., Wang, X., Ke, Z., et al. (2023). BiFormer: Vision Transformer with Bi-Level Routing Attention. *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)*. DOI: 10.1109/cvpr52729.2023.00995.

## Risk Mitigation

**Risk 1: Extreme Computational Cost.** Training 4D spatiotemporal transformers and proxy networks on Waymo requires massive GPU resources that may exceed academic budgets.
*Mitigation:* We will aggressively utilize mixed-precision training (AMP), gradient checkpointing, and distributed data parallelism. We will initially prototype and validate all architectural and XAI modules on the significantly smaller nuScenes dataset before scaling to Waymo. 
*Fallback Plan:* If Waymo remains computationally infeasible, we will restrict the final evaluation to nuScenes and synthetically generated 3D datasets, which remain highly respected benchmarks in the community.

**Risk 2: Causal Proxy Model Unfaithfulness.** The lightweight CPM might fail to accurately approximate the highly non-linear routing decisions of the primary teacher model, leading to misleading causal explanations.
*Mitigation:* We will incrementally increase the capacity of the CPM and utilize attention-based feature sharing between the teacher and the proxy to ensure high Causal Fidelity Scores.
*Fallback Plan:* If the CPM fails to converge on complex routing distributions, we will pivot to a Linear Proxy Model that approximates only the final layer's routing logits, reducing the approximation space at the cost of fine-grained explainability.

**Risk 3: Suboptimal 4D Voxel Routing.** Adapting 2D bi-level routing to highly sparse 4D voxel grids might result in severe memory fragmentation or suboptimal region selection, failing to achieve theoretical $O(N)$ efficiency.
*Mitigation:* We will implement sparse tensor operations (e.g., using MinkowskiEngine or TorchSparse) to handle empty voxels efficiently, ensuring memory is only allocated for active spatial regions.
*Fallback Plan:* If 4D region partitioning proves too fragmented, we will fall back to a pseudo-4D approach: applying 3D spatial routing independently and using standard 1D temporal attention across the sequence, which still offers significant efficiency gains over global 4D attention.