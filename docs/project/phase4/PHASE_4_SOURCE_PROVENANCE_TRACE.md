# Phase 4 / WP-4A — Source-Provenance Loss Boundary Trace

> **Status:** WP-4A complete. Read-only investigation. No production code changed.
> **Repo:** `C:\Next-Era\Elephant-Rock-Research-Lab` @ `bfe2e43bba7af90b4687db1997f6c5b5fa0ed2e3`
> **Branch:** `feat/quarantine-and-frontend-redesign`

## Purpose

Identify the first concrete boundary at which retrieved literature stops being
available as durable citation data, for the Phase 3 defect: all six live papers
contained `[SOURCE-N]` markers (10–83 per paper) but **zero** bibliography,
reference list, or recoverable source identity, and BibTeX exports contained
only self-citations.

The Phase 3 closeout (`docs/project/phase3/PHASE_3_CLOSEOUT.md:48`) framed the
missing source data as *"consistent with and likely downstream of the ingestion
failure, but the exact data path was not traced."* This trace locates that
boundary.

## Method

Static read-only trace of one successful run's data path through 12 boundaries,
from provider search result to BibTeX export. Every claim is grounded in
`file:line`. The two load-bearing claims (the boundary-8 loss site and the
boundary-12 self-citation fabrication) were independently re-verified by the
main agent against the source.

---

## Decision-rule conclusion

### **(B) Source data never becomes durable — at the `[SOURCE-N]` marker-map boundary (boundary 8).**

Stable identifiers (DOI / arXiv ID / title / authors / year / venue / URL) **are**
available after retrieval and **are** persisted to the `papers` table (boundaries
1→3 work for every source except PubMed, which hard-codes `doi=""`). The defect
is **not** a drop of existing data.

What is never durable is the **per-paper, per-run citation index** — the
assignment *"in this generated paper, `[SOURCE-7]` denoted `papers.id=42`."* That
assignment is constructed as a local `list[str]` inside `PaperSynthesisStage.execute`
and is destroyed when the stage returns. There is no schema, column, JSON field,
run-artifact file, or chromadb metadata key that captures it. There is no producer
and therefore no consumer.

**Bounded conclusion (per Phase 4 direction):**

> The first demonstrated provenance-loss boundary is the non-persistence of the
> synthesis-time marker-to-source map. Embedding failure is **not required** to
> produce the missing-bibliography defect, although it may independently degrade
> retrieval, novelty checking, or source quality.

This is more precise than claiming ingestion is wholly irrelevant: the marker-map
non-persistence is *sufficient* to explain the missing bibliography, independent
of whether ingestion succeeds or fails. The synthesis path consumes `ctx.all_papers`
in memory, so a missing bibliography occurs even when retrieval succeeds; but
ingestion failure can still separately harm novelty checking and retrieval-driven
source augmentation. The bibliography is missing because no code path ever writes
the marker→source map, and every downstream reader (review endpoint,
BibTeX/Markdown/LaTeX export, reference resolver) is forced to re-derive a source
list from the LLM-generated proposal "References" text — which is itself
hallucinated or empty.

### Demonstrated loss boundary

```text
backend/pipeline/stages.py:1913-1931   — source_papers built as local list[str]
backend/pipeline/stages.py:2003-2013   — metadata["full_paper"] carries no map field
backend/pipeline/synthesis/paper_synthesizer.py:21-33  — PaperSynthesisResult has no source-map field
backend/pipeline/synthesis/section_wise_synthesizer.py:541-570 — emits a literal placeholder bibliography
backend/pipeline/persistence.py:166-223 — _extract_paper_artifact reads paper_markdown only
```

There is **no** `paper_source_markers` table, no JSON column on `proposals`, no
run-artifact file, and no chromadb metadata key for the marker→source assignment.

### Secondary (C)-class defects (source data IS durable but is omitted by readers)

Even the source data that survives in the `papers` table is not used downstream:

- **`backend/api/routes/exports.py:523-561`** (`export_run_bibtex`) — fetches
  `pipeline_runs.config_json` (dead code, lines 539-542) and then fabricates a
  self-citation `Paper(id=f"idea:{idea.id}", source="elephant_rock", authors=[], year=2026)`
  per idea (lines 550-556). It never queries the `papers` table. This is the
  "BibTeX exports contain only self-citations" finding, demonstrated in code.
- **`backend/api/routes/review.py:136-274`** (Trust & Sources) — derives sources
  from `proposals.references_json` (LLM text), not from `[SOURCE-N]` markers or
  the `papers` table.
- **`backend/pipeline/provenance/reference_resolver.py:124`** — `parse_reference`
  explicitly treats `[SOURCE-1]` as "irrelevant — treated as raw only."
- **`backend/api/routes/paper_export.py:77-134`** (Markdown/LaTeX) — ships
  `paper_md` verbatim; the exporter does not consult the `papers` table.

---

## Boundary-by-boundary table

| # | Boundary | In | Out | Stable IDs | Metadata | Failure state | Persistence | Consumer |
|---|---|---|---|---|---|---|---|---|
| 1 | Provider search result | 1 query | ≤20 `SearchResult`s/source | arXiv `arxiv_id` (`arxiv_source.py:227`); OpenAlex/CrossRef/S2 `doi`; **PubMed `doi=""` always** (`pubmed_source.py:325`) | title/authors/year/venue/url | Per-source `SourceSearchOutcome` with explicit failed/partial/success (`contracts.py:190-217`); failure = empty list, not silent drop | In-memory only | `SearchService.search_all_with_provenance` |
| 2 | Normalized literature record | all `SearchResult`s | `list[CandidateWithDiscoveries]` dedup by DOI-or-title (`search_service.py:384-398`); canonical `Paper` carries all fields | Same; source priority S2>PubMed>OpenAlex>CrossRef>arXiv (`search_service.py:378`) | Same | Per-source exceptions isolated via `gather(return_exceptions=True)` (`search_service.py:203-209`) | In-memory; `CandidateWithDiscoveries.discovery_metadata` carries `source_record_id`/`source_rank` | `LiteratureSearchStage` → `_post_literature_search` |
| 3 | Metadata persistence | `list[CandidateWithDiscoveries]` | 1 `papers` row per unique source + `run_papers` + N `paper_discoveries` | **Yes, fully.** `crud.add_paper` writes `doi`, `arxiv_id` (`persistence.py:526-528`); table has dedicated columns (`db/models.py:51-52`) | Yes, all fields | All-or-nothing transactional; raises after logging on exception (`persistence.py:643-646`). PubMed `doi=""` persists as empty string. | `papers`, `run_papers`, `paper_discoveries`, `search_queries`, `search_query_executions` | `IngestionStage`, `GapAnalysisStage`, `ProposalSynthesisStage`, `PaperSynthesisStage` (all read `ctx.all_papers` in memory, not DB) |
| 4 | Embedding / indexing | `ctx.all_papers` (in-memory) | chunk count = paper count; chromadb metadata = `{paper_id, paper_title, source, section, year, keywords}` (`vector_store.py:116-126`) | **None** — no DOI, no arXiv, no authors, no venue, no URL written to chromadb | title (truncated 500), year, keywords, source name, paper_id only | Zero-vector embeddings silently rejected at write (`vector_store.py:104-111`); returns count, not failure list | `chromadb` collection; BM25 index; governed runs also `vector_index_records` | `TwoStageRetriever.retrieve` → `NoveltyCheckingStage`, `IdeatorAgent._augment_with_retrieval` |
| 5 | Gap-analysis context | `ctx.all_papers` (in-memory) | `list[ResearchGap]` + cluster_report | Papers passed by reference; identity not used in gap output | Same | Runs on in-memory papers; ingestion failure does not starve it | `research_gaps` (via `persist_gaps`) | `IdeaGenerationStage` / `TreeSearchStage` |
| 6 | Proposal references | `ctx.all_papers[:30]` (in-memory, full identity) | `ResearchProposal`; `sections["references"]` is LLM text; `proposal.metadata` carries nothing source-related | **YES in the prompt only.** `_format_literature` builds `[SOURCE-{idx}] {authors} ({year}). {title}. {venue}. DOI: ... URL: ... arXiv: ...` (`proposal_synthesizer.py:850-856`) — the full map is materialized as a prompt string | Yes, fully, in the prompt only | LLM may emit hallucinated `[1] Author (Year)`; `_parse_references` only matches `[N]`, so `[SOURCE-N]` refs fall through as raw text (`proposal_synthesizer.py:758-772`) | `proposals.references_json` (LLM text, NOT the map); `proposals.content_md`. **The SOURCE-N→paper map is NOT persisted.** | `persist_proposals` (`persistence.py:879-961`) |
| 7 | Paper synthesis context | `ctx.all_papers[:30]` re-formatted + `proposal.to_markdown()` | `PaperSynthesisResult(paper_markdown, word_count, venue, model_used, source_count)` only | **DROPPED HERE.** `stages.py:1913-1931` re-formats sources as `[SOURCE-{idx}] {authors} ({year}). {title}. {venue}. Abstract: ...` — **no DOI, no URL, no arXiv** (unlike `_format_literature`). Map held in local `source_papers: list[str]`, never returned. | authors/year/title/venue/abstract only, in prompt only | LLM failure / timeout → `metadata["full_paper"]=None` (`stages.py:1954,1962`). Section-wise `_assemble_paper` emits placeholder `"[Generated from N source papers — see proposal for full bibliography]"` (`section_wise_synthesizer.py:565-567`) | `proposals.paper_md`; `proposals.paper_meta_json` (synthesis scalars only, `persistence.py:208-223`). **No source-map column exists.** | `_extract_paper_artifact` → `persist_proposals` |
| 8 | **`[SOURCE-N]` marker map** | none — map exists only transiently in boundary 7's local var | **0** — no map emitted to any durable store | n/a | n/a | **By design, not by failure.** The marker→paper association lives only in the LLM's prompt context window during synthesis. | **Nowhere.** No DB column, no JSON field, no run-artifact file, no chromadb metadata. | **Nothing — there is no consumer because there is no producer.** |
| 9 | Paper persistence | `ResearchProposal.metadata["full_paper"]` | 1 `proposals` row: `paper_md`, `paper_meta_json`, `references_json`, `sections_json` | n/a (operates on already-orphaned markdown) | n/a | n/a | `proposals.paper_md` (Text), `proposals.paper_meta_json` (Text) | `paper_export.py` routes; `review.py` route |
| 10 | Trust & Sources | `proposal.references_json` (LLM text, NOT a SOURCE-N map) | `sources[]` with `source_ref_hash, raw, title, authors, year, doi, resolution_status, match_method, confidence` | Sources derived from `references_json`, not from `[SOURCE-N]` markers in `paper_md`. `parse_reference` treats `[SOURCE-1]` as "irrelevant" (`reference_resolver.py:124`) | Whatever the LLM emitted in the References section | Unresolvable refs surface as `resolution_status:"unresolved"` (no silent drop) — but the input list is the wrong list (hallucinated proposal refs, not the actual source set) | Reads `proposals.references_json` + `papers` table at request time; writes `source_reviews` on human decision | Frontend review UI |
| 11 | Bibliography (MD/LaTeX) | `proposal.paper_md` | Markdown: verbatim `paper_md` (markers, no bib). LaTeX: `paper_md` wrapped in `\begin{document}` shell | **None carried into bibliography.** Exporter does not consult `papers` table. | None | n/a — operates on orphaned markdown as-is | Filesystem (`data/exports`, `data/runs/`) | Frontend download / GET |
| 12 | BibTeX export | (per-idea) `proposal.references_json`; (per-run) `ideas` list | Per-idea: 1 `@misc{erlab_paper_ideaN}` self-entry + N `@article` from `references_json` dicts. Per-run: N `@article` from fabricated `Paper(id=f"idea:{idea.id}", source="elephant_rock", authors=[], year=2026)` | Per-run **never loads `papers` table** — fabricates a self-citation Paper per idea (`exports.py:549-557`). Per-idea only resolves refs that parse via `parse_reference` (which skips `[SOURCE-N]`). | Per-idea: title/authors/year/venue/doi IF the LLM happened to emit them as parseable text | Empty `references_json` → only the self-citation entry | HTTP response (no file) | Frontend / external bibliographic tools |

---

## Answers to the seven trace questions

**Q1. Were source identities available immediately after retrieval (1→2)?**
**YES** for all sources except PubMed. `arxiv_source.py:227` sets `arxiv_id`;
`openalex_source.py:206`, `crossref_source.py:173`, `semantic_scholar.py:268-269`
set `doi` (S2 also `arxiv_id`). PubMed is the lone retrieval-side defect:
`pubmed_source.py:325` hard-codes `doi=""` and never sets `arxiv_id`. The
normalized `Paper` model (`models.py:12-27`) carries `doi`, `arxiv_id`, `url`,
plus title/authors/year/venue. Identities survive 1→2.

**Q2. Were they persisted before embedding (2→3, before 3→4)?**
**YES.** `persist_search_results` runs in `_post_literature_search`
(`stage_lifecycle.py:246-253`) — after `LiteratureSearchStage`, before
`IngestionStage`. `persistence.py:526-528` writes `doi=paper.doi,
arxiv_id=paper.arxiv_id` to the `papers` table, which has dedicated columns
(`db/models.py:51-52`). Durable identity exists before any embedding happens.

**Q3. Did an embedding/indexing failure (boundary 4) discard otherwise valid metadata?**
**NO — embedding failure does not discard metadata, and is not required to
produce the citation defect.** The metadata was never going to be carried by the
embedding path: `vector_store.py:116-126` writes only
`{paper_id, paper_title, source, section, year, keywords}` regardless of success
or failure. The downstream stages that need source identity (gap analysis,
proposal synthesis, paper synthesis) consume `ctx.all_papers` in memory
(`stages.py:778, 1194, 1914`), not the vector store. Ingestion failure (B-06)
starves only `NoveltyCheckingStage` and `IdeatorAgent._augment_with_retrieval`
(`ideator_agent.py:153-167`), which can independently degrade retrieval, novelty
checking, or source quality — but is not the cause of the missing bibliography.
**Marker-map non-persistence is sufficient to explain the citation defect
without invoking ingestion failure.**

**Q4. Did proposal synthesis (boundary 6) receive identifiable sources?**
**YES — in memory only.** `ProposalSynthesisStage` passes `ctx.all_papers[:30]`
(`stages.py:1194`) to `ProposalSynthesizer.synthesize`, which calls
`_format_literature` (`proposal_synthesizer.py:203, 842-860`). That function
materializes the full SOURCE-N→identity map as a prompt string with authors,
year, title, venue, DOI, URL, arXiv, and abstract, and injects it into the LLM
prompt. The identities were available; they were not captured.

**Q5. Were paper markers (boundary 8) EVER associated with source records?**
**YES, but only ephemerally — never durably.** Three transient forms, all lost
on stage exit:
- `PaperSynthesisStage.execute` builds `source_papers: list[str]` where index
  `i-1` ↔ `ctx.all_papers[i-1]` ↔ `[SOURCE-{i}]` (`stages.py:1913-1931`). Local
  variable; discarded when `execute` returns.
- `ProposalSynthesizer._format_literature` builds the same indexed string
  (`proposal_synthesizer.py:846-859`). Local to `synthesize()`; only the LLM
  response is kept.
- `SectionDraft.structured_claims` carries `evidence_ids` like `["SOURCE-3"]`
  (`section_contracts.py:134`, `section_wise_synthesizer.py:344`). But
  `SectionDraft` objects are NOT included in `metadata["full_paper"]` —
  `stages.py:2003-2013` hand-picks only scalars and `synthesis_strategy`. The
  claims/evidence trail is dropped at the dict-construction step.

At no point does any code write `(run_id, proposal_id, marker="SOURCE-N",
paper_id)` to any table, file, or collection.

**Q6. Did persistence (boundary 9) drop an existing citation map?**
**NO — there was no map to drop.** `_extract_paper_artifact`
(`persistence.py:166-223`) reads only `paper_markdown` (line 203) plus synthesis
scalars (lines 210-216). It cannot drop a field the producer never wrote. The
dataclass `PaperSynthesisResult` (`paper_synthesizer.py:21-33`) has no source-map
field; `to_dict()` is `asdict(self)` and therefore also has none. The persistence
reader is innocent; the producer is the gap.

**Q7. Did export (boundaries 11/12) omit references available elsewhere?**
**YES, in two distinct ways:**
- Per-idea BibTeX (`paper_export.py:137-213`) reads `proposal.references_json`
  (LLM-generated proposal-text refs, NOT the actual `[SOURCE-N]` source set).
  Even if it tried to read markers, `parse_reference` deliberately ignores them
  (`reference_resolver.py:124`). The `papers` table is not consulted.
- Per-run BibTeX (`exports.py:518-561`) explicitly fabricates a self-citation
  `Paper(id=f"idea:{idea.id}", source="elephant_rock", authors=[], year=2026)`
  per idea (`exports.py:549-557`) and never touches the `papers` table. The
  fetch of `config_json` at lines 539-542 is dead code. This is the closeout's
  "only self-citations" finding, demonstrated.

So even the source data that IS durable (in `papers`) is omitted by the exporters.

---

## What "smallest run-scoped source manifest" would need to capture

To restore provenance minimally (WP-4B), persist the assignment that today exists
only in `source_papers`. For each generated paper, a row per cited source with at
least:

```text
run_id              — already in pipeline_runs
proposal_id/idea_id — already in proposals
marker              — literal "SOURCE-7"
marker_index        — int N
paper_id            — FK to existing papers row (resolved via crud.get_paper_by_source_id)
source_rank         — position in ctx.all_papers[:30] (already computed at stages.py:1914)
synthesis_strategy  — "monolithic" or "section_wise" (already in paper_meta_json)
discovery_route_ids — optional: PaperDiscovery rows for this paper in this run (already exist)
```

This reuses data that already exists at `papers`, `paper_discoveries`, and
`paper_meta_json` — it does **not** require re-fetching from providers. The
shape of the fix (subject to WP-4B authorization):

1. Widen `PaperSynthesisResult` (or add a parallel return) to carry
   `[(marker_index, paper_source_id)]`.
2. Have `_extract_paper_artifact` read it.
3. Add a `paper_source_markers` table (or a JSON column on `proposals`).
4. Point the BibTeX, Markdown/LaTeX, and review endpoints at that table instead
   of `references_json`.

---

## Independent re-verification (main agent)

The two load-bearing claims were re-verified by direct source read:

1. **Boundary 8 loss site** — `backend/pipeline/stages.py:1890-2020` confirms
   `source_papers` is a local `list[str]` (line 1913), consumed only as
   formatted strings passed to the synthesizer (line 1943); the persisted
   `metadata["full_paper"]` dict (lines 2003-2013) carries no source-map field.
   **Verified.**
2. **Boundary 12 self-citation fabrication** — `backend/api/routes/exports.py:515-561`
   confirms `export_run_bibtex` fetches `config_json` (dead code, 539-542) then
   fabricates `Paper(source="elephant_rock", authors=[], year=2026)` per idea
   (550-556) and never queries the `papers` table. **Verified.**

Both hold. The (B) conclusion stands.

---

## Caveats — what static reading could NOT establish

1. **Live-run paper_md contents** — confirmed by code that the section-wise path
   always emits the placeholder bibliography and the monolithic path returns
   whatever the LLM produced. Could not inspect the 6 live papers' actual
   `paper_md` to confirm which path each took. A live DB read of
   `paper_meta_json.synthesis_strategy` would identify which path each took.
2. **Whether the monolithic LLM ever emits a usable bibliography** — the
   monolithic system prompt (`backend/pipeline/synthesis/prompts/paper_synthesis_system.md:53`)
   instructs "Use [SOURCE-X] for all citations" but does NOT instruct the model
   to emit a resolved bibliography. Even perfect compliance yields orphaned
   markers.
3. **Why `export_run_bibtex` ignores the `papers` table** — the function fetches
   `config_json` then does nothing with it (dead code). Could not determine
   whether unfinished refactor or intentional; effect is the demonstrated
   self-citation behavior either way.
4. **Live ingestion failure mode** — closeout says ingestion failed;
   `vector_store.py:104-111` silently rejects zero vectors, the most likely
   mechanism. Not reproduced; and as shown in Q3, irrelevant to citation
   provenance.
5. **`IdeaPaperLink` usage** — `persistence.py:805-874` populates `IdeaPaperLink`
   from `idea.supporting_papers` for `IdeaGenerationStage` ideas (empty for
   `TreeSearchStage`, `stages.py:1402`). The review endpoint does NOT traverse
   `IdeaPaperLink → Paper → doi/arxiv_id`; it only reads `references_json`
   (`review.py:202-243`). An additional (C)-class defect, secondary to the (B)
   conclusion.
6. **All claims are about the static code path on the current branch.** A live
   run taking an alternate path could shift specifics, but the structural
   absence of any source-map persistence (boundary 8) means no path can recover
   the markers.

---

## Exit condition check

> *The zero-bibliography defect has a repository-grounded causal path, not merely
> a correlation with ingestion failure.*

**Met.** The causal path is demonstrated: `stages.py:1913-1931` (build map) →
`stages.py:2003-2013` (drop map from persisted dict) → no schema/column to
receive it → every downstream reader re-derives from hallucinated
`references_json` or fabricates self-citations. The Phase 3 "ingestion failure"
correlation is explicitly refuted by the code path (Q3).

---

## Key files (absolute paths)

1. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\stages.py` — `PaperSynthesisStage` loss site (1838-2056); `ProposalSynthesisStage` (1144-1262)
2. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\synthesis\paper_synthesizer.py` — `PaperSynthesisResult` has no source-map field
3. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\synthesis\section_wise_synthesizer.py` — placeholder bibliography (541-570)
4. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\synthesis\proposal_synthesizer.py` — `_format_literature` in-memory map (842-860)
5. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\persistence.py` — `_extract_paper_artifact` (166-223); `persist_search_results` (441-646)
6. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\literature\search_service.py` — provenance-bearing search (86-398)
7. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\literature\models.py` — normalized `Paper` schema
8. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\literature\pubmed_source.py` — `doi=""` defect (319-330)
9. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\db\models.py` — `Paper`, `Proposal` (38-156); `PaperDiscovery` (691-782)
10. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\knowledge\vector_store.py` — chromadb metadata schema (84-153)
11. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\provenance\reference_resolver.py` — `[SOURCE-N]` ignored (124)
12. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\api\routes\review.py` — Trust & Sources (136-274)
13. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\api\routes\exports.py` — BibTeX self-citation (518-561)
14. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\api\routes\paper_export.py` — per-idea BibTeX from `references_json` (137-213)
15. `C:\Next-Era\Elephant-Rock-Research-Lab\backend\pipeline\orchestrator\stage_lifecycle.py` — `_post_literature_search` ordering (223-295)

---

*End of WP-4A. Decision-rule conclusion: **(B) source data never becomes durable** at the marker-map boundary. Ready for WP-4B authorization.*
