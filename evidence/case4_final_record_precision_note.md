# Case 4 final record — precision note (additive; no sealed artifact modified)

Recorded 2026-08-19 per the owner's independent verification of the
publication branch. This note qualifies one sentence in
`evidence/case4_final_record.md` for archival precision; the final
record itself is preserved unchanged.

## The qualified sentence

The final record states, of the consumed qualifying attempt: "Zero
operator interventions. Zero quota or transport errors." The precise,
owner-verified reading is:

> **Zero Z.AI generation-provider quota or transport errors.**

That is the distinction that matters against the earlier quota specimen
(`evidence/case4_qualifying_runfail_1/`, HTTP 429 code 1308): the final
attempt's generation provider (glm-5.2 via the Coding Plan endpoint)
never throttled or failed, and the R2 transport-identity machinery was
never triggered.

## External, non-authority-affecting errors that did occur

The preserved run log (`evidence/case4_qualifying_runfail_3/r1_run.log`)
contains, verbatim and in full:

- **3 × PubMed `HTTP 429 Too Many Requests`** on literature-search
  queries (external bibliographic API rate limiting).
- **3 × OpenAlex `HTTP 400`** on literature-search queries.
- **LM Studio embedding `HTTP 400`** events during the ingestion stage
  (`body={"error":"Model reloaded.."}`, model
  `bortunac/text-embedding-bge-m3-embeddings`), absorbed by the stage's
  bounded retries (attempts 1/4, 2/4 recorded before recovery; the
  pipeline proceeded).

None of these touched the paper, the assurance gates, the repair, the
freeze/release authority, or the terminal classification. The
authoritative matrix and result records identify `numeric_fidelity` at
the remediation boundary as the sole cause of the final `blocked`
state, as the final record states.

The run log contains **zero** occurrences of `GatewayTransportError`,
Z.AI error code `1308`, or `api.z.ai` — confirmed by exact-string
search over the preserved artifact.
