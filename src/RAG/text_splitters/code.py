# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Code-aware text chunking using AST-style parsing."""

from __future__ import annotations

import logging
import re
from typing import Any

from .base import ChunkerBase, TextChunk

logger = logging.getLogger(__name__)


class CodeChunker(ChunkerBase):
    """Code-aware chunking that splits by functions/classes.

    Attempts to split code by structural boundaries (functions, classes)
    while respecting chunk size limits.

    Args:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        metadata: Default metadata for all chunks.
        language: Programming language for parsing hints.
        split_by: Strategy: "function", "class", or "module".

    """

    LANGUAGE_PATTERNS = {
        "python": {
            "function": r"^(async\s+)?def\s+\w+\s*\(",
            "class": r"^class\s+\w+[\(:]",
            "import": r"^(import\s+|from\s+\S+\s+import)",
            "decorator": r"^@\w+",
            "comment": r"^(#|'''|\"\"\")",
        },
        "javascript": {
            "function": r"^(async\s+)?function\s+\w+|const\s+\w+\s*=\s*(async\s+)?\([^)]*\)\s*=>|export\s+(async\s+)?function",
            "class": r"^(export\s+)?class\s+\w+",
            "import": r"^(import\s+|export\s+|require\s*\()",
            "comment": r"^(//|/\*|\*)",
        },
        "typescript": {
            "function": r"^(async\s+)?(function\s+\w+|const\s+\w+\s*=\s*(async\s+)?\([^)]*\)\s*(:\s*\w+)?\s*=>|export\s+(async\s+)?function)",
            "class": r"^(export\s+)?(abstract\s+)?class\s+\w+|interface\s+\w+|type\s+\w+",
            "import": r"^(import\s+|export\s+|require\s*\()",
            "comment": r"^(//|/\*|\*)",
        },
        "java": {
            "function": r"^\s*(public|private|protected|static)?\s*\w+\s+\w+\s*\(",
            "class": r"^\s*(public\s+)?(abstract\s+)?class\s+\w+|interface\s+\w+",
            "import": r"^import\s+",
            "comment": r"^(//|/\*)",
        },
        "go": {
            "function": r"^func\s+(\(\w+\s+\*?\w+\)\s+)?\w+\s*\(",
            "class": r"^type\s+\w+\s+struct",
            "import": r"^import\s+",
            "comment": r"^(//|/\*)",
        },
        "rust": {
            "function": r"^(pub\s+)?(async\s+)?fn\s+\w+",
            "class": r"^(pub\s+)?struct\s+\w+|impl\s+\w+",
            "import": r"^use\s+",
            "comment": r"^(//|/\*|\*)",
        },
        "generic": {
            "function": r"^(function|func|def|fn)\s+\w+",
            "class": r"^(class|struct|interface)\s+\w+",
            "import": r"^(import|use|require)",
            "comment": r"^(#|//|/\*)",
        },
    }

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        metadata: dict[str, Any] | None = None,
        language: str = "python",
        split_by: str = "function",
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, metadata)
        self.language = language.lower()
        self.split_by = split_by
        self.patterns = self.LANGUAGE_PATTERNS.get(self.language, self.LANGUAGE_PATTERNS["generic"])
        self._validate_params()

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split code by structural boundaries.

        Args:
            text: The code text to split.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of TextChunk objects.

        """
        if not text or not text.strip():
            return []

        merged_metadata = self._merge_metadata(metadata)
        merged_metadata["language"] = self.language

        blocks = self._extract_code_blocks(text)

        if not blocks:
            return self._fallback_chunk(text, merged_metadata)

        chunks: list[TextChunk] = []

        for block in blocks:
            block_text = block["content"]
            block_start = block["start"]
            block_end = block["end"]

            if len(block_text) <= self.chunk_size:
                chunks.append(
                    TextChunk(
                        content=block_text,
                        chunk_index=len(chunks),
                        start_char=block_start,
                        end_char=block_end,
                        metadata={
                            **merged_metadata,
                            "block_type": block.get("type", "unknown"),
                            "block_name": block.get("name", ""),
                        },
                    )
                )
            else:
                sub_chunks = self._split_large_block(block, merged_metadata)
                chunks.extend(sub_chunks)

        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap_context(chunks)

        logger.debug(
            f"CodeChunker: {len(chunks)} chunks (language={self.language}, split_by={self.split_by})"
        )
        return chunks

    def _extract_code_blocks(self, text: str) -> list[dict[str, Any]]:
        """Extract code blocks based on patterns."""
        lines = text.split("\n")
        blocks: list[dict[str, Any]] = []

        current_block: dict[str, Any] | None = None
        current_content: list[str] = []

        patterns_to_check = []
        if self.split_by == "class":
            patterns_to_check = ["class", "function"]
        elif self.split_by == "function":
            patterns_to_check = ["function"]
        else:
            patterns_to_check = ["class", "function"]

        for i, line in enumerate(lines):
            matched = False

            for block_type in patterns_to_check:
                pattern = self.patterns.get(block_type, "")
                if pattern and re.match(pattern, line.lstrip()):
                    if current_block and current_content:
                        current_block["content"] = "\n".join(current_content)
                        current_block["end"] = sum(len(line) + 1 for line in lines[:i])
                        blocks.append(current_block)

                    block_name = self._extract_name(line, block_type)
                    current_block = {
                        "type": block_type,
                        "name": block_name,
                        "start": sum(len(line) + 1 for line in lines[:i]),
                    }
                    current_content = [line]
                    matched = True
                    break

            if not matched:
                if current_block:
                    current_content.append(line)
                elif not blocks:
                    if i == 0:
                        current_block = {
                            "type": "module_level",
                            "name": "",
                            "start": 0,
                        }
                        current_content = [line]
                    else:
                        pass

        if current_block and current_content:
            current_block["content"] = "\n".join(current_content)
            current_block["end"] = len(text)
            blocks.append(current_block)

        return blocks

    def _extract_name(self, line: str, block_type: str) -> str:
        """Extract the name of a function or class."""
        stripped = line.lstrip()

        if block_type == "function":
            match = re.search(r"\b([a-zA-Z_]\w*)\s*\(", stripped)
            if match:
                return match.group(1)
        elif block_type == "class":
            match = re.search(r"\bclass\s+([a-zA-Z_]\w*)", stripped)
            if match:
                return match.group(1)

        return ""

    def _split_large_block(
        self,
        block: dict[str, Any],
        metadata: dict[str, Any],
    ) -> list[TextChunk]:
        """Split a large code block into smaller chunks."""
        chunks: list[TextChunk] = []
        content = block["content"]
        start_offset = block["start"]

        lines = content.split("\n")
        current_chunk_lines: list[str] = []
        current_size = 0
        chunk_start_line = 0

        for i, line in enumerate(lines):
            line_size = len(line) + 1

            if current_size + line_size > self.chunk_size and current_chunk_lines:
                chunk_content = "\n".join(current_chunk_lines)
                chunks.append(
                    TextChunk(
                        content=chunk_content,
                        chunk_index=len(chunks),
                        start_char=start_offset
                        + sum(len(ln) + 1 for ln in lines[:chunk_start_line]),
                        end_char=start_offset + sum(len(ln) + 1 for ln in lines[:i]),
                        metadata={
                            **metadata,
                            "block_type": block.get("type", "unknown"),
                            "block_name": block.get("name", ""),
                            "chunk_part": len(chunks) + 1,
                        },
                    )
                )

                overlap_lines = self._get_overlap_lines(current_chunk_lines)
                current_chunk_lines = overlap_lines
                current_size = sum(len(ln) + 1 for ln in overlap_lines)
                chunk_start_line = i - len(overlap_lines)

            current_chunk_lines.append(line)
            current_size += line_size

        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunks.append(
                TextChunk(
                    content=chunk_content,
                    chunk_index=len(chunks),
                    start_char=start_offset + sum(len(ln) + 1 for ln in lines[:chunk_start_line]),
                    end_char=len(content),
                    metadata={
                        **metadata,
                        "block_type": block.get("type", "unknown"),
                        "block_name": block.get("name", ""),
                        "chunk_part": len(chunks) + 1 if len(chunks) > 0 else 1,
                    },
                )
            )

        return chunks

    def _get_overlap_lines(self, lines: list[str]) -> list[str]:
        """Get lines for overlap based on chunk_overlap size."""
        if not lines or self.chunk_overlap <= 0:
            return []

        overlap_size = 0
        overlap_lines: list[str] = []

        for line in reversed(lines):
            if overlap_size + len(line) + 1 > self.chunk_overlap:
                break
            overlap_lines.insert(0, line)
            overlap_size += len(line) + 1

        return overlap_lines

    def _fallback_chunk(self, text: str, metadata: dict[str, Any]) -> list[TextChunk]:
        """Fallback to line-based chunking when no blocks detected."""
        chunks: list[TextChunk] = []
        lines = text.split("\n")
        current_lines: list[str] = []
        current_size = 0
        chunk_start = 0

        for _i, line in enumerate(lines):
            line_size = len(line) + 1

            if current_size + line_size > self.chunk_size and current_lines:
                chunk_content = "\n".join(current_lines)
                chunks.append(
                    TextChunk(
                        content=chunk_content,
                        chunk_index=len(chunks),
                        start_char=chunk_start,
                        end_char=chunk_start + len(chunk_content),
                        metadata={
                            **metadata,
                            "block_type": "fallback",
                            "block_name": "",
                        },
                    )
                )

                overlap_lines = self._get_overlap_lines(current_lines)
                current_lines = overlap_lines
                current_size = sum(len(ln) + 1 for ln in overlap_lines)
                chunk_start = (
                    chunk_start + len(chunk_content) - sum(len(ln) + 1 for ln in overlap_lines)
                )

            current_lines.append(line)
            current_size += line_size

        if current_lines:
            chunk_content = "\n".join(current_lines)
            chunks.append(
                TextChunk(
                    content=chunk_content,
                    chunk_index=len(chunks),
                    start_char=chunk_start,
                    end_char=len(text),
                    metadata={
                        **metadata,
                        "block_type": "fallback",
                        "block_name": "",
                    },
                )
            )

        return chunks

    def _add_overlap_context(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Add context comments for overlap (optional enhancement)."""
        return chunks
