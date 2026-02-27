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
├── __init__.py              # Exports: FFRAGClient, FFEmbeddings, FFVectorStore,
│                            #          RAGMCPTools, split_text, CHROMADB_AVAILABLE
├── text_splitter.py         # Text chunking utilities
│                            # - split_text(text, chunk_size, chunk_overlap, metadata)
│                            # - split_documents(documents, text_key, ...)
│                            # - TextChunk dataclass
├── FFEmbeddings.py          # LiteLLM embedding wrapper
│                            # - embed(texts) -> list[list[float]]
│                            # - embed_single(text) -> list[float]
│                            # - Supports: mistral, openai, azure, anthropic
├── FFVectorStore.py         # ChromaDB operations
│                            # - add_chunks(chunks) -> int
│                            # - add_documents(documents) -> int
│                            # - search(query, n_results) -> list[dict]
│                            # - delete_by_reference(reference_name)
│                            # - list_documents() -> list[str]
│                            # - get_stats() -> dict
│                            # - clear()
├── FFRAGClient.py           # High-level RAG interface
│                            # - add_document(content, reference_name, metadata)
│                            # - search(query, n_results) -> list[dict]
│                            # - format_results_for_prompt(results, max_chars)
│                            # - search_and_format(query, n_results, max_chars)
│                            # - delete_by_reference(reference_name)
│                            # - get_stats() -> dict
└── mcp_tools.py             # MCP tool definitions
                             # - rag_search(query, n_results)
                             # - rag_add_document(content, reference_name)
                             # - rag_list_documents()
                             # - rag_get_stats()
                             # - rag_delete_document(reference_name)
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

### Document Indexing Flow

```
Document (library/doc.pdf)
         │
         ▼
┌─────────────────────────┐
│   DocumentProcessor     │
│   .parse_document()     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   DocumentProcessor     │
│   ._index_to_rag()      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   FFRAGClient           │
│   .add_document()       │
└───────────┬─────────────┘
            │
            ├─── split_text() ───► TextChunks
            │
            ▼
┌─────────────────────────┐
│   FFVectorStore         │
│   .add_chunks()         │
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

## Future Enhancements

1. **Hybrid Search** - Combine keyword and semantic search
2. **Re-ranking** - Post-retrieval relevance scoring
3. **Multi-collection** - Separate collections by topic/domain
4. **Streaming** - Stream search results for large datasets
5. **Caching** - Cache embeddings for repeated queries
6. **Metadata Filtering** - Search within document subsets
