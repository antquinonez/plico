# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Document parsing and caching with checksum-based deduplication.

Handles parsing of text files directly and non-text files via LlamaParse,
with parquet-based caching using SHA256 checksums for validation.
Optional RAG indexing via FFRAGClient for semantic search.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from ..config import get_config

if TYPE_CHECKING:
    from ..RAG import FFRAGClient

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document parsing and caching with checksum-based deduplication.

    Documents are parsed (via LlamaParse for non-text files) and stored as
    parquet files. The parquet filename includes the first N characters of
    the SHA256 checksum to enable cache validation.

    Optionally indexes documents to RAG for semantic search.

    Attributes:
        cache_dir: Directory where parquet files are stored
        api_key: LlamaParse API key (from LLAMACLOUD_TOKEN env var)
        checksum_length: Number of checksum chars to use in filename
        rag_client: Optional FFRAGClient for RAG indexing

    """

    PARQUET_SCHEMA = {
        "reference_name": pl.Utf8,
        "common_name": pl.Utf8,
        "original_path": pl.Utf8,
        "checksum": pl.Utf8,
        "content": pl.Utf8,
        "parsed_at": pl.Datetime,
        "file_size": pl.Int64,
    }

    def __init__(
        self,
        cache_dir: str,
        api_key: str | None = None,
        checksum_length: int | None = None,
        rag_client: FFRAGClient | None = None,
    ) -> None:
        """Initialize the DocumentProcessor.

        Args:
            cache_dir: Directory for parquet cache files.
            api_key: LlamaParse API key (defaults to LLAMACLOUD_TOKEN env var).
            checksum_length: Number of checksum chars to use in filenames. Uses config if None.
            rag_client: Optional FFRAGClient for RAG indexing.

        """
        self.cache_dir = Path(cache_dir)
        self.api_key = api_key or os.environ.get("LLAMACLOUD_TOKEN")
        self.rag_client = rag_client

        config = get_config()
        self.checksum_length = (
            checksum_length
            if checksum_length is not None
            else config.document_processor.checksum_length
        )
        self._text_extensions = config.document_processor.text_extensions

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentProcessor initialized with cache_dir={cache_dir}")

    @property
    def TEXT_EXTENSIONS(self) -> set[str]:
        """Get text extensions from config."""
        return self._text_extensions

    def compute_checksum(self, file_path: str) -> str:
        """Compute SHA256 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            Full 64-character hex string of the checksum

        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_checksum_prefix(self, checksum: str) -> str:
        """Get the first N characters of checksum for filename."""
        return checksum[: self.checksum_length]

    def get_parquet_path(self, checksum: str, base_name: str) -> Path:
        """Generate parquet file path from checksum and base name.

        Format: {checksum_prefix}|{sanitized_base_name}.parquet
        """
        safe_name = self._sanitize_name(base_name)
        filename = f"{self.get_checksum_prefix(checksum)}@{safe_name}.parquet"
        return self.cache_dir / filename

    def _sanitize_name(self, name: str) -> str:
        """Sanitize filename by removing/replacing problematic characters."""
        name = Path(name).stem
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    def needs_parsing(self, file_path: str, reference_name: str) -> bool:
        """Check if a document needs to be (re)parsed.

        Returns True if:
        - No parquet file exists for this document, OR
        - Existing parquet has different checksum

        Args:
            file_path: Path to source document
            reference_name: Reference name to look up in parquet

        Returns:
            True if document needs parsing, False if cached version is valid

        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        current_checksum = self.compute_checksum(file_path)
        parquet_path = self.get_parquet_path(current_checksum, reference_name)

        if not parquet_path.exists():
            logger.debug(f"No cached parquet found for {reference_name}")
            return True

        try:
            df = pl.read_parquet(parquet_path)
            if df.is_empty():
                return True

            cached_checksum = df.select("checksum").item(0, 0)
            if cached_checksum != current_checksum:
                logger.info(f"Checksum mismatch for {reference_name}, needs re-parsing")
                return True

            logger.debug(f"Cached version is valid for {reference_name}")
            return False

        except Exception as e:
            logger.warning(f"Error reading cached parquet: {e}, will re-parse")
            return True

    def parse_document(self, file_path: str) -> str:
        """Parse a document and return its content as markdown.

        For text files, reads directly. For other files, uses LlamaParse.

        Args:
            file_path: Path to the document

        Returns:
            Document content as markdown string

        """
        ext = Path(file_path).suffix.lower()

        if ext in self.TEXT_EXTENSIONS:
            return self._parse_text_file(file_path)
        else:
            return self._parse_with_llama(file_path)

    def _parse_text_file(self, file_path: str) -> str:
        """Read a text file directly."""
        logger.info(f"Reading text file directly: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            import chardet

            with open(file_path, "rb") as f:
                raw = f.read()
            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "utf-8") or "utf-8"
            logger.debug(f"Detected encoding: {encoding}")
            return raw.decode(encoding)

    def _parse_with_llama(self, file_path: str) -> str:
        """Parse a document using LlamaParse."""
        if not self.api_key:
            raise ValueError(
                "LlamaParse API key required. Set LLAMACLOUD_TOKEN environment variable."
            )

        logger.info(f"Parsing with LlamaParse: {file_path}")

        try:
            from llama_cloud_services import LlamaParse
            from llama_index.core import SimpleDirectoryReader

            parser = LlamaParse(result_type="markdown", api_key=self.api_key)

            ext = Path(file_path).suffix.lower()
            file_extractor = {ext: parser}

            documents = SimpleDirectoryReader(
                input_files=[file_path], file_extractor=file_extractor
            ).load_data()

            if documents and len(documents) > 0:
                content = documents[0].text

                if hasattr(documents[0], "metadata") and "markdown" in documents[0].metadata:
                    content = documents[0].metadata["markdown"]

                return content
            else:
                raise ValueError(f"No content parsed from {file_path}")

        except ImportError as e:
            raise ImportError(
                "LlamaParse not installed. Install with: pip install llama-cloud-services"
            ) from e

    def store_document(
        self, file_path: str, reference_name: str, common_name: str, content: str
    ) -> str:
        """Store parsed document content as a parquet file.

        Args:
            file_path: Original file path
            reference_name: Reference name for the document
            common_name: Human-readable name
            content: Parsed content (markdown)

        Returns:
            Path to the created parquet file

        """
        checksum = self.compute_checksum(file_path)
        file_size = os.path.getsize(file_path)
        parquet_path = self.get_parquet_path(checksum, reference_name)

        df = pl.DataFrame(
            {
                "reference_name": [reference_name],
                "common_name": [common_name],
                "original_path": [os.path.abspath(file_path)],
                "checksum": [checksum],
                "content": [content],
                "parsed_at": [datetime.now()],
                "file_size": [file_size],
            }
        )

        df.write_parquet(parquet_path)
        logger.info(f"Stored document parquet: {parquet_path}")

        return str(parquet_path)

    def index_to_rag(
        self,
        reference_name: str,
        common_name: str,
        content: str,
        checksum: str,
        force: bool = False,
        tags: list[str] | None = None,
        chunking_strategy: str | None = None,
    ) -> int:
        """Index document content to RAG for semantic search.

        This is the preferred method for indexing documents. It checks
        if reindexing is needed and only indexes when necessary.

        Args:
            reference_name: Reference name for the document
            common_name: Human-readable name
            content: Document content to index
            checksum: Document checksum for change detection
            force: Force reindexing even if document appears unchanged
            tags: Optional list of tags for filtering
            chunking_strategy: Optional chunking strategy override

        Returns:
            Number of chunks indexed, or 0 if RAG is not configured or skipped

        """
        logger.debug(
            f"index_to_rag called: rag_client={self.rag_client is not None}, "
            f"ref={reference_name}, checksum={checksum[:8]}..."
        )
        if not self.rag_client:
            logger.info("RAG client not configured, skipping indexing")
            return 0

        try:
            chunks_added = self.rag_client.index_document(
                content=content,
                reference_name=reference_name,
                common_name=common_name,
                checksum=checksum,
                force=force,
                tags=tags,
                chunking_strategy=chunking_strategy,
            )
            if chunks_added > 0:
                logger.info(f"Indexed {chunks_added} chunks to RAG for: {reference_name}")
            else:
                logger.debug(f"Document {reference_name} already indexed, skipped")
            return chunks_added
        except Exception as e:
            logger.warning(f"Failed to index document to RAG: {e}")
            return 0

    def load_document(self, parquet_path: str) -> dict[str, Any]:
        """Load document data from a parquet file.

        Args:
            parquet_path: Path to parquet file

        Returns:
            Dictionary with document data

        """
        df = pl.read_parquet(parquet_path)

        if df.is_empty():
            raise ValueError(f"Empty parquet file: {parquet_path}")

        row = df.row(0, named=True)
        return dict(row)

    def get_document_content(self, file_path: str, reference_name: str, common_name: str) -> str:
        """Get document content, parsing only if needed.

        This is the main entry point for document retrieval.
        Checks checksum to determine if re-parsing is needed.
        Does NOT index to RAG - use index_to_rag() separately.

        Args:
            file_path: Path to source document
            reference_name: Reference name
            common_name: Human-readable name

        Returns:
            Document content as markdown

        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        checksum = self.compute_checksum(file_path)
        parquet_path = self.get_parquet_path(checksum, reference_name)

        if not self.needs_parsing(file_path, reference_name):
            logger.info(f"Using cached document: {reference_name}")
            doc_data = self.load_document(str(parquet_path))
            return doc_data["content"]

        logger.info(f"Parsing document: {reference_name}")
        content = self.parse_document(file_path)
        self.store_document(file_path, reference_name, common_name, content)

        return content

    def get_document_checksum(self, file_path: str) -> str:
        """Get checksum for a document file.

        Args:
            file_path: Path to the document file.

        Returns:
            SHA256 checksum string.

        """
        return self.compute_checksum(file_path)

    def clear_cache(self) -> int:
        """Clear all cached parquet files.

        Returns:
            Number of files deleted

        """
        count = 0
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
            count += 1
        logger.info(f"Cleared {count} cached parquet files")
        return count
