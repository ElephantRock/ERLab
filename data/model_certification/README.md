# Model Certification

This directory contains model certification data.

## Flow

```text
1. Create a candidate manifest in candidates/
2. Run certification: python -m backend.pipeline.model_certification.cli certify --manifest <path>
3. Review the capability report in reports/<model_id>/
4. If approved and suitable, promote to production registry
```

## Directory structure

```text
candidates/              — Candidate model manifests (YAML)
reports/                 — Certification capability reports (YAML)
production_registry.yaml — Production-admitted models with scoped stages
```

## Key invariant

**No untested model can enter the production registry.**

Every model must pass through certification and receive an explicit
admission decision before being promoted. The production registry only
contains models with explicit stage eligibility.
