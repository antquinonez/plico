# Test Coverage Report

**Generated:** 2026-04-10
**Total Coverage:** 88%
**Unit Tests:** 1820 passed, 3 skipped
**Integration Tests:** 44 passed (real API calls)

## Summary

| Metric | Value |
|--------|-------|
| Total Statements | 9,092 |
| Covered Statements | 7,983 |
| Missed Statements | 1,109 |
| Coverage Percentage | **88%** |

## Coverage by Module

### Core Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/config.py` | 282 | 8 | **97%** |
| `src/PermanentHistory.py` | 18 | 0 | **100%** |
| `src/FFAI.py` | 488 | 43 | **91%** |
| `src/OrderedPromptHistory.py` | 141 | 18 | **87%** |
| `src/FFAIClientBase.py` | 42 | 8 | **81%** |
| `src/ConversationHistory.py` | 17 | 1 | **94%** |
| `src/retry_utils.py` | 35 | 0 | **100%** |

### Agent Module

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/agent/agent_result.py` | 42 | 0 | **100%** |
| `src/agent/agent_loop.py` | 101 | 2 | **98%** |

### Client Implementations

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/Clients/FFAzureLiteLLM.py` | 37 | 0 | **100%** |
| `src/Clients/FFNvidiaDeepSeek.py` | 72 | 1 | **99%** |
| `src/Clients/FFAnthropicCached.py` | 98 | 3 | **97%** |
| `src/Clients/FFAzureDeepSeekV3.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistral.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzureMistralSmall.py` | 20 | 1 | **95%** |
| `src/Clients/FFAzurePhi.py` | 20 | 1 | **95%** |
| `src/Clients/FFAnthropic.py` | 84 | 5 | **94%** |
| `src/Clients/model_defaults.py` | 27 | 2 | **93%** |
| `src/Clients/FFPerplexity.py` | 157 | 24 | **85%** |
| `src/Clients/FFLiteLLMClient.py` | 175 | 24 | **86%** |
| `src/Clients/FFOpenAIAssistant.py` | 115 | 16 | **86%** |
| `src/Clients/FFGemini.py` | 211 | 41 | **81%** |
| `src/Clients/FFMistral.py` | 153 | 27 | **82%** |
| `src/Clients/FFMistralSmall.py` | 169 | 59 | **65%** |
| `src/Clients/FFAzureClientBase.py` | 227 | 79 | **65%** |
| `src/Clients/FFAzureCodestral.py` | 137 | 53 | **61%** |
| `src/Clients/FFAzureDeepSeek.py` | 126 | 48 | **62%** |
| `src/Clients/FFAzureMSDeepSeekR1.py` | 124 | 56 | **55%** |

### Orchestrator Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/orchestrator/builtin_tools.py` | 155 | 0 | **100%** |
| `src/orchestrator/tool_registry.py` | 115 | 0 | **100%** |
| `src/orchestrator/results/result.py` | 43 | 0 | **100%** |
| `src/orchestrator/state/execution_state.py` | 17 | 0 | **100%** |
| `src/orchestrator/document_registry.py` | 142 | 0 | **100%** |
| `src/orchestrator/scoring.py` | 104 | 4 | **96%** |
| `src/orchestrator/synthesis.py` | 163 | 5 | **97%** |
| `src/orchestrator/results/builder.py` | 80 | 4 | **95%** |
| `src/orchestrator/state/prompt_node.py` | 21 | 1 | **95%** |
| `src/orchestrator/discovery.py` | 105 | 2 | **98%** |
| `src/orchestrator/planning.py` | 167 | 13 | **92%** |
| `src/orchestrator/client_registry.py` | 89 | 7 | **92%** |
| `src/orchestrator/validation.py` | 395 | 31 | **92%** |
| `src/orchestrator/condition_evaluator.py` | 341 | 33 | **90%** |
| `src/orchestrator/workbook_formatter.py` | 121 | 8 | **93%** |
| `src/orchestrator/workbook_parser.py` | 556 | 83 | **85%** |
| `src/orchestrator/executor.py` | 169 | 18 | **89%** |
| `src/orchestrator/excel_orchestrator.py` | 124 | 21 | **83%** |
| `src/orchestrator/manifest.py` | 265 | 28 | **89%** |
| `src/orchestrator/document_processor.py` | 163 | 19 | **88%** |
| `src/orchestrator/base/orchestrator_base.py` | 784 | 137 | **83%** |

### RAG Modules

| Module | Statements | Missed | Coverage |
|--------|------------|--------|----------|
| `src/RAG/text_splitter.py` | 24 | 0 | **100%** |
| `src/RAG/mcp_tools.py` | 29 | 0 | **100%** |
| `src/RAG/text_splitters/factory.py` | 42 | 0 | **100%** |
| `src/RAG/indexing/deduplication.py` | 56 | 0 | **100%** |
| `src/RAG/indexing/hierarchical_index.py` | 99 | 1 | **99%** |
| `src/RAG/indexing/bm25_index.py` | 108 | 2 | **98%** |
| `src/RAG/search/rerankers.py` | 92 | 2 | **98%** |
| `src/RAG/FFVectorStore.py` | 150 | 11 | **93%** |
| `src/RAG/text_splitters/character.py` | 41 | 2 | **95%** |
| `src/RAG/text_splitters/markdown.py` | 111 | 8 | **93%** |
| `src/RAG/text_splitters/recursive.py` | 108 | 8 | **93%** |
| `src/RAG/search/query_expansion.py` | 57 | 4 | **93%** |
| `src/RAG/text_splitters/hierarchical.py` | 82 | 11 | **87%** |
| `src/RAG/FFRAGClient.py` | 348 | 56 | **84%** |
| `src/RAG/text_splitters/base.py` | 45 | 4 | **91%** |
| `src/RAG/search/hybrid_search.py` | 95 | 9 | **91%** |
| `src/RAG/indexing/contextual_embeddings.py` | 51 | 6 | **88%** |
| `src/RAG/text_splitters/code.py` | 141 | 22 | **84%** |
| `src/RAG/FFEmbeddings.py` | 136 | 27 | **80%** |

## Priority Areas for Improvement

### High Priority (< 65% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/Clients/FFAzureMSDeepSeekR1.py` | 55% | 56 | Add tests for extended features |
| `src/Clients/FFAzureCodestral.py` | 61% | 53 | Add tests for streaming methods |
| `src/Clients/FFMistralSmall.py` | 65% | 59 | Add tests for Mistral Small specific features |
| `src/Clients/FFAzureClientBase.py` | 65% | 79 | Add tests for Azure base class methods |
| `src/Clients/FFAzureDeepSeek.py` | 62% | 48 | Add tests for extended features |

### Medium Priority (65-80% coverage)

| Module | Coverage | Missing Lines | Action |
|--------|----------|---------------|--------|
| `src/RAG/FFEmbeddings.py` | 80% | 27 | Add tests for local embeddings |
| `src/RAG/text_splitters/code.py` | 84% | 22 | Add tests for more languages |
| `src/FFAIClientBase.py` | 81% | 8 | Add tests for abstract methods |
| `src/orchestrator/base/orchestrator_base.py` | 83% | 137 | Add tests for planning/synthesis/agent execution paths |
| `src/orchestrator/excel_orchestrator.py` | 83% | 21 | Add tests for discovery integration |
| `src/orchestrator/workbook_parser.py` | 85% | 83 | Add tests for new sheet parsers (scoring, synthesis) |
| `src/FFGemini.py` | 81% | 41 | Add tests for token refresh edge cases |
| `src/Clients/FFMistral.py` | 82% | 27 | Add tests for extended features |

## Test Files

### Unit Tests (tests/)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_condition_evaluator.py` | 161 | Conditional expression parsing and evaluation |
| `test_ffai.py` | 106 | FFAI wrapper, history, DataFrame export |
| `test_rag.py` | 102 | RAG client, vector store, embeddings |
| `test_agent.py` | 86 | Agent loop, tool-call execution |
| `test_workbook_parser.py` | 79 | Workbook parsing and building |
| `test_excel_orchestrator.py` | 68 | Orchestrator execution |
| `test_manifest_comprehensive.py` | 65 | Comprehensive manifest tests |
| `test_builtin_tools.py` | 58 | Built-in tool implementations |
| `test_rag_chunkers.py` | 57 | Text chunking strategy tests |
| `test_validation.py` | 56 | OrchestratorValidator tests |
| `test_text_splitter.py` | 51 | Legacy text splitter tests |
| `test_orchestrator_base.py` | 50 | Base orchestrator class tests |
| `test_discovery.py` | 50 | Document auto-discovery |
| `test_retry_utils.py` | 47 | Retry decorator tests |
| `test_rag_enhancements.py` | 44 | RAG enhancement tests |
| `test_synthesis.py` | 43 | Cross-row synthesis tests |
| `test_document_processor.py` | 43 | Document parsing and caching |
| `test_scoring.py` | 41 | Scoring rubric and aggregation tests |
| `test_manifest.py` | 41 | Manifest export and execution |
| `test_rag_search.py` | 40 | Search, reranking, hybrid search |
| `test_planning_artifact_parser.py` | 40 | Planning artifact parser tests |
| `test_document_registry.py` | 40 | Document lookup and injection |
| `test_rag_indexing.py` | 38 | BM25, hierarchical index tests |
| `test_config.py` | 37 | Configuration loading and precedence |
| `test_ffazure_clients.py` | 34 | Azure client tests |
| `test_fflitellm_client.py` | 32 | LiteLLM client tests |
| `test_ffgemini.py` | 30 | Gemini client tests |
| `test_ffanthropic_cached.py` | 26 | Anthropic cached client tests |
| `test_results.py` | 23 | PromptResult and ResultBuilder tests |
| `test_ffperplexity.py` | 23 | Perplexity client tests |
| `test_discovery_injection.py` | 21 | Discovery injection into orchestrator |
| `test_planning.py` | 20 | Planning phase tests |
| `test_ordered_prompt_history.py` | 20 | Ordered history tests |
| `test_ffazure_litellm.py` | 18 | Azure LiteLLM factory tests |
| `test_ffmistral.py` | 17 | Mistral client tests |
| `test_ffopenai_assistant.py` | 13 | OpenAI Assistant tests |
| `test_client_registry.py` | 13 | Client registry functionality |
| `test_litellm_orchestrator_integration.py` | 11 | LiteLLM orchestrator integration |
| `test_ffnvidia_deepseek.py` | 11 | NVIDIA client tests |
| `test_permanent_history.py` | 9 | Permanent history tests |
| `test_ffanthropic.py` | 9 | Anthropic client tests |
| `test_ffaiclient_base.py` | 9 | Abstract base class tests |
| `test_state.py` | 8 | ExecutionState and PromptNode tests |

### Integration Tests (tests/integration/)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_orchestrator_integration.py` | 8 | Full orchestrator workflows |
| `test_batch_integration.py` | 8 | Batch execution with variables |
| `test_conditional_integration.py` | 8 | Conditional execution |
| `test_context_assembly.py` | 8 | Context assembly from history |
| `test_client_isolation.py` | 7 | Client isolation in parallel execution |
| `test_multiclient_integration.py` | 5 | Multi-client execution |

## Coverage Targets

| Priority | Module Group | Current | Target |
|----------|--------------|---------|--------|
| High | Core (`FFAI`, `config`) | 87-97% | 90% |
| High | Orchestrator | 83-100% | 85% |
| High | RAG | 80-100% | 85% |
| Medium | Clients | 55-100% | 75% |
| New | Agent | 98-100% | 90% |

## Running Tests

### Run All Unit Tests

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

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### Generate HTML Coverage Report

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Notes

1. **Integration tests require API keys** - Set environment variables in `.env`
2. **Client tests use extensive mocking** - All client tests work without real API keys
3. **RAG module average: 92%** - Significant improvement from prior baselines
4. **Agent module: 99%** - Nearly complete coverage from initial implementation
5. **Orchestrator base at 83%** - Large module; planning/synthesis/agent paths account for most gaps
6. **Total tests: 1,820 unit + 44 integration = 1,864**
