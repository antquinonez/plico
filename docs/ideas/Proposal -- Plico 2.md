**Proposal: “Plico 2.0 — Spreadsheet-Native RAG & Long-Context Orchestration for Analysts & Researchers”**

**Version**: 0.9-draft
**Date**: February 2026
**Target users**: Policy analysts, market researchers, competitive intelligence teams, quant-lite finance / due-diligence teams, academic researchers who already live 80%+ of their day inside Excel

### 1. Executive Summary (the one-liner pitch)

Turn Excel into the control plane for production-grade, auditable, multi-model RAG + prompt-chaining workflows — without forcing users to leave the spreadsheet, write Python, learn a visual DAG tool, or administer a vector database.

Plico 1.x already proved the Excel-native orchestration model works.
Plico 2.0 adds **declarative retrieval** (vector + hybrid + table-aware + text-to-SQL fallbacks), **smart chunking & reranking**, **long-context-aware routing**, and **automatic citation & traceability** — all still defined inside ordinary .xlsx cells.

Goal: make Plico the default “AI workbook” format that serious non-technical teams actually adopt in 2026–2028.

### 2. Problem Statement (why this matters now)

In early 2026 most analyst/research teams are stuck in one of three bad equilibria:

- A. They use ChatGPT / Claude Projects / Gemini with copy-paste → no reproducibility, no batch, no audit trail.
- B. They try LangChain / LlamaIndex / Haystack → huge onboarding cost → only 1–2 power users per department ever ship anything.
- C. They buy a no-code AI platform (n8n, SmythOS, Dify, Flowise, etc.) → discover that visual node editors have terrible version control, poor diff readability, and feel alien to Excel-native teams.

Meanwhile long-context windows (Claude 4 Sonnet 1M+, Gemini 2.5 Pro 1M+, Mistral Large 240k+) + dramatically cheaper inference are shifting economics:

- For documents < ~400–600 pages, full-context stuffing + good conditions often beats poorly-tuned RAG.
- For documents > 1k pages or multi-document corpora, selective retrieval is still mandatory — but users hate managing embeddings, chunk sizes, top-k, rerankers, etc.

Plico is uniquely positioned to bridge both worlds inside the same workbook users already trust.

### 3. Core Design Principles for 2.0

1. **Everything stays in Excel cells** (or very close — acceptable small extensions: one new sheet, two new columns)
2. **Retrieval is just another prompt step** (can be conditional, batched, multi-source, referenced in history)
3. **Default to “good enough” RAG that non-engineers can tune in < 10 minutes**
4. **Preserve perfect auditability** — every retrieved chunk, score, source filepath, latency, token count appears in results sheet
5. **Reuse existing strengths** — shared history, safe AST conditions, per-prompt client switching, batch templating, document cache
6. **Progressive disclosure** — simple whole-document injection continues to work; power users gradually turn on indexing/retrieval

### 4. Proposed Excel Schema Extensions (minimal footprint)

**documents sheet** (add 5 optional columns)

| reference_name | common_name          | file_path              | index_name     | chunk_strategy    | embedding_client   | metadata_json                          | refresh_days |
|----------------|----------------------|------------------------|----------------|-------------------|--------------------|----------------------------------------|--------------|
| corp10k_2025   | 2025 10-K filing     | lib/abc-10k-2025.pdf   | filings_v1     | recursive_512     | litellm-openai-ada | {"ticker":"ABC", "fy":"2025"}          | 30           |
| competitor_pr  | Press releases Q4    | lib/pr_*.pdf           | pr_db          | semantic          | default            | {"company_group":"peers"}              | 7            |
| sales_data     | Internal sales Q1-Q4 | data/internal/sales.xlsx | sales_sql    | table_aware       | —                  | {"schema":"sales", "pk":"order_id"}    | —            |

**prompts sheet** (add one optional column: retrieval)

retrieval (JSON array of retrieval instructions — can be templated)

Example simple single-source:
```json
[{"index":"filings_v1", "query":"{{user_question}}", "top_k":6, "min_score_threshold":0.68}]
```

Example multi-source + conditional rerank:
```json
[
  {"index":"filings_v1",     "query":"{{user_question}} financial risk debt covenant", "top_k":5},
  {"index":"pr_db",          "query":"{{company}} recent press release",               "top_k":3},
  {"index":"sales_sql",      "query_sql":true, "natural_query":"{{user_question}}"},
  {"rerank":true, "reranker_client":"litellm-cohere-rerank", "top_n_after_rerank":4}
]
```

### 5. Execution Semantics (high level)

When a prompt has a non-empty `retrieval` array:

1. For each retrieval spec → embed query (using specified embedding_client or default)
2. Retrieve from persistent index (FAISS flat → IVF-PQ → optional HNSW later)
3. If `query_sql`:true → instead generate SQL via small cheap model, execute against parsed table(s)
4. Apply optional min_score_threshold filter
5. If `rerank`:true → call reranker → re-order & cut to top_n_after_rerank
6. Format retrieved chunks into clean markdown with citation tags
   ```
   <chunk source="corp10k_2025.pdf" page="47" score="0.84" chunk_id="c_3921">
   Revenue decreased 8% YoY due to weakening demand in APAC...
   </chunk>
   ```
7. Store the formatted context block as the “response” of this prompt_name
8. Downstream prompts that include this name in `history` receive the block automatically

### 6. Phase 1 MVP Scope (3–5 engineer-months)

- FAISS local indexes stored in `doc_cache/vectors/{index_name}.faiss` + metadata parquet
- Chunk strategies: fixed, recursive, semantic (via sentence-transformers or cheap embedding model)
- Table-aware parsing for .xlsx (convert sheets → markdown tables + row-level metadata)
- One embedding client + one reranker client (configurable via clients sheet)
- Basic citation + source traceability in results sheet
- Condition support: `{{my_retrieval.num_chunks}} < 2` → fallback prompt

### 7. Phase 2 Nice-to-Haves (post-MVP)

- Text-to-SQL generation & execution for indexed Excel/SQLite sources
- Hybrid search (keyword + vector)
- Multi-modal chunk support (tables → vision embeddings)
- Auto-evaluation mode (Ragas-style faithfulness / answer-relevance scores written to results)
- Index refresh scheduler (cron-like via CLI flag or background thread)
- Optional remote vector stores (Pinecone, Qdrant, Weaviate) via config

### 8. Success Criteria (measurable)

- 80% of typical 10–50 document analyst workflows runnable without writing code
- Average time to first useful RAG answer < 12 minutes from workbook creation
- > 90% of retrieved chunks correctly cited back to source file + page / cell range
- At least 3× reduction in token cost vs. naive full-context stuffing (via conditions + retrieval skipping)

### 9. Risks & Mitigations

Risk: users still stuff too much context → cost explosion
Mitigation: aggressive defaults on min_score_threshold + num_chunks cap + condition templates

Risk: index staleness
Mitigation: checksum + refresh_days column + --refresh-indexes CLI flag

Risk: embedding model quality variance
Mitigation: let users pick any LiteLLM embedding model per index
