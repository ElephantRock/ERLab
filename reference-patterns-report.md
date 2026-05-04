# Reference Patterns Report: Knowledge Graph, Truth Maintenance, Deduplication & Rate Limiting

Searched across 8 reference repositories. Findings organized by pattern category.

---

## 1. Knowledge Graph Relationship Extraction Patterns

### 1A. LangChain — Open-Ended Triple Extraction Prompt
**File:** `C:\Next AI\ref\langchain-master\libs\langchain\langchain_classic\indexes\prompts\knowledge_triplet_extraction.py`

**Pattern:** LLM-based extraction of (subject, predicate, object) triples using a few-shot prompt. The predicate is free-form — not from a fixed enum. The prompt instructs the LLM to act as a "networked intelligence" and extract ALL knowledge triples, using `<|>` as a delimiter.

```python
KG_TRIPLE_DELIMITER = "<|>"

_DEFAULT_KNOWLEDGE_TRIPLE_EXTRACTION_TEMPLATE = (
    "You are a networked intelligence helping a human track knowledge triples"
    " about all relevant people, things, concepts, etc. and integrating"
    " them with your knowledge stored within your weights"
    " as well as that stored in a knowledge graph."
    " Extract all of the knowledge triples from the text."
    " A knowledge triple is a clause that contains a subject, a predicate,"
    " and an object. ..."
    "EXAMPLE\n"
    "It's a state in the US. It's also the number 1 producer of gold in the US.\n\n"
    f"Output: (Nevada, is a, state){KG_TRIPLE_DELIMITER}(Nevada, is in, US)"
    f"{KG_TRIPLE_DELIMITER}(Nevada, is the number 1 producer of, gold)\n"
    "END OF EXAMPLE\n\n"
    ...
)
```

**Key takeaway for our system:** This approach uses free-form predicates. For academic papers, we'd need to **constrain the predicate space** to `cites`, `uses_method`, `extends`, `contradicts`, etc. — replacing the open-ended prompt with a typed enum, or using structured output (function calling / JSON schema) to force specific relationship types.

### 1B. LangChain — Memory-Context Triple Extraction
**File:** `C:\Next AI\ref\langchain-master\libs\langchain\langchain_classic\memory\prompt.py` (lines 113-163)

**Pattern:** Variant that extracts from conversation history, using `{history}` + `{input}` variables. Useful pattern for incremental extraction — only process the "last line" while keeping full history as context.

```python
"Conversation history (for reference only):\n"
"{history}"
"\nLast line of conversation (for extraction):\n"
"Human: {input}\n\n"
"Output:"
```

**Key takeaway:** When processing a paper, you can pass the paper abstract + full text as "history" and ask about specific claims in "input" for targeted extraction.

### 1C. LangChain — Citation Fuzzy Match (Structured Output)
**File:** `C:\Next AI\ref\langchain-master\libs\langchain\langchain_classic\chains\openai_functions\citation_fuzzy_match.py`

**Pattern:** Uses Pydantic models + structured output to extract facts with evidence. The `_get_span()` method implements **incremental fuzzy matching** — starts with 0 edit distance tolerance and increases until it finds a match in the source text.

```python
class FactWithEvidence(BaseModel):
    fact: str = Field(..., description="Body of the sentence, as part of a response")
    substring_quote: list[str] = Field(
        ...,
        description=(
            "Each source should be a direct quote from the context, "
            "as a substring of the original content"
        ),
    )

    def _get_span(self, quote: str, context: str, errs: int = 100) -> Iterator[str]:
        import regex
        minor = quote
        major = context
        errs_ = 0
        s = regex.search(f"({minor}){{e<={errs_}}}", major)
        while s is None and errs_ <= errs:
            errs_ += 1
            s = regex.search(f"({minor}){{e<={errs_}}}", major)
        if s is not None:
            yield from s.spans()
```

**Key takeaway:** The `regex` library with `{e<=N}` syntax provides approximate/fuzzy regex matching. This is directly applicable for matching extracted relationship claims back to source text spans.

---

## 2. Truth Maintenance / Evidential Reasoning Systems

### 2A. OpenNARS — Core Truth Value System
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Truth.h`

**Data model:** Truth is a struct with `frequency` (0-1, how true) and `confidence` (0-1, how certain):
```c
typedef struct {
    double frequency;   // [0,1] how often the statement is true
    double confidence;  // [0,1] how much evidence supports it
} Truth;
```

**Constants** from `Config.h`:
```c
#define TRUTH_EVIDENTIAL_HORIZON_INITIAL 1.0  // controls w2c/c2w conversion
#define MAX_CONFIDENCE 0.99                     // never 100% certain
#define RELIANCE 0.9                            // structural deduction confidence
```

### 2B. OpenNARS — Truth Revision (Evidence Merging)
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Truth.c` (lines 46-74)

**Core revision formula** — merges two independent evidence streams into one:
```c
Truth Truth_Revision(Truth v1, Truth v2)
{
    TruthValues(v1,v2, f1,c1, f2,c2);
    double w1 = Truth_c2w(c1);  // confidence → evidence weight
    double w2 = Truth_c2w(c2);
    double w = w1 + w2;
    // Weighted average of frequencies, confidence = max of w2c(w), c1, c2
    return (Truth) {
        .frequency = MIN(1.0, (w1 * f1 + w2 * f2) / w),
        .confidence = MIN(MAX_CONFIDENCE, MAX(MAX(Truth_w2c(w), c1), c2))
    };
}

// Conversion functions:
double Truth_w2c(double w) { return w / (w + TRUTH_EVIDENTIAL_HORIZON); }
double Truth_c2w(double c) { return TRUTH_EVIDENTIAL_HORIZON * c / (1 - c); }
double Truth_Expectation(Truth v) { return (v.confidence * (v.frequency - 0.5) + 0.5); }
```

**Python equivalent** from `english_to_narsese.py`:
```python
def Truth_Revision(v1, v2):
    (f1, c1) = v1
    (f2, c2) = v2
    w1 = Truth_c2w(c1)
    w2 = Truth_c2w(c2)
    w = w1 + w2
    return (min(1.0, (w1 * f1 + w2 * f2) / w),
            min(0.99, max(max(Truth_w2c(w), c1), c2)))
```

### 2C. OpenNARS — Evidential Stamp System (Prevents Double-Counting)
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Stamp.h` + `Stamp.c`

**Pattern:** Each belief carries a "stamp" — a list of evidential base IDs. When two beliefs share any base ID, they have **evidential overlap** and should NOT be revised together (that would double-count evidence).

```c
typedef struct {
    long evidentialBase[STAMP_SIZE];  // STAMP_SIZE = 10
} Stamp;

bool Stamp_checkOverlap(Stamp *a, Stamp *b)
{
    for(int i=0; i<STAMP_SIZE; i++)
    {
        if(a->evidentialBase[i] == STAMP_FREE) break;
        for(int j=0; j<STAMP_SIZE; j++)
        {
            if(b->evidentialBase[j] == STAMP_FREE) break;
            if(a->evidentialBase[i] == b->evidentialBase[j])
                return true;
        }
    }
    return false;
}
```

**Stamps are merged by interleaving** when revision happens:
```c
Stamp Stamp_make(Stamp *stamp1, Stamp *stamp2)
{
    Stamp ret = {0};
    bool processStamp1 = true, processStamp2 = true;
    for (int j=0, i=0; i<STAMP_SIZE; i++)
    {
        // interleave stamp1 and stamp2 entries
        if(processStamp1 && stamp1->evidentialBase[i] != STAMP_FREE)
            ret.evidentialBase[j++] = stamp1->evidentialBase[i];
        if(processStamp2 && stamp2->evidentialBase[i] != STAMP_FREE)
            ret.evidentialBase[j++] = stamp2->evidentialBase[i];
        ...
    }
    return ret;
}
```

### 2D. OpenNARS — Revision vs Choice Decision
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Inference.c` (lines 152-190)

**Pattern:** When a new belief arrives that matches an existing one, the system decides:
1. **If evidential overlap exists** → **Choice**: keep the higher-confidence belief (no revision)
2. **If no overlap AND terms match** → **Revision**: merge into stronger belief

```c
Event Inference_RevisionAndChoice(Event *existing, Event *incoming, long currentTime, bool *revised)
{
    ...
    bool overlap = Stamp_checkOverlap(&incoming->stamp, &existing->stamp);
    
    if(overlap || !Term_Equal(&existing->term, &incoming->term))
    {
        // CHOICE: keep the one with higher confidence
        if(incoming_updated.truth.confidence > existing_updated.truth.confidence)
            return *incoming;
    }
    else
    {
        // REVISION: merge evidence, increase activation
        Event revised_spike = Inference_EventRevision(&existing_updated, &incoming_updated);
        if(revised_spike.truth.confidence >= existing_updated.truth.confidence)
        {
            *revised = true;
            return revised_spike;
        }
    }
}
```

### 2E. OpenNARS — Implication Revision with Overlap Handling
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Inference.c` (lines 84-108)

**Pattern:** For implication rules (like "if X then Y"), when stamps overlap, keep the higher-confidence implication instead of revising:
```c
Implication Inference_ImplicationRevision(Implication *a, Implication *b)
{
    Truth T = Truth_Revision(a->truth, b->truth);
    Stamp S = conclusionStamp;
    if(Stamp_checkOverlap(&a->stamp, &b->stamp))
    {
        // Overlap: use the more confident one's truth + stamp
        if(a->truth.confidence > b->truth.confidence)
            { T = a->truth; S = a->stamp; }
        else
            { T = b->truth; S = b->stamp; }
    }
    // Weighted average of occurrence time offsets
    double avg = weighted_average(a->offset, b->offset, 
                                  Truth_c2w(a->truth.confidence), 
                                  Truth_c2w(b->truth.confidence));
    ...
}
```

### 2F. OpenNARS — Additional Truth Functions
**File:** `C:\Next AI\ref\OpenNARS-for-Applications-master\src\Truth.c`

| Function | Formula | Use Case |
|----------|---------|----------|
| `Truth_Deduction(f1,c1, f2,c2)` | f=f1*f2, c=c1*c2*f | Forward chain: A→B, B→C ⟹ A→C |
| `Truth_Induction(v1,v2)` | `Truth_Abduction(v2,v1)` | Backward: from observations infer rule |
| `Truth_Abduction(f1,c1, f2,c2)` | f=f2, c=w2c(f1*c1*c2) | Abductive inference |
| `Truth_Eternalize(v)` | f=v.f, c=w2c(v.c) | Convert temporal to eternal truth |
| `Truth_Projection(v, t1, t2)` | c = v.c * decay^|Δt| | Temporal discounting |
| `Truth_Intersection(v1,v2)` | f=f1*f2, c=c1*c2 | Conjunction |
| `Truth_Union(v1,v2)` | f=or(f1,f2), c=c1*c2 | Disjunction |
| `Truth_Negation(v1)` | f=1-f1, c=c1 | Negation |

---

## 3. Paper/Title Deduplication Patterns

### 3A. LangChain — Document Indexing Deduplication (Hash-Based)
**File:** `C:\Next AI\ref\langchain-master\libs\core\langchain_core\indexing\api.py` (lines 133-160)

**Pattern:** Hash-based deduplication preserving insertion order:
```python
def _deduplicate_in_order(hashed_documents: Iterable[Document]) -> Iterator[Document]:
    """Deduplicate a list of hashed documents while preserving order."""
    seen: set[str] = set()
    for hashed_doc in hashed_documents:
        if hashed_doc.id not in seen:
            seen.add(cast("str", hashed_doc.id))
            yield hashed_doc
```

**Hash calculation** supports multiple algorithms:
```python
def _calculate_hash(text, algorithm):
    if algorithm == "sha1":
        digest = hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()
        return str(uuid.uuid5(NAMESPACE_UUID, digest))
    if algorithm == "blake2b":
        return hashlib.blake2b(text.encode("utf-8")).hexdigest()
    ...
```

**Key takeaway:** Hash-based dedup only catches exact duplicates. For title dedup across sources (arXiv, Semantic Scholar, Crossref), you need fuzzy matching ON TOP of this.

### 3B. LangChain — Fuzzy String Distance Evaluation
**File:** `C:\Next AI\ref\langchain-master\libs\langchain\langchain_classic\evaluation\string_distance\base.py`

**Pattern:** Uses `rapidfuzz` library with 6 distance metrics for string comparison:

```python
class StringDistance(str, Enum):
    DAMERAU_LEVENSHTEIN = "damerau_levenshtein"
    LEVENSHTEIN = "levenshtein"
    JARO = "jaro"
    JARO_WINKLER = "jaro_winkler"  # DEFAULT - best for short strings like titles
    HAMMING = "hamming"
    INDEL = "indel"

# Usage:
from rapidfuzz import distance as rf_distance
metric = rf_distance.JaroWinkler.normalized_distance
score = metric("Paper Title A", "Paper Title B")  # returns 0.0 (identical) to 1.0 (max diff)
```

**For paper title dedup, recommended approach:**
1. Normalize titles (lowercase, strip punctuation, normalize whitespace)
2. Use `JaroWinkler.normalized_similarity()` — tuned for short strings, handles prefix matches well
3. Threshold at ~0.92-0.95 similarity for "same paper" detection

### 3C. Haystack — Document Joiner (Multi-Source Dedup)
**File:** `C:\Next AI\ref\haystack-main\haystack\components\joiners\document_joiner.py`

**Pattern:** Multiple strategies for merging duplicate documents from different retrievers:

```python
class JoinMode(Enum):
    CONCATENATE = "concatenate"       # Keep highest-scored duplicate
    MERGE = "merge"                   # Weighted sum of scores for duplicates
    RECIPROCAL_RANK_FUSION = "reciprocal_rank_fusion"  # RRF scoring
    DISTRIBUTION_BASED_RANK_FUSION = "distribution_based_rank_fusion"
```

**Concatenate (dedup by ID, keep best score):**
```python
@staticmethod
def _concatenate(document_lists):
    output = []
    docs_per_id = defaultdict(list)
    for doc in itertools.chain.from_iterable(document_lists):
        docs_per_id[doc.id].append(doc)
    for docs in docs_per_id.values():
        doc_with_best_score = max(docs, key=lambda doc: doc.score if doc.score else -inf)
        output.append(doc_with_best_score)
    return output
```

**Merge (weighted score combination):**
```python
def _merge(self, document_lists):
    scores_map = defaultdict(int)
    documents_map = {}
    weights = self.weights or [1/len(document_lists)] * len(document_lists)
    for documents, weight in zip(document_lists, weights):
        for doc in documents:
            scores_map[doc.id] += (doc.score if doc.score else 0) * weight
            documents_map[doc.id] = doc
    return [replace(doc, score=scores_map[doc.id]) for doc in documents_map.values()]
```

**Reciprocal Rank Fusion:**
```python
def _reciprocal_rank_fusion(self, document_lists):
    k = 61  # constant from original paper
    for rank, doc in enumerate(documents):
        scores_map[doc.id] += (weight * len(document_lists)) / (k + rank)
    # Normalize by max possible score
    for _id in scores_map:
        scores_map[_id] /= len(document_lists) / k
```

**Key takeaway for paper dedup:** The `docs_per_id` + `defaultdict(list)` pattern groups duplicates by ID. For fuzzy title matching, replace `doc.id` with a normalized title key, and use JaroWinkler similarity instead of exact match.

### 3D. Haystack — DuplicatePolicy Enum
**File:** `C:\Next AI\ref\haystack-main\haystack\components\writers\document_writer.py`

```python
class DuplicatePolicy(Enum):
    NONE = "NONE"           # Rely on DocumentStore settings
    SKIP = "SKIP"           # Skip if ID exists
    OVERWRITE = "OVERWRITE" # Overwrite existing
    FAIL = "FAIL"           # Raise error on duplicate
```

---

## 4. Rate Limiting & API Patterns

### 4A. LangChain — Token Bucket Rate Limiter
**File:** `C:\Next AI\ref\langchain-master\libs\core\langchain_core\rate_limiters.py`

**Pattern:** Thread-safe token bucket implementation, usable with any LLM or API:

```python
class InMemoryRateLimiter(BaseRateLimiter):
    def __init__(self, *,
        requests_per_second: float = 1,      # e.g., 1/10 = 0.1 for 10-second intervals
        check_every_n_seconds: float = 0.1,   # poll interval
        max_bucket_size: float = 1,           # burst capacity
    ):
        self.available_tokens = 0.0
        self._consume_lock = threading.Lock()
        self.last = None

    def _consume(self) -> bool:
        with self._consume_lock:
            now = time.monotonic()
            if self.last is None:
                self.last = now
            elapsed = now - self.last
            if elapsed * self.requests_per_second >= 1:
                self.available_tokens += elapsed * self.requests_per_second
                self.last = now
            self.available_tokens = min(self.available_tokens, self.max_bucket_size)
            if self.available_tokens >= 1:
                self.available_tokens -= 1
                return True
            return False

    def acquire(self, *, blocking: bool = True) -> bool:
        while not self._consume():
            time.sleep(self.check_every_n_seconds)
        return True

    async def aacquire(self, *, blocking: bool = True) -> bool:
        while not self._consume():
            await asyncio.sleep(self.check_every_n_seconds)
        return True
```

**Usage with chat models:**
```python
rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1,  # 1 request per 10 seconds
    check_every_n_seconds=0.1,
    max_bucket_size=10,
)
model = ChatAnthropic(model_name="...", rate_limiter=rate_limiter)
```

### 4B. LangChain — Retry with Exponential Backoff
**File:** `C:\Next AI\ref\langchain-master\libs\langchain_v1\langchain\agents\middleware\_retry.py`

```python
def calculate_delay(
    attempt: int,
    backoff_factor: float,
    max_delay: float | None = None,
) -> float:
    """Calculate delay with exponential backoff + optional jitter."""
    if backoff_factor == 0.0:
        return 0.0
    delay = backoff_factor * (2 ** attempt)
    if max_delay is not None:
        delay = min(delay, max_delay)
    return delay
```

**Key takeaway:** For Semantic Scholar API:
- Use `InMemoryRateLimiter(requests_per_second=1.0)` for unauthenticated (100 req/5min)
- Use `InMemoryRateLimiter(requests_per_second=10.0)` for authenticated (1 req/sec with key)
- Add exponential backoff on 429 responses
- API key goes in `x-api-key` header

---

## 5. Synthesis: Recommended Architecture for Our System

### Multi-Relationship Extraction
Adapt LangChain's triple extraction prompt with:
- **Constrained predicates**: Replace free-form with `cites | uses_method | extends | contradicts | improves_upon | benchmarks_against`
- **Structured output**: Use Pydantic models (like citation_fuzzy_match pattern)
- **Source grounding**: Use the `regex` fuzzy span matching to link each relationship back to source text

### Truth/Evidence System
Port OpenNARS's core model:
```python
@dataclass
class RelationshipTruth:
    frequency: float      # 0-1, how supported
    confidence: float     # 0-0.99, evidence strength
    evidential_stamp: set[int]  # source paper IDs that contributed evidence

    def revise(self, other: 'RelationshipTruth') -> 'RelationshipTruth':
        if self.evidential_stamp & other.evidential_stamp:
            # Overlap → choice (keep higher confidence)
            return self if self.confidence >= other.confidence else other
        # No overlap → merge
        w1 = self.confidence / (1 - self.confidence)
        w2 = other.confidence / (1 - other.confidence)
        w = w1 + w2
        return RelationshipTruth(
            frequency=min(1.0, (w1*self.frequency + w2*other.frequency) / w),
            confidence=min(0.99, max(w/(w+1), self.confidence, other.confidence)),
            evidential_stamp=self.evidential_stamp | other.evidential_stamp,
        )
```

### Paper Deduplication Pipeline
```python
from rapidfuzz.distance import JaroWinkler

def normalize_title(title: str) -> str:
    return re.sub(r'[^\w\s]', '', title.lower()).strip()

def deduplicate_papers(papers: list[dict]) -> list[dict]:
    groups = {}  # canonical_title → [papers]
    for paper in papers:
        norm = normalize_title(paper['title'])
        # Find best match in existing groups
        best_key, best_sim = None, 0.0
        for key in groups:
            sim = JaroWinkler.normalized_similarity(norm, key)
            if sim > best_sim:
                best_key, best_sim = key, sim
        if best_sim > 0.92:  # threshold
            groups[best_key].append(paper)
        else:
            groups[norm] = [paper]
    return [max(papers, key=lambda p: len(p.get('abstract', ''))) for papers in groups.values()]
```

### API Rate Limiting
```python
from langchain_core.rate_limiters import InMemoryRateLimiter

semantic_scholar_limiter = InMemoryRateLimiter(
    requests_per_second=1.0,  # with API key
    check_every_n_seconds=0.1,
    max_bucket_size=5,
)
```
