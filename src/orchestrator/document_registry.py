"""Document registry for managing document definitions and content retrieval.

Validates document references and provides content injection for prompts
referencing external documents via the 'documents' workbook sheet.
"""

import logging
import os
from pathlib import Path
from typing import Any

from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class DocumentRegistry:
    """Manages document definitions and content retrieval for prompt references.

    Documents are defined in the workbook's 'documents' sheet and processed
    through the DocumentProcessor. This registry validates all references
    and provides content for prompt injection.

    Attributes:
        documents: Dictionary mapping reference_name to document config
        processor: DocumentProcessor instance for parsing/caching
        workbook_dir: Directory containing the workbook (for relative paths)

    """

    def __init__(
        self,
        documents: list[dict[str, Any]],
        processor: DocumentProcessor,
        workbook_dir: str,
    ) -> None:
        """Initialize the document registry.

        Args:
            documents: List of document configs from workbook sheet.
            processor: DocumentProcessor for parsing documents.
            workbook_dir: Directory containing the workbook.

        """
        self.processor = processor
        self.workbook_dir = Path(workbook_dir).resolve()
        self.documents: dict[str, dict[str, Any]] = {}
        self._content_cache: dict[str, str] = {}

        for doc in documents:
            ref_name = doc.get("reference_name")
            if ref_name:
                self.documents[ref_name] = doc

        logger.info(f"DocumentRegistry initialized with {len(self.documents)} documents")

    def resolve_path(self, file_path: str) -> str:
        """Resolve a file path relative to the workbook directory.

        Args:
            file_path: Path from the documents sheet (may be relative)

        Returns:
            Absolute path to the document

        """
        path = Path(file_path)

        if path.is_absolute():
            return str(path)

        resolved = (self.workbook_dir / path).resolve()
        return str(resolved)

    def validate_documents(self) -> list[str]:
        """Validate that all registered documents exist on disk.

        Returns:
            List of reference names that are valid

        Raises:
            FileNotFoundError: If any document file doesn't exist

        """
        missing = []
        valid = []

        for ref_name, doc in self.documents.items():
            file_path = self.resolve_path(doc.get("file_path", ""))
            if not os.path.exists(file_path):
                missing.append(f"{ref_name}: {file_path}")
            else:
                valid.append(ref_name)

        if missing:
            raise FileNotFoundError("Document(s) not found:\n" + "\n".join(missing))

        logger.info(f"All {len(valid)} documents validated")
        return valid

    def get_reference_names(self) -> set[str]:
        """Get all registered reference names."""
        return set(self.documents.keys())

    def get_document_config(self, reference_name: str) -> dict[str, Any] | None:
        """Get the configuration for a document by reference name."""
        return self.documents.get(reference_name)

    def get_content(self, reference_name: str) -> str:
        """Get the content of a document by reference name.

        Uses the DocumentProcessor for parsing/caching. Results are
        cached in memory for the session.

        Args:
            reference_name: The reference name from the documents sheet

        Returns:
            Document content as markdown string

        Raises:
            KeyError: If reference_name not found
            FileNotFoundError: If document file doesn't exist

        """
        if reference_name in self._content_cache:
            return self._content_cache[reference_name]

        if reference_name not in self.documents:
            raise KeyError(f"Document reference not found: {reference_name}")

        doc = self.documents[reference_name]
        file_path = self.resolve_path(doc.get("file_path", ""))
        common_name = doc.get("common_name", reference_name)

        content = self.processor.get_document_content(
            file_path=file_path, reference_name=reference_name, common_name=common_name
        )

        self._content_cache[reference_name] = content
        return content

    def get_all_content(self, reference_names: list[str]) -> dict[str, str]:
        """Get content for multiple documents.

        Args:
            reference_names: List of reference names

        Returns:
            Dictionary mapping reference names to content

        """
        result = {}
        for ref_name in reference_names:
            try:
                result[ref_name] = self.get_content(ref_name)
            except (KeyError, FileNotFoundError) as e:
                logger.error(f"Failed to get content for {ref_name}: {e}")
                raise
        return result

    def format_references_block(self, reference_names: list[str]) -> str:
        """Format document content as an XML references block.

        Output format:
        <REFERENCES>
        <DOC name='ref1'>
        content...
        </DOC>

        <DOC name='ref2'>
        content...
        </DOC>
        </REFERENCES>

        Args:
            reference_names: List of reference names to include

        Returns:
            Formatted XML string

        """
        if not reference_names:
            return ""

        docs_content = self.get_all_content(reference_names)

        doc_blocks = []
        for ref_name in reference_names:
            if ref_name in docs_content:
                content = docs_content[ref_name]
                doc_blocks.append(f"<DOC name='{ref_name}'>\n{content}\n</DOC>")

        if not doc_blocks:
            return ""

        return "<REFERENCES>\n" + "\n\n".join(doc_blocks) + "\n</REFERENCES>"

    def inject_references_into_prompt(self, prompt: str, reference_names: list[str] | None) -> str:
        """Inject document references into a prompt.

        Format:
        <REFERENCES>
        <DOC name='...'>content</DOC>
        </REFERENCES>

        ===
        Based on the documents above, please answer: [original prompt]

        Args:
            prompt: Original prompt text
            reference_names: List of document reference names

        Returns:
            Prompt with injected document references

        """
        if not reference_names:
            return prompt

        refs_block = self.format_references_block(reference_names)

        if not refs_block:
            return prompt

        return f"{refs_block}\n\n===\nBased on the documents above, please answer: {prompt}"

    def clear_cache(self) -> None:
        """Clear the in-memory content cache."""
        self._content_cache.clear()
        logger.info("Document content cache cleared")
