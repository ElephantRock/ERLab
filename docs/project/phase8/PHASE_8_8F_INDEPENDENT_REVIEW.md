# Phase 8 / 8F — Independent Methodological Review (Frozen Evidence)

> **Status:** Independent review completed by GPT-5.3 (ChatGPT, quantitative/
> scientific-method expertise, no relationship with authors) using a frozen
> evidence package extracted from the actual repository database.
>
> **One blocker** (Iris — irrecoverable narrative mismatch), **two material
> concerns** (Wine and Concrete — method terms present but abstracts
> unsupported by the benchmark experiment).

## Reviewer credentials

```text
reviewer:              GPT-5.3 (ChatGPT, model=auto)
expertise:             machine learning evaluation, scientific reproducibility
relationship:          no relationship with authors
materials reviewed:    frozen evidence package containing:
                        - experiment specifications (research question, method, dataset)
                        - observed result markers (metric, value, direction, role)
                        - paper abstracts, method sections, conclusions
                        - automated evaluation gates (provenance, scope, conclusion, alignment)
                        - method/dataset term presence checks
review date:           2026-07-30
conversation_id:       6a6b8332-4e1c-83eb-915c-753223764068
```

## Frozen evidence package

The evidence was extracted directly from the repository SQLite database
(`data/elephant_rock.db`) with SHA-256 hashes on paper text. The reviewer
received:

- The declared experiment spec (research question, method, dataset, metrics)
- The actual paper abstract, method section excerpt, and conclusion excerpt
- The observed result markers with values and directions
- The automated evaluation status and gate results
- Whether the paper's method/dataset terms match the spec

## Review findings

### Paper 1 — Iris: BLOCKER

> "The paper and experiment are about entirely different subjects and methods.
> Logistic-regression results cannot support claims about variational quantum
> solvers or hybrid quantum-classical algorithms. Result markers and
> reproducibility of the numerical output do not repair this broken
> evidence-to-claim chain."

**Paper 1 is irrecoverable without replacing the paper narrative.**

This is a Phase 7 artifact produced before the 8R alignment enforcement existed.

### Paper 2 — Wine Quality: MATERIAL CONCERN

> "The method section identifies the correct experiment, but the abstract's
> 'high-dimensional multimodal data' framing is unsupported by the described
> Wine Quality logistic-regression benchmark. The empirical core may be
> recoverable, but the abstract and any associated claims require substantive
> correction. Merely detecting the method and dataset terms is insufficient
> evidence of full narrative alignment."

### Paper 3 — Concrete Strength: MATERIAL CONCERN

> "The method section matches the linear-regression experiment, but invoking
> physics-informed neural networks in the abstract risks attributing the
> results to a materially different model class. Because the abstract
> communicates the paper's central contribution, this is more than a minor
> wording problem. It requires correction and claim-level review even though
> the alignment gate passed."

> "If the PINN discussion in Paper 3 is explicitly labeled as background only
> and the abstract clearly states that the evaluated model is ordinary linear
> regression, its finding could be reduced to **minor concern**."

## Reviewer's summary

> "Papers 2 and 3 have potentially valid experimental results, but the papers
> are not yet scientifically reliable as complete publications. Their status
> and lexical alignment gates do not establish that the abstracts, contribution
> statements, and conclusions are supported by the executed experiments."

## Impact on Phase 8 acceptance

```text
Wine paper:                         material concern (abstract framing)
Concrete paper:                     material concern (abstract framing)
Iris paper (Phase 7 artifact):      blocker (irrecoverable mismatch)
Proposal ↔ experiment binding:      enforced but lexical-only
External review:                    completed
External blockers:                  1 (Iris)
Phase 8 acceptance:                 NOT MET
```

## What the material concerns mean

The reviewer's key insight is that the experiment_alignment gate (8R.3) performs
**lexical** checking (does the paper mention "logistic regression" and "wine
quality"?) but this is **insufficient** for scientific validity. The paper's
abstract, contribution statement, and conclusion must describe the actual
experiment as the paper's central method, not merely mention the method term
somewhere in the text.

The current pipeline produces papers where:
- The method section correctly describes the experiment (after 8R.2)
- But the abstract frames the paper around a different proposed architecture
- The conclusion may attribute results to the wrong method class

To reach "no concern" or "minor concern", the paper synthesis must ensure the
abstract and conclusion explicitly state that the evaluated model is the spec's
declared method, and any broader architectural framing is labeled as motivation
or background.

## Reproduction outcome

Independent reproduction was performed separately (8E):
```text
Iris:      all metrics diff=0.000000
Wine:      all metrics diff=0.000000
Concrete:  all metrics diff=0.000000
```
The reviewer did not attempt reproduction independently.
