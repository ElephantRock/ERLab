# BATCH-123 BLUEPRINT — Wiki Generation Service

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-123
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a WikiGenerator that produces a structured 30-field JSON wiki entry from
paper text, plus a WikiVerifier that cross-checks wiki claims against source text.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Define WikiEntry dataclass with 30 structured fields
  - Create WikiGenerator that uses LLM structured_output to fill the wiki
  - Create WikiVerifier that checks each factual claim against source text
  - Closed-book policy: only include information from the paper

What the code MUST NOT do:
  - Must NOT modify existing claims package (B121/B122 frozen)
  - Must NOT store wiki entries in database (future batch)
  - Must NOT call external APIs beyond the LLM provider

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest backend/tests/test_pipeline/test_batch123_wiki_generation.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: WikiGenerator MUST return empty WikiEntry on failure, not crash.
  HB-02: WikiVerifier MUST NOT modify the wiki entry — only flag issues.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

  WikiEntry (dataclass):
    - paper_id:         str
    - one_line_summary: str
    - problem_statement: str
    - proposed_method:   str
    - key_insights:      list[str]       (3-5 insights)
    - method_details:    dict            (architecture, training, loss, data)
    - experiments:       list[dict]      (dataset, metric, value, baseline)
    - limitations:       list[str]
    - future_work:       list[str]
    - connections:       list[str]       (related methods/papers)
    - code_and_resources: list[str]      (GitHub URLs, etc.)
    - tags:              list[str]
    - novelty_assessment: str            (incremental|significant|breakthrough)
    - quality_score:     float           (0-1, from WikiVerifier)
    - unsupported_claims: list[str]      (flagged by WikiVerifier)

  WikiGenerator:
    - __init__(self, provider)
    - generate(self, paper_text: str, paper_id: str) -> WikiEntry

  WikiVerifier:
    - verify(self, wiki: WikiEntry, source_text: str) -> WikiEntry
      (sets quality_score and unsupported_claims)

  File layout:
    backend/pipeline/wiki/
      __init__.py
      models.py
      generator.py
      verifier.py
      prompts/
        wiki_generation.md

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline:  2,316
  Expected delta: +8
  Expected total: 2,324

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: WikiEntry Model + WikiGenerator
  Priority: Critical
  Files: backend/pipeline/wiki/__init__.py, models.py, generator.py, prompts/wiki_generation.md
  Tests: 4
  | TEST-123-01-01 | unit | WikiEntry has all required fields | Missing field | Create WikiEntry | No AttributeError |
  | TEST-123-01-02 | unit | WikiGenerator returns WikiEntry from mock | Empty on valid input | Mock LLM returns valid JSON | WikiEntry with all fields |
  | TEST-123-01-03 | unit | WikiGenerator returns empty entry on failure (HB-01) | Crashes | Mock LLM raises | Returns WikiEntry with defaults |
  | TEST-123-01-04 | unit | Prompt exists with closed-book | Missing file | Check path | assert Path exists, contains CLOSED-BOOK |

TASK-02: WikiVerifier
  Priority: High
  Files: backend/pipeline/wiki/verifier.py
  Tests: 4
  | TEST-123-02-01 | unit | WikiVerifier sets quality_score | Score stays 0 | Verify with valid wiki | quality_score > 0 |
  | TEST-123-02-02 | unit | WikiVerifier flags unsupported claims | Empty list | Verify with fabricated wiki | len(unsupported_claims) > 0 |
  | TEST-123-02-03 | unit | WikiVerifier does NOT modify wiki (HB-02) | Wiki mutated | Verify and check original | Original fields unchanged |
  | TEST-123-02-04 | unit | WikiVerifier handles empty source text | Crash | Pass empty string | Returns wiki with low quality_score |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 8 new tests pass
  BAC-02: backend/pipeline/wiki/ package with generator + verifier
  BAC-03: No modifications to claims package
  BAC-04: Documents archived under /docs/aiv/BATCH-123/
