# Test Coverage Report

**Generated:** 2026-03-01
**Total Coverage:** 84%
**Tests:** 1006 passed, 1 skipped

## Summary

| Metric | Value |
|--------|-------|
| Total Statements | 6,631 |
| Covered Statements | 5,591 |
| Missed Statements | 1,040 |
| Coverage Percentage | 84% |

## Coverage by Module

### Core Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/config.py` | 226 | 8 | **96%** |
| `src/PermanentHistory.py` | 17 | 0 | **100%** |
| `src/FFAI.py` | 426 | 37 | **91%** |
| `src/OrderedPromptHistory.py` | 140 | 18 | **87%** |
| `src/FFAIClientBase.py` | 22 | 5 | **77%** |
| `src/ConversationHistory.py` | 16 | 1 | **94%** |

### Client Implementations

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/Clients/FFPerplexity.py` | 69 | 0 | **100%** |
| `src/Clients/FFAzureLiteLLM.py` | 36 | 0 | **100%** |
| `src/Clients/FFNvidiaDeepSeek.py` | 69 | 1 | **99%** |
| `src/Clients/FFLiteLLMClient.py` | 101 | 1 | **99%** |
| `src/Clients/FFAzureDeepSeekV3.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistral.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistralSmall.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzurePhi.py` | 20 | 1 | **95%** |
| `src/Clients/FFAnthropic.py` | 81 | 5 | **94%** |
| `src/Clients/FFAnthropicCached.py` | 97 | 3 | **97%** |
| `src/Clients/model_defaults.py` | 27 | 2 | **93%** |
| `src/Clients/FFOpenAIAssistant.py` | 110 | 13 | **88%** |
| `src/Clients/FFMistral.py` | 146 | 27 | **82%** |
| `src/Clients/FFGemini.py` | 85 | 24 | **72%** |
| `src/Clients/FFMistralSmall.py` | 146 | 41 | **72%** |
| `src/Clients/FFAzureClientBase.py` | 226 | 79 | **65%** |
| `src/Clients/FFAzureCodestral.py` | 136 | 53 | **61%** |
| `src/Clients/FFAzureDeepSeek.py` | 125 | 48 | **62%** |
| `src/Clients/FFAzureMSDeepSeekR1.py` | 123 | 56 | **54%** |

### Orchestrator Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/orchestrator/workbook_parser.py` | 402 | 23 | **94%** |
| `src/orchestrator/client_registry.py` | 88 | 7 | **92%** |
| `src/orchestrator/manifest.py` | 636 | 82 | **87%** |
| `src/orchestrator/excel_orchestrator.py` | 596 | 116 | **81%** |
| `src/orchestrator/document_registry.py` | 140 | 30 | **79%** |
| `src/orchestrator/condition_evaluator.py` | 313 | 88 | **72%** |
| `src/orchestrator/document_processor.py` | 148 | 49 | **67%** |

### RAG Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/RAG/text_splitter.py` | 24 | 0 | **100%** |
| `src/RAG/mcp_tools.py` | 29 | 0 | **100%** |
| `src/RAG/text_splitters/factory.py` | 42 | 0 | **100%** |
| `src/RAG/indexing/bm25_index.py` | 108 | 2 | **98%** |
| `src/RAG/search/rerankers.py` | 92 | 2 | **98%** |
| `src/RAG/FFVectorStore.py` | 142 | 10 | **93%** |
| `src/RAG/text_splitters/markdown.py` | 111 | 8 | **93%** |
| `src/RAG/text_splitters/recursive.py` | 108 | 8 | **93%** |
| `src/RAG/search/query_expansion.py` | 57 | 4 | **93%** |
| `src/RAG/text_splitters/character.py` | 41 | 2 | **95%** |
| `src/RAG/text_splitters/base.py` | 45 | 4 | **91%** |
| `src/RAG/search/hybrid_search.py` | 95 | 9 | **91%** |
| `src/RAG/indexing/contextual_embeddings.py` | 51 | 6 | **88%** |
| `src/RAG/text_splitters/hierarchical.py` | 82 | 11 | **87%** |
| `src/RAG/FFRAGClient.py` | 345 | 55 | **84%** |
| `src/RAG/indexing/deduplication.py` | 56 | 10 | **82%** |
| `src/RAG/text_splitters/code.py` | 141 | 30 | **79%** |
| `src/RAG/FFEmbeddings.py` | 136 | 34 | **75%** |
| `src/RAG/indexing/hierarchical_index.py` | 99 | 26 | **74%** |

## Priority Areas for Improvement

### High Priority (< 60% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/Clients/FFAzureMSDeepSeekR1.py` | 54% | 56 | Add tests for extended features |

### Medium Priority (60-75% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/orchestrator/document_processor.py` | 67% | 49 | Add tests for document parsing |
| `src/Clients/FFAzureCodestral.py` | 61% | 53 | Add tests for streaming methods |
| `src/Clients/FFAzureDeepSeek.py` | 62% | 48 | Add tests for extended features |
| `src/Clients/FFAzureClientBase.py` | 65% | 79 | Add tests for Azure base class methods |
| `src/orchestrator/condition_evaluator.py` | 72% | 88 | Add tests for complex expressions |
| `src/Clients/FFGemini.py` | 72% | 24 | Add tests for token refresh edge cases |
| `src/Clients/FFMistralSmall.py` | 72% | 41 | Add tests for Mistral Small specific features |
| `src/RAG/indexing/hierarchical_index.py` | 74% | 26 | Add tests for delete operations |
| `src/RAG/FFEmbeddings.py` | 75% | 34 | Add tests for local embeddings |
| `src/FFAIClientBase.py` | 77% | 5 | Add tests for abstract methods |
| `src/RAG/text_splitters/code.py` | 79% | 30 | Add tests for more languages |

## Test Categories

### Unit Tests

Located in `tests/` directory:

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_condition_evaluator.py` | 145+ | Conditional expression parsing and evaluation |
| `test_config.py` | 30+ | Configuration loading and precedence |
| `test_client_registry.py` | 12 | Client registry functionality |
| `test_ffai.py` | 96 | FFAI wrapper, history, DataFrame export |
| `test_excel_orchestrator.py` | 30+ | Orchestrator execution |
| `test_workbook_parser.py` | 20+ | Workbook parsing and building |
| `test_manifest.py` | 20+ | Manifest export and execution |
| `test_rag.py` | 90+ | RAG client, vector store, embeddings |
| `test_rag_chunkers.py` | 50+ | Text chunking strategies |
| `test_rag_search.py` | 47+ | Search, reranking, hybrid search |
| `test_rag_indexing.py` | 20+ | BM25, hierarchical indexing |
| `test_ff*.py` | 100+ | Individual client tests |

### Integration Tests

Located in `tests/integration/` directory:

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_orchestrator_integration.py` | 10 | Full orchestrator workflows |
| `test_batch_integration.py` | 8 | Batch execution with variables |
| `test_conditional_integration.py` | 8 | Conditional execution |
| `test_multiclient_integration.py` | 6 | Multi-client execution |
| `test_documents_integration.py` | 5 | Document reference injection |
| `test_context_assembly.py` | 10 | Context assembly from history |
| `test_client_isolation.py` | 8 | Client isolation in parallel execution |
| `test_ffmistralsmall_integration.py` | 17 | Mistral Small API integration |

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Run Specific Test File

```bash
pytest tests/test_ffai.py -v
```

### Run Integration Tests Only

```bash
pytest tests/integration/ -v
```

### Generate HTML Coverage Report

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Coverage Targets

| Priority | Module Group | Current | Target |
|----------|--------------|---------|--------|
| High | Core (`FFAI`, `config`) | 91-96% | 90% ✓ |
| High | Orchestrator | 67-94% | 85% |
| High | RAG | 74-100% | 85% |
| Medium | Clients | 54-100% | 75% |

## Notes

1. **Integration tests require API keys** - Set environment variables in `.env`
2. **Client tests use extensive mocking** - All client tests work without real API keys
3. **RAG module coverage significantly improved** - Now at 87% average
4. **FFAI module coverage significantly improved** - Now at 91%

## Recent Coverage Changes

| Date | Change | Reason |
|------|--------|--------|
| 2026-03-01 | Baseline report | Initial coverage documentation (73%) |
| 2026-03-01 | +119 client tests | Coverage 70% → 78% for Clients module |
| 2026-03-01 | +121 RAG tests | Coverage 73% → 82% overall |
| 2026-03-01 | +59 FFAI tests | Coverage 82% → 84% overall, FFAI 63% → 91% |

## New Tests Added (2026-03-01)

### FFAI Module Tests

| Test Class | Tests | Coverage Impact |
|------------|-------|------------------|
| `TestFFAIExtractJson` | 4 | `_extract_json` method |
| `TestFFAICleanResponseExtended` | 5 | `_clean_response` edge cases |
| `TestFFAIBuildPrompt` | 5 | `_build_prompt` with history |
| `TestFFAIGenerateResponseExtended` | 4 | System instructions, dependencies, thread lock |
| `TestFFAIHistoryAccessExtended` | 12 | Interaction access methods |
| `TestFFAIClientConversationHistoryErrors` | 5 | Error handling paths |
| `TestFFAIDataFrameExtended` | 14 | DataFrame export methods |
| `TestFFAIPersistence` | 3 | Auto-persist, persist_all |
| `TestFFAIInitExtended` | 1 | Shared history initialization |
| `TestFFAIGenerateResponseException` | 2 | Exception handling |
| `TestFFAITimestampConversion` | 2 | Timestamp to datetime |
| `TestFFAIAddClientMessageWithKwargs` | 1 | Client message with kwargs |

**Total new FFAI tests:** 59

**Coverage improvement:** FFAI.py 63% → 91%, Overall 82% → 84%
