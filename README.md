# FFClients

A declarative context handling API wrapper for AI clients with Excel-based orchestration.

## Features

- **Declarative Context Management**: Reference previous prompts by name for automatic context assembly
- **Multiple AI Clients**: Support for Mistral AI models
- **Excel Orchestration**: Define and execute prompt workflows via Excel workbooks
- **History Management**: Track, search, and export conversation history to DataFrames
- **Document References**: Inject external documents into prompts with automatic parsing and caching

## Installation

```bash
pip install -e . --break-system-packages
```

## Quick Start

### Python API

```python
from src.FFAI import FFAI
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(api_key="your-api-key")
ffai = FFAI(client)

# Simple prompt
response = ffai.generate_response("Hello!")

# Named prompt with history context
ffai.generate_response("What is 2+2?", prompt_name="math")
ffai.generate_response(
    "What was my math question?",
    prompt_name="followup",
    history=["math"]
)
```

### Excel Orchestrator

```bash
# Create a new workbook template
python scripts/run_orchestrator.py my_prompts.xlsx

# Edit prompts in Excel, then run
python scripts/run_orchestrator.py my_prompts.xlsx
```

## Documentation

- [Client API User Guide](docs/CLIENT%20API%20USER%20GUIDE.md)
- [Orchestrator README](docs/ORCHESTRATOR%20README.md)

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=term-missing
```

## License

MIT License - Copyright (c) 2025 Antonio Quinonez / Far Finer LLC

See [LICENSE](LICENSE) for details.
