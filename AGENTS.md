# AGENTS.md

Instructions for AI coding agents working on this project.

## Extended Instructions

Task-specific guides in `ai/`:
- `ai/agents_reference.md` — project structure, client reference, RAG module, dependencies
- `ai/agents_orchestrator.md` — config worksheet schema, workbook scripts, configuration files
- `ai/agents_modules.md` — rate limiting, agent module, planning phase, observability, evaluation
- `ai/agents_use_cases.md` — resume screening, manifest workflow, pre-screening
- `ai/agents_conventions.md` — code style guidelines, naming, formatting, key patterns
- `ai/agents_testing.md` — test organization and writing conventions

## Project Overview

Plico is an AI orchestration library that drives multi-prompt LLM workflows from Excel workbooks and YAML manifests. It provides client abstractions over multiple AI providers (Mistral, Gemini, Perplexity, LiteLLM), a deterministic DAG orchestrator with conditional execution, planning phases, agent tool-call loops, scoring/synthesis, and RAG integration.

## Git Operations

**Never commit, push, or submit a pull request unless the user explicitly asks.**
This includes `git commit`, `git push`, `gh pr create`, and any other remote-submitted action.
Wait for the user to request each of these steps individually.

## Build/Lint/Test Commands

### Testing

```bash
pytest tests/ -v                           # Run all tests (excluding integration)
pytest tests/test_ffai.py -v               # Run single test file
pytest tests/test_ffai.py::TestFFAIInit -v # Run single test class
pytest tests/test_ffai.py::TestFFAIInit::test_init_basic -v  # Run single test method
pytest tests/ --cov=src --cov-report=term-missing  # Run with coverage
pytest tests/integration/ -v               # Run integration tests (requires API keys)
```

### Linting and Formatting

```bash
ruff check src tests          # Check linting
ruff check src tests --fix    # Auto-fix linting issues
ruff format src tests         # Format code
```

### Invoke Tasks (Recommended)

```bash
inv --list                    # Show all available tasks
inv test                      # Run tests (excludes integration)
inv test -p tests/test_ffai.py  # Run specific test file
inv test-all                  # Run all tests including integration
inv lint                      # Run linting
inv format                    # Run formatting
inv config-check              # Display current configuration
```

### Workbook Tasks (wb namespace)

```bash
inv wb.create                 # Create all test workbooks
inv wb.run                    # Run orchestrator on all workbooks
inv wb.run -c 4               # Run with concurrency=4
inv wb.validate               # Validate all workbook results
inv wb.clean                  # Remove all test workbooks
inv wb.all                    # Full pipeline: clean, create, run, validate
inv wb.spot-check             # Spot check responses from key prompts
inv wb.basic                  # Create, run, and validate basic workbook
inv wb.multiclient            # Create, run, and validate multiclient workbook
inv wb.conditional            # Create, run, and validate conditional workbook
inv wb.documents              # Create, run, and validate documents workbook
inv wb.batch                  # Create, run, and validate batch workbook
inv wb.max                    # Create, run, and validate max workbook
inv wb.agent                  # Create, run, and validate agent workbook
```

### RAG Tasks (rag namespace)

```bash
inv rag.status                # Show RAG indexing status
inv rag.clear                 # Clear all RAG indexes
inv rag.clear -c recursive    # Clear specific chunking strategy
inv rag.clear-strategy recursive  # Clear specific chunking strategy
inv rag.rebuild               # Rebuild indexes from documents workbook
inv rag.stats                 # Show detailed RAG statistics
```

### Screening Tasks (screening namespace)

```bash
inv screening.create -r ./resumes/ -j ./jd.md                     # Create workbook only
inv screening.create -r ./resumes/ -j ./jd.md --planning          # Create with planning mode
inv screening.run -r ./resumes/ -j ./jd.md                        # Create and run (Excel)
inv screening.run -r ./resumes/ -j ./jd.md --planning -c 2        # Planning mode, concurrency 2
inv screening.manifest -r ./resumes/ -j ./jd.md                   # Create manifest and run (YAML)
inv screening.manifest -r ./resumes/ -j ./jd.md --planning        # Manifest with planning mode
inv screening.inspect ./screening.xlsx                             # Inspect results
```

### Pre-commit

```bash
pre-commit run --all-files    # Run all hooks on all files
pre-commit install            # Install git hooks
```

## Environment

- Virtual environment: `.venv/` (Python 3.14)
  - Activate: `source .venv/bin/activate`
  - Install: `uv pip install -e ".[dev]"`
- Environment variables: Load via `python-dotenv` (`load_dotenv()`)
- Set `POLARS_SKIP_CPU_CHECK=1` for Polars compatibility

### Required Environment Variables (in .env)

```bash
# At least one API key required
MISTRALSMALL_KEY=your-key-here
MISTRAL_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
GEMINI_KEY=your-key-here
PERPLEXITY_KEY=your-key-here
NVIDIA_KEY=your-key-here
OPENAI_KEY=your-key-here

# Azure deployments
AZURE_MISTRAL_KEY=your-key-here
AZURE_PHI_KEY=your-key-here
# ... etc
```

## Key Conventions

### No emojis
Do not use emojis in code or commit messages unless explicitly asked.

### No comments in production code (src/)
Do not add inline comments (`#`) that explain *what* code does. Docstrings on public classes and methods are always allowed. "Why" comments explaining non-obvious design rationale are allowed. Tests and scripts may use comments freely.

### Key Patterns
- AI clients inherit from `FFAIClientBase`
- Use `match` statements for configuration parsing (Python 3.10+)
- DataFrame operations prefer Polars over Pandas
- Excel workbooks use openpyxl
- Access configuration via `get_config()` from `src.config`
- RAG operations use `FFRAGClient` from `src.RAG`

For full code style rules (type hints, imports, formatting, naming, docstrings, error handling, ruff, vulture), see `ai/agents_conventions.md`.

## Making Changes

1. Run the full test suite after changes.
2. New features should have tests in `tests/test_<module>.py`.
3. Run linting after changes: `ruff check src tests`.
4. **Do not commit unless the user explicitly asks.**

## Notes

- This is proprietary code - do not share externally
- Integration tests require real API keys in `.env`
- Use `inv --list` to see all available commands
- Use `inv guide` for a project-level task overview
