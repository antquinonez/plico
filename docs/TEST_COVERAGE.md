# Test Coverage Report

**Generated:** 2026-03-01
**Total Coverage:** 70%
**Tests:** 697 passed, 1 skipped

## Summary

| Metric | Value |
|--------|-------|
| Total Statements | 6,624 |
| Covered Statements | 4,619 |
| Missed Statements | 2,005 |
| Coverage Percentage | 70% |

## Coverage by Module

### Core Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/config.py` | 225 | 8 | **96%** |
| `src/PermanentHistory.py` | 17 | 0 | **100%** |
| `src/OrderedPromptHistory.py` | 140 | 18 | **87%** |
| `src/FFAIClientBase.py` | 22 | 5 | **77%** |
| `src/FFAI.py` | 426 | 156 | **63%** |
| `src/ConversationHistory.py` | 16 | 11 | **31%** |

### Client Implementations

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/Clients/FFPerplexity.py` | 69 | 0 | **100%** |
| `src/Clients/FFNvidiaDeepSeek.py` | 69 | 1 | **99%** |
| `src/Clients/FFLiteLLMClient.py` | 101 | 3 | **97%** |
| `src/Clients/FFAzureDeepSeekV3.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistral.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistralSmall.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzurePhi.py` | 20 | 1 | **95%** |
| `src/Clients/FFAnthropic.py` | 81 | 5 | **94%** |
| `src/Clients/model_defaults.py` | 27 | 3 | **89%** |
| `src/Clients/FFOpenAIAssistant.py` | 110 | 13 | **88%** |
| `src/Clients/FFMistral.py` | 146 | 27 | **82%** |
| `src/Clients/FFMistralSmall.py` | 146 | 49 | **66%** |
| `src/Clients/FFAzureClientBase.py` | 226 | 84 | **63%** |
| `src/Clients/FFAzureCodestral.py` | 136 | 85 | **38%** |
| `src/Clients/FFAzureMSDeepSeekR1.py` | 123 | 81 | **34%** |
| `src/Clients/FFAzureDeepSeek.py` | 125 | 82 | **34%** |
| `src/Clients/FFGemini.py` | 85 | 63 | **26%** |
| `src/Clients/FFAnthropicCached.py` | 97 | 71 | **27%** |
| `src/Clients/FFAzureLiteLLM.py` | 36 | 29 | **19%** |

### Orchestrator Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/orchestrator/workbook_builder.py` | 396 | 40 | **90%** |
| `src/orchestrator/client_registry.py` | 88 | 7 | **92%** |
| `src/orchestrator/excel_orchestrator.py` | 596 | 116 | **81%** |
| `src/orchestrator/document_registry.py` | 140 | 30 | **79%** |
| `src/orchestrator/condition_evaluator.py` | 313 | 88 | **72%** |
| `src/orchestrator/document_processor.py` | 148 | 49 | **67%** |
| `src/orchestrator/manifest.py` | 636 | 405 | **36%** |

### RAG Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/RAG/text_splitter.py` | 24 | 0 | **100%** |
| `src/RAG/mcp_tools.py` | 29 | 0 | **100%** |
| `src/RAG/text_splitters/factory.py` | 42 | 0 | **100%** |
| `src/RAG/indexing/bm25_index.py` | 108 | 2 | **98%** |
| `src/RAG/text_splitters/character.py` | 41 | 2 | **95%** |
| `src/RAG/text_splitters/markdown.py` | 111 | 8 | **93%** |
| `src/RAG/text_splitters/base.py` | 45 | 4 | **91%** |
| `src/RAG/search/hybrid_search.py` | 95 | 9 | **91%** |
| `src/RAG/search/query_expansion.py` | 57 | 5 | **91%** |
| `src/RAG/indexing/contextual_embeddings.py` | 51 | 6 | **88%** |
| `src/RAG/text_splitters/hierarchical.py` | 82 | 11 | **87%** |
| `src/RAG/FFEmbeddings.py` | 136 | 34 | **75%** |
| `src/RAG/indexing/hierarchical_index.py` | 99 | 26 | **74%** |
| `src/RAG/text_splitters/code.py` | 141 | 30 | **79%** |
| `src/RAG/indexing/deduplication.py` | 56 | 10 | **82%** |
| `src/RAG/FFVectorStore.py` | 142 | 57 | **60%** |
| `src/RAG/text_splitters/recursive.py` | 108 | 52 | **52%** |
| `src/RAG/search/rerankers.py` | 92 | 31 | **66%** |
| `src/RAG/FFRAGClient.py` | 345 | 185 | **46%** |

## Priority Areas for Improvement

### High Priority (< 50% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/orchestrator/manifest.py` | 36% | 405 | Add tests for `ManifestOrchestrator` execution paths |
| `src/Clients/FFAzureLiteLLM.py` | 19% | 29 | Add unit tests for Azure LiteLLM client |
| `src/Clients/FFAnthropicCached.py` | 27% | 71 | Add tests for cached prompt functionality |
| `src/Clients/FFGemini.py` | 26% | 63 | Add unit tests for Gemini client |
| `src/Clients/FFAzureDeepSeek.py` | 34% | 82 | Add unit tests for Azure DeepSeek |
| `src/Clients/FFAzureMSDeepSeekR1.py` | 34% | 81 | Add unit tests for Azure MS DeepSeek R1 |
| `src/Clients/FFAzureCodestral.py` | 38% | 85 | Add unit tests for Azure Codestral |
| `src/ConversationHistory.py` | 31% | 11 | Add tests for conversation management |
| `src/RAG/FFRAGClient.py` | 46% | 185 | Add tests for RAG client methods |

### Medium Priority (50-70% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/RAG/text_splitters/recursive.py` | 52% | 52 | Add edge case tests |
| `src/RAG/FFVectorStore.py` | 60% | 57 | Add tests for vector operations |
| `src/FFAI.py` | 63% | 156 | Add tests for persistence, DataFrame export |
| `src/Clients/FFAzureClientBase.py` | 63% | 84 | Add tests for Azure base class methods |
| `src/RAG/search/rerankers.py` | 66% | 31 | Add tests for reranking logic |
| `src/orchestrator/document_processor.py` | 67% | 49 | Add tests for document parsing |
| `src/Clients/FFMistralSmall.py` | 66% | 49 | Add tests for Mistral Small specific features |

## Test Categories

### Unit Tests

Located in `tests/` directory:

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_condition_evaluator.py` | 145+ | Conditional expression parsing and evaluation |
| `test_config.py` | 30+ | Configuration loading and precedence |
| `test_client_registry.py` | 12 | Client registry functionality |
| `test_ffai.py` | 20+ | FFAI wrapper class |
| `test_excel_orchestrator.py` | 30+ | Orchestrator execution |
| `test_workbook_builder.py` | 20+ | Workbook parsing and building |
| `test_manifest.py` | 20+ | Manifest export and execution |
| `test_rag*.py` | 50+ | RAG chunking, search, indexing |
| `test_ff*.py` | 50+ | Individual client tests |

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
| High | Core (`FFAI`, `config`) | 63-96% | 85% |
| High | Orchestrator | 36-92% | 80% |
| Medium | RAG | 46-100% | 75% |
| Medium | Clients | 19-100% | 70% |
| Low | Azure specialized | 19-38% | 50% |

## Notes

1. **Integration tests require API keys** - Set environment variables in `.env`
2. **Some client tests are minimal** - Many Azure clients share base class logic
3. **Manifest orchestrator needs coverage** - New feature with limited test coverage
4. **RAG client has many untested paths** - Advanced features need more tests

## Recent Coverage Changes

| Date | Change | Reason |
|------|--------|--------|
| 2026-03-01 | Baseline report | Initial coverage documentation |
