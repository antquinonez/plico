# Technical Specification

## Overview
This document describes the API requirements for the document reference system.

## Features
- Document parsing with LlamaParse
- Checksum-based caching
- Parquet storage for parsed content

## API Endpoints

### POST /parse
Parse a document and return markdown content.

Request:
```json
{
  "file_path": "/path/to/document.pdf",
  "reference_name": "spec_doc"
}
```

Response:
```json
{
  "content": "# Document Title\n\n...",
  "checksum": "a3f2b1c8..."
}
```

## Version
1.0.0
