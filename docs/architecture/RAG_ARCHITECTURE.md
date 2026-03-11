# RAG (Retrieval-Augmented Generation) Architecture

## Overview

The RAG subsystem provides semantic search capabilities over document collections, enabling prompts to retrieve relevant context rather than injecting entire documents. This improves response quality and reduces token usage for large document libraries.

## Design Goals

1. **Semantic Search** - Find relevant content based on meaning, not just keywords
2. **Token Efficiency** - Retrieve only relevant chunks instead of entire documents
3. **Provider Flexibility** - Support multiple embedding providers via LiteLLM
4. **Seamless Integration** - Work alongside existing document reference system
5. **MCP Tooling** - Expose search capabilities for AI assistants

## Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAG SUBSYSTEM                                    │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      FFRAGClient                                 │   │
│   │  - High-level RAG interface                                     │   │
│   │  - add_document(), search(), format_results_for_prompt()        │   │
│   │  - Coordinates text splitting and vector storage                │   │
│   └──────────────────────────────┬──────────────────────────────────┘   │
│                                  │                                       │
│            ┌─────────────────────┴─────────────────────┐                │
│            │                                           │                 │
│            ▼                                           ▼                 │
│   ┌─────────────────┐                      ┌─────────────────────┐      │
│   │  TextSplitter   │                      │   FFVectorStore     │      │
│   │                 │                      │                     │      │
│   │ - split_text()  │                      │ - add_chunks()      │      │
│   │ - split_docs()  │                      │ - search()          │      │
│   │ - TextChunk     │                      │ - delete_by_ref()   │      │
│   └─────────────────┘                      │ - list_documents()  │      │
│                                            └──────────┬──────────┘      │
│                                                       │                  │
│                                                       ▼                  │
│                                            ┌─────────────────────┐      │
│                                            │    FFEmbeddings     │      │
│                                            │                     │      │
│                                            │ - embed()           │      │
│                                            │ - embed_single()    │      │
│                                            │ - LiteLLM backend   │      │
│                                            └─────────────────────┘      │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      RAGMCPTools                                 │   │
│   │  - rag_search(), rag_add_document(), rag_list_documents()       │   │
│   │  - rag_get_stats(), rag_delete_document()                       │   │
│   │  - get_tool_definitions() for MCP integration                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Used by
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR INTEGRATION                              │
│                                                                          │
│   DocumentProcessor                                                      │
│   - _index_to_rag() indexes documents when loaded                       │
│   - get_document_content() indexes cached docs                          │
│                                                                          │
│   DocumentRegistry                                                       │
│   - semantic_search() retrieves relevant chunks                         │
│   - inject_semantic_query() formats and injects context                 │
│   - Works alongside full document injection (references column)         │
│                                                                          │
│   ExcelOrchestrator                                                      │
│   - Initializes RAG client in _init_documents()                         │
│   - Handles semantic_query column in prompts                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/RAG/
├── __init__.py                  # Exports all RAG components
├── text_splitter.py             # DEPRECATED - backward compatibility wrapper
├── FFEmbeddings.py              # LiteLLM embedding wrapper with caching
│                               # - embed(texts) -> list[list[float]]
│                               # - embed_single(text) -> list[float]
│                               # - Supports: mistral, openai, azure, anthropic
│                               # - Local models: local/all-MiniLM-L6-v2
│                               # - LRU cache for repeated queries
├── FFVectorStore.py             # ChromaDB operations
│                               # - add_chunks(chunks) -> int
│                               # - add_documents(documents) -> int
│                               # - search(query, n_results) -> list[dict]
│                               # - delete_by_reference(reference_name)
│                               # - list_documents() -> list[str]
│                               # - get_stats() -> dict
│                               # - clear()
├── FFRAGClient.py               # High-level RAG interface
│                               # - add_document(content, reference_name, metadata)
│                               # - search(query, n_results) -> list[dict]
│                               # - format_results_for_prompt(results, max_chars)
│                               # - search_and_format(query, n_results, max_chars)
│                               # - delete_by_reference(reference_name)
│                               # - get_stats() -> dict
│                               # - Per-prompt overrides (query_expansion, rerank, semantic_filter)
├── mcp_tools.py                 # MCP tool definitions
│                               # - rag_search(query, n_results)
│                               # - rag_add_document(content, reference_name)
│                               # - rag_list_documents()
│                               # - rag_get_stats()
│                               # - rag_delete_document(reference_name)
├── text_splitters/              # Chunking strategies
│   ├── __init__.py              # Exports all chunkers + factory
│   ├── base.py                  # ChunkerBase, TextChunk, HierarchicalTextChunk
│   ├── character.py             # CharacterChunker - word-boundary aware
│   ├── recursive.py             # RecursiveChunker - hierarchical separators
│   ├── markdown.py              # MarkdownChunker - header-aware
│   ├── code.py                  # CodeChunker - AST-style for code
│   ├── hierarchical.py          # HierarchicalChunker - parent-child
│   └── factory.py               # get_chunker(), list_chunkers(), chunk_text()
├── indexing/                    # Index implementations
│   ├── __init__.py              # Exports all index types
│   ├── bm25_index.py            # BM25Index - sparse keyword index
│   ├── hierarchical_index.py    # HierarchicalIndex - parent-child storage
│   ├── contextual_embeddings.py # ContextualEmbeddings, LateChunkingEmbeddings
│   └── deduplication.py         # ChunkDeduplicator - exact & similarity dedup
└── search/                      # Search strategies
    ├── __init__.py              # Exports all search components
    ├── hybrid_search.py         # HybridSearch, reciprocal_rank_fusion
    ├── rerankers.py             # CrossEncoderReranker, DiversityReranker, NoopReranker
    └── query_expansion.py       # QueryExpander, fuse_search_results
```

## Configuration

### RAGConfig (src/config.py)

```python
class RAGConfig(BaseModel):
    """RAG configuration settings."""

    enabled: bool = True
    persist_dir: str = "./chroma_db"
    collection_name: str = "plico_documents"
    embedding_model: str = "mistral/mistral-embed"
    local_embeddings: bool = False
    embedding_cache_size: int = 256
    generate_summaries: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200
    n_results_default: int = 5
```

### RAGChunkingConfig

```python
class RAGChunkingConfig(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    contextual_headers: bool = True
    dedup_enabled: bool = False
    dedup_mode: str = "exact"  # or "similarity"
```

### RAGSearchConfig

```python
class RAGSearchConfig(BaseModel):
    mode: str = "vector"
    hybrid_alpha: float = 0.6
    rerank: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    query_expansion: bool = False
    query_expansion_variations: int = 3
    summary_boost: float = 1.5
```

### config/main.yaml

```yaml
rag:
  enabled: true
  persist_dir: "./chroma_db"
  collection_name: "plico_kb"
  embedding_model: "mistral/mistral-embed"
  local_embeddings: false
  embedding_cache_size: 256
  generate_summaries: false

  chunking:
    strategy: "recursive"
    chunk_size: 1000
    chunk_overlap: 200
    contextual_headers: true
    dedup_enabled: false
    dedup_mode: "exact"

  search:
    mode: "vector"
    hybrid_alpha: 0.6
    rerank: false
    rerank_model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
    query_expansion: false
    query_expansion_variations: 3
    summary_boost: 1.5
```

## Data Flow

### Pre-Indexing Flow (Orchestrator Startup)

```
ExcelOrchestrator.run()
         │
         ▼
DocumentRegistry.__init__()
         │
         ▼
DocumentRegistry.index_all_documents()
         │
         ├──► For each document in documents sheet:
         │    │
         │    ├──► DocumentProcessor.get_document_checksum()
         │    │
         │    ├──► FFRAGClient.needs_reindex(reference_name, checksum)
         │    │
         │    └──► If needs reindex:
         │         │
         │         ├──► FFRAGClient.delete_by_reference_and_type()
         │         │
         │         └──► DocumentProcessor.index_to_rag()
         │
         ▼
    All documents pre-indexed and searchable
```

### Document Indexing Flow (Single Document)

```
DocumentProcessor.index_to_rag()
         │
         ▼
┌─────────────────────────┐
│   FFRAGClient           │
│   .index_document()     │
└───────────┬─────────────┘
            │
            ├─── get_chunker(strategy) ───► Chunker
            │
            ├─── chunker.split_text() ───► TextChunks
            │
            ▼
┌─────────────────────────┐
│   FFVectorStore         │
│   .add_chunks()         │
│   (with chunking_strategy,   │
│    document_checksum)   │
└───────────┬─────────────┘
            │
            ├─── FFEmbeddings.embed(chunks) ───► vectors
            │
            ▼
┌─────────────────────────┐
│   ChromaDB              │
│   collection.add()      │
└─────────────────────────┘
```

### Semantic Search Flow

```
Prompt with semantic_query="authentication methods"
         │
         ▼
┌─────────────────────────────────┐
│   DocumentRegistry              │
│   .inject_semantic_query()      │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   DocumentRegistry              │
│   .semantic_search(query)       │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   FFRAGClient                   │
│   .search(query, n_results)     │
└───────────────┬─────────────────┘
                │
                ├─── FFEmbeddings.embed_single(query) ───► query_vector
                │
                ▼
┌─────────────────────────────────┐
│   FFVectorStore                 │
│   .search(query_vector)         │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   ChromaDB                      │
│   collection.query()            │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   Results:                      │
│   [{content, metadata, score}]  │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   FFRAGClient                   │
│   .format_results_for_prompt()  │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   Formatted Context:            │
│   <RELEVANT_CONTEXT>            │
│   [1] (source: doc1) 0.85       │
│   Relevant content here...      │
│   </RELEVANT_CONTEXT>           │
└─────────────────────────────────┘
```

## Workbook Integration

### prompts Sheet with semantic_query

| sequence | prompt_name | prompt | semantic_query | references |
|----------|-------------|--------|----------------|------------|
| 1 | context | I run a coffee shop... | | |
| 2 | search | What are the key points? | `coffee shop best practices` | |
| 3 | full_doc | Summarize this document | | `["product_spec"]` |
| 4 | hybrid | Based on the docs and search | `pricing strategies` | `["api_guide"]` |

### Column Behavior

| Column | Behavior |
|--------|----------|
| `references` | Full document injection (existing behavior) |
| `semantic_query` | RAG search for relevant chunks |
| Both | Both full docs + relevant chunks injected |
| Neither | No document context added |

### Context Injection Format

When `semantic_query` is present:

```xml
<RELEVANT_CONTEXT>
[1] (source: product_spec) Score: 0.85
The authentication system uses OAuth 2.0 with refresh tokens...

[2] (source: api_guide) Score: 0.78
API endpoints require Bearer token authentication...
</RELEVANT_CONTEXT>

===
[original prompt]
```

When both `references` and `semantic_query` are present:

```xml
<REFERENCES>
<DOC name='product_spec'>
Full document content here...
</DOC>
</REFERENCES>

<RELEVANT_CONTEXT>
[1] (source: api_guide) Score: 0.82
Relevant excerpt from search...
</RELEVANT_CONTEXT>

===
Based on the documents above and relevant context, please answer:
[original prompt]
```

## ChromaDB Storage

### Collection Schema

| Field | Type | Description |
|-------|------|-------------|
| id | string | `{reference_name}_{chunk_index}_{unique}` |
| document | string | Chunk text content |
| embedding | vector | Embedding vector (dimension depends on model) |
| metadata | object | Additional metadata |

### Metadata Fields

| Field | Description |
|-------|-------------|
| `reference_name` | Document identifier |
| `common_name` | Human-readable document name |
| `tags` | Comma-separated tags for filtering (e.g., `api,authentication`) |
| `chunking_strategy` | Chunking strategy used (recursive, markdown, code, hierarchical, character) - **auto-inferred from file extension** |
| `document_checksum` | SHA256 hash of original document content |
| `indexed_at` | ISO timestamp when document was indexed |
| `_chunk_index` | Index within document |
| `_start_char` | Start position in original text |
| `_end_char` | End position in original text |
| (custom) | Any additional metadata passed |

### Automatic Chunking Strategy Inference

The chunking strategy is automatically inferred from the document's file extension:

| Extension | Strategy | Description |
|-----------|----------|-------------|
| `.md` | `markdown` | Header-aware chunking, preserves document structure |
| `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.h`, `.rb`, `.php`, `.swift`, `.kt` | `code` | AST-style chunking, function-aware |
| All others | `recursive` | General-purpose hierarchical chunking |

This inference happens at document load time in `WorkbookParser._infer_chunking_strategy()`.

### Persistence

```
chroma_db/
├── chroma.sqlite3           # Metadata and index
└── {collection_id}/         # Vector data
    ├── data_level0.bin
    ├── data_level1.bin
    └── ...
```

## Pre-Indexing System

### Overview

Documents are automatically pre-indexed at orchestrator startup, not lazily when referenced. This ensures all documents in the `documents` sheet are searchable immediately.

### Index Tracking

Each chunk in ChromaDB includes metadata for tracking:

| Metadata Field | Description |
|----------------|-------------|
| `chunking_strategy` | Chunking strategy used (recursive, markdown, code, hierarchical, character) |
| `document_checksum` | SHA256 hash of document content |
| `indexed_at` | ISO timestamp when document was indexed |
| `reference_name` | Document identifier |
| `tags` | Comma-separated tags from documents sheet |
| `common_name` | Human-readable document name |
| `tags` | Comma-separated tags for filtering |
| `chunking_strategy` | Chunking strategy used (auto-inferred from file extension) |
| `document_checksum` | SHA256 hash of document content |
| `indexed_at` | ISO timestamp when document was indexed |
| `_chunk_index` | Index within document |
| `_start_char` | Start position in original text |
| `_end_char` | End position in original text |

### Reindexing Logic

Documents are reindexed when:
1. Document content changes (checksum mismatch)
2. Chunking strategy changes (different `chunking_strategy`)
3. Manual rebuild requested via invoke task

### Flow

```
ExcelOrchestrator.run()
         │
         ▼
DocumentRegistry.__init__()
         │
         ▼
DocumentRegistry.index_all_documents()
         │
         ├──► For each document in documents sheet:
         │    │
         │    ├──► DocumentProcessor.get_document_checksum()
         │    │
         │    ├──► FFRAGClient.needs_reindex(reference_name, checksum)
         │    │         │
         │    │         └──► FFVectorStore.get_indexed_documents()
         │    │                   .filter(checksum != current)
         │    │
         │    └──► If needs reindex:
         │         │
         │         ├──► FFRAGClient.delete_by_reference_and_type()
         │         │
         │         └──► DocumentProcessor.index_to_rag()
         │                   │
         │                   └──► FFRAGClient.index_document()
         │                             │
          │                             └──► FFVectorStore.add_chunks(chunking_strategy, checksum)
         │
         ▼
    Orchestrator continues with all documents pre-indexed
```

## Index Management Tasks

The following invoke tasks are available for managing RAG indexes:

### List Index Status

```bash
inv rag.status
```

Shows:
- Total chunk count
- Indexed documents by reference name
- Index types in use
- Last indexed timestamps

### Clear All Indexes

```bash
inv rag.clear
```

Removes all chunks from the vector store. Use with caution.

### Clear Specific Chunking Strategy

```bash
inv rag.clear-strategy recursive
inv rag.clear-strategy markdown
```

Removes only chunks with the specified `chunking_strategy`. Useful when changing chunking strategies.

### Rebuild Indexes

```bash
inv rag.rebuild
```

Clears all indexes and reindexes all documents from the configured workbook.

### View RAG Statistics

```bash
inv rag.stats
```

Shows detailed statistics about the RAG system configuration and current state.

## Invoke Task Reference

| Task | Description |
|------|-------------|
| `inv rag.status` | Show indexed documents and index types |
| `inv rag.clear` | Clear all indexes (destructive) |
| `inv rag.clear-strategy <type>` | Clear specific index type only |
| `inv rag.rebuild` | Rebuild all indexes from workbook |
| `inv rag.stats` | Show RAG configuration and statistics |

## MCP Tools

The RAG subsystem exposes tools for AI assistants via the MCP (Model Context Protocol) interface.

### Tool Definitions

```python
tools = [
    {
        "name": "rag_search",
        "description": "Search the RAG knowledge base for relevant documents",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "n_results": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "rag_add_document",
        "description": "Add a document to the RAG knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "reference_name": {"type": "string"},
                "metadata": {"type": "object"}
            },
            "required": ["content", "reference_name"]
        }
    },
    # ... rag_list_documents, rag_get_stats, rag_delete_document
]
```

### Usage Example

```python
from src.RAG import RAGMCPTools, FFRAGClient

rag_client = FFRAGClient(persist_dir="./chroma_db")
mcp_tools = RAGMCPTools(rag_client=rag_client)

# Execute tools
results = mcp_tools.execute_tool("rag_search", {"query": "authentication"})
definitions = mcp_tools.get_tool_definitions()
```

## Embedding Models

### Supported Providers (via LiteLLM)

| Provider | Model String | Dimension |
|----------|--------------|-----------|
| Mistral | `mistral/mistral-embed` | 1024 |
| OpenAI | `openai/text-embedding-3-small` | 1536 |
| OpenAI | `openai/text-embedding-3-large` | 3072 |
| Azure | `azure/{deployment-name}` | varies |

### Local Models (sentence-transformers)

| Model | Dimension | Speed | Quality |
|-------|-----------|-------|---------|
| `local/all-MiniLM-L6-v2` | 384 | Fast | Good |
| `local/all-mpnet-base-v2` | 768 | Medium | Better |
| `local/multi-qa-MiniLM-L6-cos-v1` | 384 | Fast | QA-optimized |

```python
# Zero API cost with local models
embeddings = FFEmbeddings(model="local/all-MiniLM-L6-v2")
```

### API Key Configuration

```bash
# Mistral (default)
export MISTRAL_API_KEY="your-key"

# OpenAI
export OPENAI_API_KEY="your-key"

# Azure
export AZURE_OPENAI_API_KEY="your-key"
```

### Environment-Based Selection

```python
# Automatic based on model prefix
embeddings = FFEmbeddings(model="openai/text-embedding-3-small")
# Uses OPENAI_API_KEY

embeddings = FFEmbeddings(model="mistral/mistral-embed")
# Uses MISTRAL_API_KEY
```

## Text Splitting

### Chunking Strategy

The text splitter uses a sliding window approach with word-boundary awareness:

```python
def split_text(
    text: str,
    chunk_size: int = 1000,      # Max characters per chunk
    chunk_overlap: int = 200,     # Overlap between chunks
    metadata: dict | None = None  # Metadata attached to each chunk
) -> list[TextChunk]:
```

### TextChunk Dataclass

```python
@dataclass
class TextChunk:
    content: str           # Chunk text
    chunk_index: int       # Index in sequence
    start_char: int        # Start position in original
    end_char: int          # End position in original
    metadata: dict | None  # Optional metadata
```

### Example

```python
from src.RAG import split_text

text = "Long document content..."
chunks = split_text(
    text,
    chunk_size=500,
    chunk_overlap=100,
    metadata={"source": "doc.pdf", "author": "John"}
)

# chunks[0].content -> First 500 chars (approximately)
# chunks[1].content -> Overlaps 100 chars with chunks[0]
```

## Error Handling

| Error | Behavior |
|-------|----------|
| ChromaDB not installed | `CHROMADB_AVAILABLE = False`, RAG disabled |
| Missing API key | `ValueError` on embed() call |
| Empty document | Returns 0 chunks, logs warning |
| Search on empty collection | Returns empty list |
| Invalid reference name | Silently handled by ChromaDB |

## Testing

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| text_splitter | 7 | split_text, split_documents, edge cases |
| FFEmbeddings | 6 | init, embed, error handling |
| FFVectorStore | 8 | CRUD operations, search |
| FFRAGClient | 9 | High-level operations |
| RAGMCPTools | 7 | Tool execution |
| Integration | 3 | DocumentRegistry integration |
| RAG Enhancements | 27 | Query expansion, deduplication, per-prompt overrides |

## Dependencies

```
FFRAGClient
├── FFVectorStore
│   ├── chromadb (external)
│   └── FFEmbeddings
│       └── litellm (external)
├── text_splitter (internal)
└── config (internal)

RAGMCPTools
└── FFRAGClient
```

### pyproject.toml

```toml
dependencies = [
    # ... existing dependencies
    "chromadb>=1.5.0,<2.0.0",
]
```

## Python Version Compatibility

| Version | ChromaDB | Status |
|---------|----------|--------|
| 3.11 | v1.x Compatible | Supported |
| 3.12 | v1.x Compatible | Supported |
| 3.13 | v1.x Compatible | Supported |
| 3.14 | v1.x Compatible | Supported |

ChromaDB v1.x now supports pydantic v2, enabling compatibility with all Python versions 3.11+.

### Running Tests

```bash
# Run RAG tests
pytest tests/test_rag.py -v

# Run RAG enhancement tests
pytest tests/test_rag_enhancements.py -v

# Run with coverage
pytest tests/test_rag.py --cov=src/RAG --cov-report=term-missing
```

```python
from src.RAG import HybridSearch, BM25Index

# Create hybrid search
hybrid = HybridSearch(
    vector_search_fn=vector_search,
    bm25_search_fn=bm25_search,
    alpha=0.6
)
results = hybrid.search("query", n_results=10, mode="hybrid")
```

### 2. Re-ranking (Implemented)

Post-retrieval relevance scoring using cross-encoders or diversity promotion.

```yaml
rag:
  search:
    rerank: true
    rerank_model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

```python
from src.RAG.search import get_reranker, DiversityReranker

# Diversity reranking
reranker = DiversityReranker(lambda_param=0.7)
reranked = reranker.rerank(query, results, n_results=5)
```

### 3. Multiple Chunking Strategies (Implemented)

```python
from src.RAG.text_splitters import get_chunker, chunk_text

# Recursive chunking (default)
chunker = get_chunker("recursive", chunk_size=1000, chunk_overlap=200)

# Markdown-aware chunking
md_chunker = get_chunker("markdown", split_headers=["h1", "h2"])

# Code-aware chunking
code_chunker = get_chunker("code", language="python", split_by="function")

# Hierarchical chunking (parent-child)
hier_chunker = get_chunker("hierarchical", chunk_size=400, parent_chunk_size=1500)

# Chunk text with one call
chunks = chunk_text(text, strategy="markdown", chunk_size=500)
```

### 4. Hierarchical Indexing (Implemented)

Parent-child chunk relationships for context-aware retrieval.

```yaml
rag:
  hierarchical:
    enabled: true
    parent_context: true
    parent_chunk_size: 1500
```

```python
from src.RAG.indexing import HierarchicalIndex

index = HierarchicalIndex(include_parent_context=True)
index.add_chunk(child_id, content, parent_id=parent_id, hierarchy_level=1)

# Get parent context for retrieved children
enhanced = index.enhance_results_with_context(search_results)
```

## Future Enhancements

1. **Multi-collection** - Separate collections by topic/domain
2. **Streaming** - Stream search results for large datasets

## RAG Enhancements (v2)

### 5. Embedding Cache (Implemented)

LRU cache for repeated embedding queries to reduce API costs and latency.

```yaml
rag:
  embedding_cache_size: 256  # Maximum cached embeddings
```

```python
from src.RAG import FFEmbeddings

embeddings = FFEmbeddings(
    model="mistral/mistral-embed",
    cache_enabled=True,
    cache_size=256
)

# First call hits API, second call returns cached result
vec1 = embeddings.embed_single("hello world")
vec2 = embeddings.embed_single("hello world")  # Cached
```

### 6. Local Embeddings (Implemented)

Use sentence-transformers for zero API cost embeddings.

```yaml
rag:
  embedding_model: "local/all-MiniLM-L6-v2"
  local_embeddings: true
```

```python
from src.RAG import FFEmbeddings

# Local model (no API key required)
local = FFEmbeddings(
    model="local/all-MiniLM-L6-v2",
    device="cpu"  # or "cuda" for GPU
)
vectors = local.embed(["Hello world"])
```

Supported local models:
- `local/all-MiniLM-L6-v2` - Fast, 384 dimensions
- `local/all-mpnet-base-v2` - Better quality, 768 dimensions
- `local/multi-qa-MiniLM-L6-cos-v1` - Optimized for QA

### 7. Query Expansion (Implemented)

Multi-query retrieval via LLM-generated variations for improved recall.

```yaml
rag:
  search:
    query_expansion: true
    query_expansion_variations: 3
```

```python
from src.RAG.search import QueryExpander, fuse_search_results

expander = QueryExpander(
    llm_generate_fn=my_llm.generate,
    n_variations=3,
    include_original=True
)

# "authentication methods" -> ["authentication methods", "How to authenticate?", "What are auth options?"]
queries = expander.expand("authentication methods")

# Search with all variations
all_results = [rag_client.search(q) for q in queries]
fused = fuse_search_results(all_results, n_results=10)
```

### 8. Chunk Deduplication (Implemented)

Detect and filter duplicate/near-duplicate chunks during indexing.

```yaml
rag:
  chunking:
    dedup_enabled: true
    dedup_mode: "exact"  # or "similarity"
```

```python
from src.RAG.indexing import ChunkDeduplicator

# Exact deduplication (hash-based)
dedup = ChunkDeduplicator(mode="exact")

# Similarity-based deduplication
dedup_sim = ChunkDeduplicator(mode="similarity", similarity_threshold=0.95)

# Filter duplicates
filtered_chunks, filtered_embeddings = dedup.filter_duplicates(chunks, embeddings)
```

### 9. Document Summaries (Implemented)

Auto-generated summary chunks for better document discovery.

```yaml
rag:
  generate_summaries: true
  search:
    summary_boost: 1.5  # Boost score for summary matches
```

When enabled, a summary chunk is generated for each document, allowing high-level searches to find relevant documents before drilling into specific chunks.

### 10. Contextual Headers (Implemented)

Prepend document context to chunks for better retrieval context.

```yaml
rag:
  chunking:
    contextual_headers: true
```

Transforms:
```
Original chunk: "The API supports OAuth 2.0 authentication..."

With contextual header:
"[Document: api_guide.md | Section: Authentication | Chunk 5/12]
The API supports OAuth 2.0 authentication..."
```

### 11. Per-Prompt RAG Overrides (Implemented)

Override RAG settings per prompt via workbook columns.

| Column | Values | Description |
|--------|--------|-------------|
| `semantic_filter` | JSON object | Metadata filter for targeted search |
| `query_expansion` | `true`, `false` | Enable/disable multi-query retrieval |
| `rerank` | `true`, `false` | Enable/disable cross-encoder reranking |

**Example prompts sheet:**

| sequence | prompt_name | prompt | semantic_query | semantic_filter | query_expansion | rerank |
|----------|-------------|--------|----------------|-----------------|-----------------|--------|
| 1 | search | Find API docs | authentication | `{"doc_type": "api"}` | true | true |
| 2 | quick | Quick lookup | pricing | | false | false |

**Semantic filter syntax:**

```json
{"reference_name": "product_spec"}
{"doc_type": "api", "version": "v2"}
```

```python
# Programmatic usage
results = rag_client.search(
    query="authentication",
    n_results=5,
    semantic_filter={"doc_type": "api"},
    query_expansion=True,
    rerank=True
)
```
