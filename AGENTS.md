# AGENTS.md - FFClients Development Guide

Guidelines for AI coding agents working in this repository.

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
inv create                    # Create all test workbooks
inv run                       # Run orchestrator on all workbooks
inv all                       # Full pipeline: clean, create, run, validate
```

### Pre-commit

```bash
pre-commit run --all-files    # Run all hooks on all files
pre-commit install            # Install git hooks
```

## Project Structure

```
src/
├── FFAI.py              # Main wrapper class for AI clients
├── FFAIClientBase.py    # Abstract base class for clients
├── config.py            # Pydantic-based configuration management
├── Clients/             # AI client implementations (FFMistral, FFAnthropic, etc.)
└── orchestrator/        # Excel orchestration (excel_orchestrator, workbook_builder, etc.)

tests/
├── conftest.py          # Shared fixtures
├── integration/         # Integration tests (require API keys)
└── test_*.py            # Unit tests

config/                  # YAML configuration files (main.yaml, clients.yaml, test.yaml)
scripts/                 # Utility scripts (run_orchestrator.py, validation/)
```

## Code Style Guidelines

### Python Version and Type Hints

- Target Python 3.10+
- Use modern union syntax: `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`
- Always include return type hints for functions/methods
- Use `from __future__ import annotations` for forward references

### Imports

```python
# Standard library first
import json
import logging
from collections.abc import Callable
from typing import Any

# Third-party packages second
import polars as pl
from pydantic import Field

# Local imports last (use relative for same package)
from .FFAIClientBase import FFAIClientBase
from ..config import get_config
```

### Formatting

- Line length: 100 characters
- Use ruff for formatting (Black-compatible)
- Indent with 4 spaces, single quotes for strings

### Naming Conventions

- **Classes**: PascalCase (`FFMistral`, `ExcelOrchestrator`)
- **Functions/Methods**: snake_case (`generate_response`, `get_config`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_MODEL`, `MAX_RETRIES`)
- **Private methods**: prefix with underscore (`_initialize_client`)
- **Files**: snake_case (`excel_orchestrator.py`, `test_ffai.py`)

### Docstrings

```python
def generate_response(self, prompt: str, prompt_name: str | None = None) -> str:
    """Generate a response from the AI client.

    Args:
        prompt: The user prompt to send.
        prompt_name: Optional name for this prompt.

    Returns:
        The AI-generated response string.

    Raises:
        ValueError: If the client is not initialized.

    """
```

### Error Handling and Logging

```python
import logging

logger = logging.getLogger(__name__)

if not api_key:
    logger.error("API key not found")
    raise ValueError("API key not found")
```

- Use specific exception types
- Log errors with `logger.error()` before raising
- Use f-strings for error messages

### Testing Conventions

- Use pytest with class-based test organization
- Place shared fixtures in `conftest.py`
- Name test files as `test_<module>.py`, classes as `Test<Feature>`, methods as `test_<description>`
- Import modules inside test methods when mocking is needed

```python
class TestFFAIGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_ffmistralsmall):
        """Test basic response generation."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!")

        assert response == "This is a test response."
```

### Ruff Rules Enabled

```toml
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
```

### Key Patterns

- AI clients inherit from `FFAIClientBase`
- Use `match` statements for configuration parsing (Python 3.10+)
- DataFrame operations prefer Polars over Pandas
- Excel workbooks use openpyxl
- Access configuration via `get_config()` from `src.config`

## Environment

- Virtual environment: `.venv313/` (Python 3.13)
  - Activate: `source .venv313/bin/activate`
  - Install: `uv pip install -e ".[dev]"`
- Environment variables: Load via `python-dotenv` (`load_dotenv()`)
- Set `POLARS_SKIP_CPU_CHECK=1` for Polars compatibility

## Notes

- This is proprietary code - do not share externally
- Integration tests require real API keys in `.env`
- Use `inv --list` to see all available commands
