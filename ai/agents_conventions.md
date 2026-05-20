# Code Style and Conventions

Extracted from [AGENTS.md](../AGENTS.md). Read this for code style rules, naming conventions, and key patterns.

## Python Version and Type Hints

- Target Python 3.10+ (Python 3.14 recommended)
- Use modern union syntax: `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`
- Always include return type hints for functions/methods
- Use `from __future__ import annotations` for forward references

## Imports

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

## Formatting

- Line length: 100 characters
- Use ruff for formatting (Black-compatible)
- Indent with 4 spaces, single quotes for strings

## Naming Conventions

- **Classes**: PascalCase (`FFMistral`, `ExcelOrchestrator`)
- **Functions/Methods**: snake_case (`generate_response`, `get_config`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_MODEL`, `MAX_RETRIES`)
- **Private methods**: prefix with underscore (`_initialize_client`)
- **Files**: snake_case (`excel_orchestrator.py`, `test_ffai.py`)

## Docstrings

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

## Error Handling and Logging

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

## Ruff Rules Enabled

```toml
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM", "PLC", "PLW", "RET", "RUF"]
```

## Dead Code Detection (Vulture)

Vulture is used to detect unreachable code and unused definitions.

```bash
vulture src vulture_whitelist.py --min-confidence 80
```

Add false positives to `vulture_whitelist.py` with a `# noqa: V103` comment explaining why the item is intentionally unused.

## Key Patterns

- AI clients inherit from `FFAIClientBase`
- Use `match` statements for configuration parsing (Python 3.10+)
- DataFrame operations prefer Polars over Pandas
- Excel workbooks use openpyxl
- Access configuration via `get_config()` from `src.config`
- RAG operations use `FFRAGClient` from `src.RAG`
