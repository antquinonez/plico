# Product Specification: FFClients Orchestrator

## Overview
FFClients Orchestrator is a Python-based system for managing AI prompt execution through Excel workbooks.

## Key Features

### 1. Multi-Client Support
- Supports multiple AI providers (Mistral, Anthropic, OpenAI, Azure, Gemini)
- Configurable client profiles with different temperature and token settings
- Per-prompt client assignment

### 2. Batch Processing
- Process multiple data rows through the same prompt chain
- Variable templating with {{variable}} syntax
- Parallel or sequential batch execution

### 3. Document References
- Reference external documents in prompts
- Automatic parsing with LlamaParse for non-text files
- Checksum-based caching in parquet format

## Technical Requirements
- Python 3.10+
- Dependencies: polars, openpyxl, anthropic, mistralai, openai

## Version History
- v1.0.0: Initial release
- v1.1.0: Added document reference system
