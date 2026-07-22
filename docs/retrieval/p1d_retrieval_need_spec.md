# P1D.0 — ERLab Retrieval Need Specification

> **Status: DRAFT (revision P1D.0a) for user review. NOT frozen. No gate closed.**
> Machine-readable twin: `p1d_retrieval_need_spec.json` (v1.1).
> Revision P1D.0a corrects: risk/non-invertibility terminology, missed-evidence rationale, and task objective/risk separation per external review.

## Mission

Determine the **lowest-complexity retrieval system that satisfies ERLab's real research workflows**.

The program does **not** begin from the assumption that ERLab needs a larger embedding model. It begins from four questions:

1. Which retrieval failures materially harm ERLab?
2. Does the current lexical system already meet the required standard?
3. Where it fails, is the cause representation, ranking, chunking, or structure?
4. Which intervention addresses that cause with acceptable operational cost?

The experiment is **successful even when the conclusion is** "retain lexical retrieval" or "fix chunking rather than change models." A negative result is a valid outcome.

## Scope guardrail

P1D is **independent of the frontend F1 roadmap.** Nothing in this spec touches production ranking, the frozen benchmark, or the frozen snapshot. All P1D artifacts are additive governance docs under `docs/retrieval/` and `data/retrieval/`.

---

## Six retrieval task families

ERLab must perform six distinct retrieval jobs. Each is defined along **three axes** (corrected in P1D.0a — v1 conflated these):

- **Task objective** — what the job is trying to retrieve.
- **Primary integrity risk** — the defining research-integrity failure of the task.
- **Primary coverage risk** — what the task can fail to surface.

| Task family | Retrieved unit | Task objective | Primary integrity risk | Primary coverage risk | Closest benchmark proxy |
|---|---|---|---|---|---|
| **Paper discovery** | Paper or abstract | Surface relevant papers broadly | agenda_mismatch | missed_relevant_evidence | `discovery_ranking` (good fit) |
| **Evidence retrieval** | Exact passage | Retrieve a passage supporting a claim | **false_support** | missed supporting evidence | `retrieval_ranking` (no passage granularity) |
| **Contradiction retrieval** | Exact passage | Surface contradicting/qualifying passages | **missed_contradiction** | missed contradicting evidence | `negated_findings` (weak proxy) |
| **Method retrieval** | Method section/passage | Retrieve usable methods/algorithms | agenda_mismatch | missed relevant method | `method_vs_application` (good fit) |
| **Multi-paper synthesis** | Diverse passages, several papers | Retrieve a diverse, non-redundant set | **redundancy** | missed diverse evidence | `near_duplicate` (adjacent) |
| **Research-gap analysis** | Papers and agenda passages | Distinguish same-question from similar-topic | **agenda_mismatch** | missed agenda-relevant paper | emergent across slices |

**Why the three-axis split matters:** Evidence retrieval's *objective* is to retrieve supporting evidence (a coverage goal), but its defining *integrity* risk is false support (it can retrieve a passage that *looks* supportive but isn't). v1 listed "missing supporting evidence" as both the table's primary risk AND (via the matrix) false support as the critical cell — that was a conflation. The objective and the integrity risk are different axes and must be tracked separately.

**Important limitation, stated up front:** the frozen 66-case benchmark was designed around adversarial *retrieval failure modes* (slices), not product *workflows* (task families). Two families — **evidence retrieval** and **contradiction retrieval** — operate at passage granularity, which the benchmark does not have. The benchmark can validate paper-level retrieval quality; it **cannot** validate whether ERLab can retrieve a specific evidential passage. This is documented in detail in `p1d_failure_analysis.md`.

## Risk hierarchy and compensability

v1 used "non-invertible" for two different concepts, creating a contradiction (the need-spec said false support was the *only* non-invertible risk; the task-risk matrix said five cells were). P1D.0a separates them cleanly:

### Two distinct concepts

| Concept | Meaning | Which risks |
|---|---|---|
| **Globally non-compensable** | No recall gain *anywhere* compensates. Reserved exclusively for one risk. | **false_support** (only) |
| **Task-specific hard gate** | Candidate must meet a frozen absolute threshold AND stay within an allowed paired regression margin on the task's defining risk. NOT zero-tolerance — microscopic regression within the margin does not fail (normal measurement/annotation variance must not make activation impossible). | missed_contradiction, agenda_mismatch, missed_relevant_evidence, redundancy |

The hard-gate thresholds and paired-regression margins themselves are **frozen at P1D.6**, not here. This spec establishes *which* risks are hard-gated and *for which tasks*; P1D.6 sets the numbers.

### The ranked hierarchy

| Rank | Risk | Compensability | Why it ranks here |
|---|---|---|---|
| **1** | **False support** | globally non-compensable | **Silent.** Creates affirmative but incorrect evidence — researcher is actively misled, not merely under-informed. Contaminates downstream analysis. No recall gain compensates. |
| **2** | **Missed contradiction** | task hard-gated | **Silent.** Omits evidence without fabricating support. Researcher proceeds as if the claim is unopposed. Especially dangerous in biomedical workflows. |
| **3** | **Agenda mismatch** | task hard-gated | Looks relevant, passes a glance, misleads if not caught. Common with dense retrieval. |
| **4** | **Missed relevant evidence** | task hard-gated | **Silent, not visible.** v1 incorrectly called this "visible absence." A researcher generally does not know an unseen paper/passage exists. The defensible distinction from false support is *affirmative vs omissive*: false support fabricates incorrect affirmative evidence; missed evidence omits without fabricating. Both are silent; both are serious. |
| **5** | **Redundancy** | task hard-gated | Inflates perceived breadth, but each redundant result is individually relevant. Lowest integrity cost. |
| **6** | **Latency / resource cost** | operationally gated (separate) | Operational, not integrity, failure. Independently disqualifying for deployment (see operational envelope). |

### Invariants

- **False support is the only globally non-compensable risk.** A material regression fails the product gate regardless of macro improvements. This is no longer called "non-invertible" to avoid the v1 contradiction.
- **The other four integrity risks are task hard-gated**, not globally non-compensable. Each has a threshold + paired regression margin (frozen at P1D.6).
- **Missed relevant evidence is silent.** The v1 "visible absence" rationale is retracted.
- **False support vs missed evidence** is an affirmative-vs-omissive distinction, not a visible-vs-silent one.
- **Latency/resource cost** is a separate operational gate.

## How this spec is used downstream

- **P1D.1** classifies all 66 historical cases by failure category *and* by task family, separating *observed* selection-split behavior from *slice-design priors* on held-out cases.
- **P1D.2** authors fresh cases grounded in these six families — including passage-level cases the benchmark lacks.
- **P1D.6** freezes the absolute thresholds and paired-regression margins for each task hard gate.

## What this spec deliberately does NOT do

- It does **not** freeze the operational envelope (`p1d_operational_envelope.json`, split into diagnostic-host and production-representative in P1D.0a).
- It does **not** freeze hard-gate thresholds or regression margins (P1D.6).
- It does **not** select or exclude candidate policies (P1D.3).
- It does **not** close any gate. The P1D.0 gate closes only when this spec, the risk matrix, and the operational envelope are all user-approved and marked frozen.
