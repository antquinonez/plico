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
├── FFEmbeddings.py              # LiteLLM embedding wrapper
│                               # - embed(texts) -> list[list[float]]
│                               # - embed_single(text) -> list[float]
│                               # - Supports: mistral, openai, azure, anthropic
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
│   └── contextual_embeddings.py # ContextualEmbeddings - context-aware embedding
└── search/                      # Search strategies
    ├── __init__.py              # Exports all search components
    ├── hybrid_search.py         # HybridSearch, reciprocal_rank_fusion
    └── rerankers.py             # CrossEncoderReranker, DiversityReranker
```

## Configuration

### RAGConfig (src/config.py)

```python
class RAGConfig(BaseModel):
    """RAG configuration settings."""

    enabled: bool = True
    persist_dir: str = "./chroma_db"
    collection_name: str = "ffclients_documents"
    embedding_model: str = "mistral/mistral-embed"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    n_results_default: int = 5
```

### config/main.yaml

```yaml
rag:
  enabled: true
  persist_dir: "./chroma_db"
  collection_name: "ffclients_documents"
  embedding_model: "mistral/mistral-embed"
  chunk_size: 1000
  chunk_overlap: 200
  n_results_default: 5
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
│   (with index_type,     │
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
| `index_type` | Chunking strategy used (recursive, markdown, code, hierarchical, character) |
| `document_checksum` | SHA256 hash of original document content |
| `indexed_at` | ISO timestamp when document was indexed |
| `_chunk_index` | Index within document |
| `_start_char` | Start position in original text |
| `_end_char` | End position in original text |
| (custom) | Any additional metadata passed |

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
| `index_type` | Chunking strategy used (recursive, markdown, code, hierarchical, character) |
| `document_checksum` | SHA256 hash of document content |
| `indexed_at` | ISO timestamp when document was indexed |
| `reference_name` | Document identifier |

### Reindexing Logic

Documents are reindexed when:
1. Document content changes (checksum mismatch)
2. Chunking strategy changes (different `index_type`)
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
         │                             └──► FFVectorStore.add_chunks(index_type, checksum)
         │
         ▼
    Orchestrator continues with all documents pre-indexed
```

## Index Management Tasks

The following invoke tasks are available for managing RAG indexes:

### List Index Status

```bash
inv index-status
```

Shows:
- Total chunk count
- Indexed documents by reference name
- Index types in use
- Last indexed timestamps

### Clear All Indexes

```bash
inv index-clear
```

Removes all chunks from the vector store. Use with caution.

### Clear Specific Index Type

```bash
inv index-clear-type recursive
inv index-clear-type markdown
```

Removes only chunks with the specified `index_type`. Useful when changing chunking strategies.

### Rebuild Indexes

```bash
inv index-rebuild
```

Clears all indexes and reindexes all documents from the configured workbook.

### View RAG Statistics

```bash
inv rag-stats
```

Shows detailed statistics about the RAG system configuration and current state.

## Invoke Task Reference

| Task | Description |
|------|-------------|
| `inv index-status` | Show indexed documents and index types |
| `inv index-clear` | Clear all indexes (destructive) |
| `inv index-clear-type <type>` | Clear specific index type only |
| `inv index-rebuild` | Rebuild all indexes from workbook |
| `inv rag-stats` | Show RAG configuration and statistics |

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

### Running Tests

```bash
# Activate Python 3.13 environment (required for ChromaDB)
source .venv313/bin/activate

# Run RAG tests
pytest tests/test_rag.py -v

# Run with coverage
pytest tests/test_rag.py --cov=src/RAG --cov-report=term-missing
```

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
    "chromadb>=0.4.0",
]
```

## Python Version Compatibility

| Version | ChromaDB | Status |
|---------|----------|--------|
| 3.14+ | Incompatible (pydantic v1) | Use .venv313 |
| 3.13 | Compatible | Recommended |
| 3.12 | Compatible | Supported |

The main virtual environment (`.venv/`) uses Python 3.14. For RAG functionality, use `.venv313/`:

```bash
# Create Python 3.13 environment
uv venv .venv313 --python 3.13
source .venv313/bin/activate
uv pip install -e ".[dev]"

# Run orchestrator with RAG
source .venv313/bin/activate
python scripts/run_orchestrator.py workbook.xlsx
```

## Implemented Enhancements

### 1. Hybrid Search (Implemented)

Combine vector similarity with BM25 keyword matching using Reciprocal Rank Fusion (RRF).

```yaml
rag:
  search:
    mode: "hybrid"  # "vector", "bm25", or "hybrid"
    hybrid_alpha: 0.6  # 60% vector, 40% BM25
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
3. **Caching** - Cache embeddings for repeated queries
4. **Metadata Filtering** - Enhanced search within document subsets
