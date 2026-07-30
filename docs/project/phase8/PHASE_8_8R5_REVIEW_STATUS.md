# Phase 8 / 8R.5 — External Review Status

> **Status:** NOT COMPLETED. The independent external review cannot be performed
> at this time because the only available reviewer channel (ChatGPT MCP) is
> experiencing persistent connection failures (navigation redirects, HTTP 400,
> fetch failures). This is an infrastructure blocker, not a code issue.

## What has been attempted

Three attempts to obtain an independent review via ChatGPT (GPT-5 model,
quantitative/scientific-method expertise):

1. **First attempt** (during initial 8F): MCP returned `projection HTTP 400`
   error. Review packet prepared but not delivered.
2. **Second attempt** (during 8R.5): MCP returned `Turn reconciliation failed`
   with `fetch_error='projection HTTP 400'`.
3. **Third attempt** (continuing prior conversation): MCP returned
   `Navigation failed after 15s — stage: url displaced`.

All three attempts used different message sizes and conversation contexts.
The failure is consistent and appears to be a platform issue.

## What has been completed (engineering)

```text
8R.1  Mismatch boundary established             PASS
8R.2  Proposal-experiment binding enforced      PASS
8R.3  Semantic alignment gate                   PASS
8R.4  G1+G2 reruns from new frozen HEAD         PASS (G2 eval=ready with alignment)
8R.5  Independent external review                NOT COMPLETED (infrastructure blocker)
```

## What the review would assess

The review packet contains:
- Experiment specifications (research question, method, dataset, metrics)
- Observed results (deterministic, reproduced exactly)
- Paper text excerpts (abstract, method, conclusion)
- RESULT marker maps (with direction metadata)
- Automated evaluation gates (provenance, scope, conclusion, alignment)
- Independent reproduction reports (diff=0.0)

The reviewer would assess:
1. Whether the experiment answers the stated question
2. Whether the baseline and metric are appropriate
3. Whether claims match the actual experiment
4. Whether limitations are adequate
5. Whether the paper is reproducible
6. Whether any central claim is misleading

## Recommended next step

Retry the ChatGPT MCP after the platform recovers, or obtain a human reviewer
with documented quantitative/scientific-method expertise. The review packet
content is fully prepared and ready for delivery.
