# P1D TEI Deployment Configuration (Frozen)

## Model identity

```
model repository        Alibaba-NLP/gte-Qwen2-1.5B-instruct
model revision          a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644
model commit etag       cac2560dd0fe9eac4e36dd2f33b83364b3c83dc3
architecture            Qwen2ForCausalLM / embedding head
parameters              1.5B
embedding dimension     1536
pooling                 last-token
dtype                   float32
nominal model capacity  32K tokens
```

## Server configuration (frozen for P1D)

```
TEI image               ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
served model name       cpu-embed
port                    8080
max-batch-tokens        8192
max-client-batch-size   1
max-concurrent-requests 2
dtype                   float32
pooling                 last-token
revision                a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644
```

### Corrections applied from review

1. **Token limit**: `max-batch-tokens 8192` — nominal model capacity is
   32K but the configured service capacity is 8,192 tokens with automatic
   truncation. Preflight must verify no frozen passage/query exceeds
   this limit.

2. **Client batch size**: `1` — the existing 81-passage preflight sends
   one passage per HTTP request. Frozen.

3. **Query protocol**: GTE-Qwen2 uses instruction-prefixed queries and
   unprefixed documents. Two explicit paths required:
   ```
   embed_query(query)     → "Instruct: Given a research question, retrieve passages relevant to answering it.\nQuery: <query>"
   embed_document(passage) → passage unchanged
   ```

4. **Image + revision pinning**: TEI image line `cpu-1.9` with model
   revision `a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644`. After first
   successful pull, pin the container digest.

5. **CPU dtype**: `--dtype float32` explicit — avoids implicit dtype
   change. Model memory ~6.62 GB before server overhead.

6. **Concurrency**: `--max-concurrent-requests 2` — conservative initial
   setting for a 1.5B fp32 CPU model. Test 1→2→4→8 before increasing.

## Frozen query instruction

```
Instruct: Given a research question, retrieve passages relevant to answering it.
Query: <query>
```

This exact string becomes part of the model identity and experimental
configuration. It is applied ONLY on the query side. Documents are sent
unchanged.

## Index isolation

The existing Nomic/Qwen3 chromadb index (`./data/chroma`) uses a
different embedding dimension. GTE-Qwen2 produces 1,536-dimensional
vectors. A separately identified index must be created:

```
provider          tei
model             Alibaba-NLP/gte-Qwen2-1.5B-instruct
revision          a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644
dimension         1536
pooling           last-token
query_protocol    instruct-v1
dtype             float32
```

The old index must NOT be overwritten until the ranking comparison
proves improvement.

## Deployment command (frozen)

```powershell
docker volume create tei-cache

docker run -d `
    --name tei-gte-qwen2 `
    --restart unless-stopped `
    -p 8080:80 `
    -v tei-cache:/data `
    ghcr.io/huggingface/text-embeddings-inference:cpu-1.9 `
    --model-id Alibaba-NLP/gte-Qwen2-1.5B-instruct `
    --revision a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644 `
    --served-model-name cpu-embed `
    --dtype float32 `
    --pooling last-token `
    --max-batch-tokens 8192 `
    --max-client-batch-size 1 `
    --max-concurrent-requests 2
```

## Expanded operational gate (P1D.3)

### A. Server identity (before corpus data)
```
TEI version                     frozen
model ID                        Alibaba-NLP/gte-Qwen2-1.5B-instruct
model revision                  a9af15a6372d7d6b25e9fb07c2ccb9e1fe645644
served model name               cpu-embed
pooling                         last-token
dtype                           float32
configured token ceiling        8192
container restart count         0
```

### B. Numerical integrity (every returned vector)
```
dimension                       1536
all values finite               yes
NaN or infinity                 0
all-zero vectors                0
input/output order preserved    yes
vector norm                     approximately 1.0 (L2 normalized)
repeated input cosine sim       >0.9999
```

### C. Operational stability
```
document passages               81 × 3 = 243/243
frozen evaluation queries       all queries × 3
HTTP 5xx                        0
timeouts                        0
container restarts              0
worker terminations             0
dimension changes               0
silent truncations              0
silent fallback                 0
median latency                  recorded
p95 latency                     recorded
maximum latency                 recorded
peak memory                     recorded
```

### D. Semantic protocol
```
documents embedded without instruction     yes
queries embedded with frozen instruction   yes
query prompt accidentally added to docs    0
unprompted evaluation queries              0
```

### E. Index isolation
```
old index untouched                yes
new index has complete identity    yes
no vector mixing                   yes
```
