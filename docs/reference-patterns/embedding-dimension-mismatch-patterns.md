# Embedding Dimension Mismatch Patterns from Reference Repos

> Research from: mem0, anything-llm, llama_index, RAG-Anything

## Summary of Patterns Found

| Pattern | Repo | Approach |
|---------|------|----------|
| **Explicit dim propagation** | mem0 | Embedder config → vector store config at init time |
| **Runtime dimension inference** | anything-llm | Infer from first chunk's vector length |
| **Insert-time validation** | mem0 (OpenSearch) | Raise ValueError on dim mismatch at insert/update |
| **Full reset on provider change** | anything-llm (pgvector) | Drop & recreate table when vector DB config changes |
| **Config-level dim override** | anything-llm (LocalAI) | `EMBEDDING_OUTPUT_DIMENSIONS` env var passed to API |
| **Pass-through (ChromaDB)** | mem0, llama_index | Let ChromaDB handle dims implicitly (no explicit dim in collection) |
| **Static dim declaration** | RAG-Anything | Hardcoded `embedding_dim=3072` in EmbeddingFunc |

---

## 1. MEM0: Explicit Dimension Propagation (Best Pattern to Copy)

### How it works
mem0 passes `embedding_dims` from the embedder config **into** the vector store config, ensuring they always match.

### File: `mem0/memory/main.py` (lines ~315-330)
```python
@staticmethod
def _process_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    if "graph_store" in config_dict:
        if "vector_store" not in config_dict and "embedder" in config_dict:
            config_dict["vector_store"] = {}
            config_dict["vector_store"]["config"] = {}
            # KEY: Propagate embedder dims → vector store dims
            config_dict["vector_store"]["config"]["embedding_model_dims"] = \
                config_dict["embedder"]["config"]["embedding_dims"]
    return config_dict
```

### File: `mem0/configs/embeddings/base.py`
```python
class BaseEmbedderConfig(ABC):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dims: Optional[int] = None,  # <-- Explicit dims
        # ...
    ):
        self.embedding_dims = embedding_dims
```

### File: `mem0/embeddings/openai.py`
```python
class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        self.config.model = self.config.model or "text-embedding-3-small"
        self.config.embedding_dims = self.config.embedding_dims or 1536  # default

    def embed(self, text, memory_action=None):
        return (
            self.client.embeddings.create(
                input=[text],
                model=self.config.model,
                dimensions=self.config.embedding_dims,  # <-- Passed to API
                encoding_format="float",
            )
            .data[0]
            .embedding
        )
```

### Vector stores receive the dims at init:
**File: `mem0/vector_stores/qdrant.py`**
```python
class Qdrant(VectorStoreBase):
    def __init__(self, collection_name, embedding_model_dims, ...):
        self.embedding_model_dims = embedding_model_dims
        self.create_col(embedding_model_dims, on_disk)

    def create_col(self, vector_size, on_disk, distance=Distance.COSINE):
        # Skip if collection already exists
        response = self.list_cols()
        for collection in response.collections:
            if collection.name == self.collection_name:
                logger.debug(f"Collection {self.collection_name} already exists.")
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance, on_disk=on_disk),
        )
```

**File: `mem0/vector_stores/pgvector.py`**
```python
class PGVector(VectorStoreBase):
    def __init__(self, ..., embedding_model_dims):
        self.embedding_model_dims = embedding_model_dims
        # SQL uses the dims directly:
        # vector vector({self.embedding_model_dims})
```

### Fallback for user identity inserts:
**File: `mem0/memory/setup.py`**
```python
dims = getattr(vector_store, "embedding_model_dims", 1536)  # safe fallback
vector_store.insert(
    vectors=[[0.1] * dims],
    payloads=[{"user_id": user_id, "type": "user_identity"}],
    ids=[user_id]
)
```

---

## 2. MEM0 OpenSearch: Insert/Update Time Dimension Validation

### File: `mem0/vector_stores/opensearch.py` (lines ~118-132)

This is the **best runtime validation pattern** to copy:

```python
def insert(self, vectors, payloads=None, ids=None):
    for idx, vec in enumerate(vectors):
        if vec is None:
            raise ValueError(
                f"Vector at index {idx} is null. "
                f"This usually means the embedding model failed to generate an embedding."
            )
        if len(vec) == 0:
            raise ValueError(
                f"Expected a vector of dimension {self.embedding_model_dims}, "
                f"got an empty vector."
            )
        # THE KEY CHECK:
        if len(vec) != self.embedding_model_dims:
            raise ValueError(
                f"Vector at index {idx} has dimension {len(vec)}, "
                f"but the index '{self.collection_name}' expects dimension "
                f"{self.embedding_model_dims}. "
                f"Ensure your embedding model's output dimensions match the "
                f"vector store configuration."
            )

def update(self, vector_id, vector=None, payload=None):
    if vector is not None:
        if len(vector) == 0:
            raise ValueError("Cannot update with an empty vector.")
        if len(vector) != self.embedding_model_dims:
            raise ValueError(
                f"Update vector has dimension {len(vector)}, "
                f"but the index '{self.collection_name}' expects dimension "
                f"{self.embedding_model_dims}. "
                f"Ensure your embedding model's output dimensions match the "
                f"vector store configuration."
            )
```

---

## 3. ANYTHING-LLM: Runtime Dimension Inference from First Chunk

### File: `server/utils/vectorDbProviders/qdrant/index.js` (lines ~138-182)

```javascript
// QDrant requires a dimension aspect for collection creation
// we pass this in from the first chunk to infer the dimensions
async getOrCreateCollection(client, namespace, dimensions = null) {
    if (await this.namespaceExists(client, namespace)) {
      return await client.getCollection(namespace);
    }
    if (!dimensions)
      throw new Error(
        `Qdrant:getOrCreateCollection Unable to infer vector dimension from input.`
      );
    await client.createCollection(namespace, {
      vectors: { size: dimensions, distance: "Cosine" },
    });
    return await client.getCollection(namespace);
}

async addDocumentToNamespace(namespace, documentData, ...) {
    let vectorDimension = null;

    // From cached vectors:
    vectorDimension =
        chunks[0][0]?.vector?.length ??
        chunks[0][0]?.values?.length ??
        null;

    // From fresh embeddings:
    for (const [i, vector] of vectorValues.entries()) {
        if (!vectorDimension) vectorDimension = vector.length;  // <-- infer from first vector
        // ...
    }

    const collection = await this.getOrCreateCollection(
        client, namespace, vectorDimension
    );
}
```

### Same pattern in Milvus provider:
**File: `server/utils/vectorDbProviders/milvus/index.js`**
```javascript
async getOrCreateCollection(client, namespace, dimensions = null) {
    const exists = await this.namespaceExists(client, namespace);
    if (exists) return client.getCollectionStats(namespace);
    if (!dimensions)
      throw new Error(`Unable to infer vector dimension from input.`);
    await client.createCollection({
        collection_name: namespace,
        fields: [
            { name: "id", dtype: "VarChar", max_length: 128, is_primary_key: true },
            { name: "vector", dtype: "FloatVector", dim: dimensions },
            { name: "metadata", dtype: "JSON" },
        ],
    });
}
```

---

## 4. ANYTHING-LLM: Full Reset on Vector DB Config Change

### File: `server/utils/vectorStore/resetAllVectorStores.js`

```javascript
async function resetAllVectorStores({ vectorDbKey }) {
    const workspaces = await Workspace.where();
    purgeEntireVectorCache();
    await DocumentVectors.delete();
    await Document.delete();

    const VectorDb = getVectorDbClass(vectorDbKey);

    if (vectorDbKey === "pgvector") {
      /*
      pgvector has a reset method that drops the entire embedding table
      which is required since if this function is called we will need to
      reset the embedding column VECTOR dimension value and you cannot change
      the dimension value of an existing vector column.
      */
      await VectorDb.reset();
    } else {
      for (const workspace of workspaces) {
        await VectorDb["delete-namespace"]({ namespace: workspace.slug });
      }
    }
}
```

---

## 5. ANYTHING-LLM: Configurable Output Dimensions via Env Var

### File: `server/utils/EmbeddingEngines/localAi/index.js`

```javascript
class LocalAiEmbedder {
    get outputDimensions() {
        if (
            process.env.EMBEDDING_OUTPUT_DIMENSIONS &&
            !isNaN(process.env.EMBEDDING_OUTPUT_DIMENSIONS) &&
            process.env.EMBEDDING_OUTPUT_DIMENSIONS > 0
        )
            return parseInt(process.env.EMBEDDING_OUTPUT_DIMENSIONS);
        return null;
    }

    async embedChunks(textChunks = []) {
        this.openai.embeddings.create({
            model: this.model,
            input: chunk,
            dimensions: this.outputDimensions,  // <-- Passed to API (null = use model default)
        })
    }
}
```

### File: `server/utils/helpers/updateENV.js`
```javascript
EmbeddingOutputDimensions: {
    envKey: "EMBEDDING_OUTPUT_DIMENSIONS",
},
```

### File: `server/models/systemSettings.js`
```javascript
EmbeddingOutputDimensions: process.env.EMBEDDING_OUTPUT_DIMENSIONS || null,
```

---

## 6. ANYTHING-LLM PGVector: Table Schema Validation

### File: `server/utils/vectorDbProviders/pgvector/index.js`

```javascript
createTableSql(dimensions) {
    return `CREATE TABLE IF NOT EXISTS "${PGVector.tableName()}" 
      (id UUID PRIMARY KEY, namespace TEXT, 
       embedding vector(${Number(dimensions)}), 
       metadata JSONB, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`;
}

async createTableIfNotExists(connection, dimensions = 384) {
    this.logger(`Creating embedding table with ${dimensions} dimensions`);
    await connection.query(this.createTableSql(dimensions));
}

// When inserting:
let vectorDimensions;
if (!vectorDimensions) vectorDimensions = chunk.values.length;  // infer from data

// Then create table with those dims:
await this.createTableIfNotExists(connection, vectorDimensions);
```

### Schema validation for existing tables:
```javascript
async validateExistingEmbeddingTableSchema(pgClient, tableName) {
    const result = await pgClient.query(this.getEmbeddingTableSchemaSql, [tableName]);
    const expectedSchema = [
        { column_name: "id", expected: "uuid" },
        { column_name: "namespace", expected: "text" },
        { column_name: "embedding", expected: "vector" },  // checks type but NOT dimension
        { column_name: "metadata", expected: "jsonb" },
        { column_name: "created_at", expected: "timestamp" },
    ];
    // Validates columns exist and have correct types
}
```

---

## 7. MEM0 ChromaDB: No Explicit Dimension (Pass-through)

### File: `mem0/vector_stores/chroma.py`

ChromaDB infers dimensions from the first vector inserted. mem0 does NOT set explicit dims:

```python
class ChromaDB(VectorStoreBase):
    def __init__(self, collection_name, client=None, host=None, port=None, 
                 path=None, api_key=None, tenant=None):
        # NOTE: No embedding_model_dims parameter!
        self.collection = self.create_col(collection_name)

    def create_col(self, name, embedding_fn=None):
        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
            # No dimension specification — ChromaDB infers from first insert
        )
        return collection

    def insert(self, vectors, payloads=None, ids=None):
        self.collection.add(ids=ids, embeddings=vectors, metadatas=payloads)
        # ChromaDB will error here if dimensions mismatch the collection
```

---

## 8. LLAMA_INDEX ChromaDB: Also No Explicit Dimension

### File: `llama-index-vector-stores-chroma/llama_index/vector_stores/chroma/base.py`

```python
class ChromaVectorStore(BasePydanticVectorStore):
    def __init__(self, chroma_collection=None, collection_name=None, ...):
        if chroma_collection is None:
            client = chromadb.HttpClient(host=host, port=port)
            self._collection = client.get_or_create_collection(
                name=collection_name, **collection_kwargs
                # No dimension param — ChromaDB handles it
            )

    def add(self, nodes, **add_kwargs):
        embeddings = [node.get_embedding() for node in nodes]
        self._collection.add(embeddings=embeddings, ids=ids, ...)
        # If dimensions mismatch, ChromaDB raises error
```

---

## 9. RAG-Anything: Static Dimension Declaration

### File: `examples/ollama_integration_example.py`

```python
OLLAMA_EMBEDDING_DIM = int(os.getenv("OLLAMA_EMBEDDING_DIM", "768"))

class OllamaRAGIntegration:
    def __init__(self):
        self.embedding_dim = OLLAMA_EMBEDDING_DIM

    def _make_embedding_func(self):
        return EmbeddingFunc(
            embedding_dim=self.embedding_dim,
            max_token_size=8192,
            func=ollama_embedding_async,
        )

    async def test_embedding(self):
        vectors = await ollama_embedding_async(["hello world"])
        if len(vectors[0]) != self.embedding_dim:
            print(
                f"⚠️  Dimension mismatch!  Set "
                f"OLLAMA_EMBEDDING_DIM={len(vectors[0])} in your .env"
            )
```

### File: `reproduce/index.py`
```python
embedding_func = EmbeddingFunc(
    embedding_dim=3072,  # Hardcoded for text-embedding-3-large
    max_token_size=8192,
    func=lambda texts: openai_embed(texts, model="text-embedding-3-large", ...),
)
```

---

## Recommended Patterns for Elephant Rock Platform

### Pattern 1: Centralized Dimension Config (from mem0)
**Best for:** Ensuring embedder and vector store always agree.

```python
# In your config/settings:
class EmbeddingConfig:
    model: str = "text-embedding-3-small"
    dimensions: int = 1536  # Single source of truth

# Propagate at init:
vector_store_config.embedding_model_dims = embedding_config.dimensions
```

### Pattern 2: Insert-Time Validation (from mem0 OpenSearch)
**Best for:** Catching mismatches early with clear error messages.

```python
def insert(self, vectors, payloads=None, ids=None):
    for idx, vec in enumerate(vectors):
        if len(vec) != self.embedding_model_dims:
            raise ValueError(
                f"Dimension mismatch: vector has {len(vec)} dims, "
                f"but collection expects {self.embedding_model_dims}. "
                f"This usually means the embedding model changed. "
                f"Either re-embed all documents or create a new collection."
            )
```

### Pattern 3: Runtime Inference from First Embedding (from anything-llm)
**Best for:** When you don't know dimensions at config time.

```python
async def get_or_create_collection(self, name, dimensions=None):
    if await self.collection_exists(name):
        return await self.get_collection(name)
    if not dimensions:
        raise ValueError("Cannot infer dimensions — provide explicit dimension or insert a vector first")
    await self.create_collection(name, vector_size=dimensions)
```

### Pattern 4: Full Reset on Provider Change (from anything-llm)
**Best for:** When embedding model changes are detected.

```python
async def handle_embedding_model_change(self, old_dims, new_dims):
    if old_dims != new_dims:
        logger.warning(
            f"Embedding dimension changed: {old_dims} → {new_dims}. "
            f"All vector data must be re-indexed."
        )
        await self.drop_all_collections()
        await self.recreate_collections(new_dims)
```

### Pattern 5: ChromaDB-Specific (Dimension-Aware Collection)
ChromaDB does NOT accept a dimension param in `get_or_create_collection`. It infers dimensions from the first insert. If you need to validate:

```python
def get_collection_dimension(self, collection_name):
    """Get the dimension of an existing ChromaDB collection."""
    collection = self.client.get_collection(name=collection_name)
    # Peek at existing data to determine dimension
    peek = collection.peek()
    if peek["embeddings"] and len(peek["embeddings"]) > 0:
        return len(peek["embeddings"][0])
    return None  # Empty collection — no dimension yet

def validate_before_insert(self, collection_name, vectors):
    existing_dim = self.get_collection_dimension(collection_name)
    if existing_dim and len(vectors[0]) != existing_dim:
        raise ValueError(
            f"Collection '{collection_name}' has dimension {existing_dim}, "
            f"but new vectors have dimension {len(vectors[0])}. "
            f"You must delete and recreate the collection, or use a different collection."
        )
```
