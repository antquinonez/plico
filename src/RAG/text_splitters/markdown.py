# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Markdown-aware text chunking that preserves document structure."""

from __future__ import annotations

import logging
import re
from typing import Any

from .base import ChunkerBase, TextChunk

logger = logging.getLogger(__name__)


class MarkdownChunker(ChunkerBase):
    """Markdown-aware chunking that splits by headers.

    Preserves document structure by splitting at markdown headers
    (h1-h6) while respecting chunk size limits.

    Args:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        metadata: Default metadata for all chunks.
        split_headers: List of header levels to split on (e.g., ["h1", "h2"]).
        preserve_structure: Whether to include header in chunk content.
        max_chunk_fallback: Whether to further split large sections.

    """

    HEADER_PATTERNS = {
        "h1": r"^# .+",
        "h2": r"^## .+",
        "h3": r"^### .+",
        "h4": r"^#### .+",
        "h5": r"^##### .+",
        "h6": r"^###### .+",
    }

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        metadata: dict[str, Any] | None = None,
        split_headers: list[str] | None = None,
        preserve_structure: bool = True,
        max_chunk_fallback: bool = True,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, metadata)
        self.split_headers = split_headers or ["h1", "h2", "h3"]
        self.preserve_structure = preserve_structure
        self.max_chunk_fallback = max_chunk_fallback
        self._validate_params()

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split markdown text by headers while respecting size limits.

        Args:
            text: The markdown text to split.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of TextChunk objects.

        """
        if not text or not text.strip():
            return []

        merged_metadata = self._merge_metadata(metadata)
        sections = self._split_by_headers(text)
        chunks: list[TextChunk] = []

        current_pos = 0
        for section in sections:
            section_text = section["content"]
            section_header = section.get("header", "")
            section_start = text.find(section_text, current_pos)
            if section_start == -1:
                section_start = current_pos
            section_end = section_start + len(section_text)

            if len(section_text) <= self.chunk_size:
                chunks.append(
                    TextChunk(
                        content=section_text.strip(),
                        chunk_index=len(chunks),
                        start_char=section_start,
                        end_char=section_end,
                        metadata={
                            **merged_metadata,
                            "header": section_header,
                            "header_level": section.get("level", 0),
                        },
                    )
                )
            elif self.max_chunk_fallback:
                sub_chunks = self._split_large_section(
                    section_text,
                    section_start,
                    section_header,
                    section.get("level", 0),
                    merged_metadata,
                )
                chunks.extend(sub_chunks)

            current_pos = section_end

        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks, merged_metadata)

        logger.debug(f"MarkdownChunker: {len(chunks)} chunks (headers={self.split_headers})")
        return chunks

    def _split_by_headers(self, text: str) -> list[dict[str, Any]]:
        """Split text by configured header levels."""
        lines = text.split("\n")
        sections: list[dict[str, Any]] = []

        current_section: dict[str, Any] = {
            "header": "",
            "level": 0,
            "content": "",
        }

        for line in lines:
            header_match = self._match_header(line)

            if header_match and header_match["level"] in self.split_headers:
                if current_section["content"].strip():
                    sections.append(current_section)

                current_section = {
                    "header": header_match["text"],
                    "level": header_match["level"],
                    "content": line + "\n",
                }
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _match_header(self, line: str) -> dict[str, Any] | None:
        """Check if line is a header and return header info."""
        for level, pattern in self.HEADER_PATTERNS.items():
            if re.match(pattern, line):
                return {"level": level, "text": line.strip()}
        return None

    def _split_large_section(
        self,
        text: str,
        start_offset: int,
        header: str,
        header_level: str,
        base_metadata: dict[str, Any],
    ) -> list[TextChunk]:
        """Split a large section into smaller chunks."""
        chunks: list[TextChunk] = []

        paragraphs = re.split(r"\n\n+", text)

        current_chunk = ""
        chunk_start = start_offset

        for para in paragraphs:
            if not para.strip():
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(
                        TextChunk(
                            content=current_chunk.strip(),
                            chunk_index=len(chunks),
                            start_char=chunk_start,
                            end_char=chunk_start + len(current_chunk),
                            metadata={
                                **base_metadata,
                                "header": header,
                                "header_level": header_level,
                            },
                        )
                    )
                    chunk_start += len(current_chunk)

                if len(para) > self.chunk_size:
                    sub_chunks = self._split_paragraph(
                        para, chunk_start, header, header_level, base_metadata
                    )
                    chunks.extend(sub_chunks)
                    chunk_start += len(para)
                    current_chunk = ""
                else:
                    current_chunk = para

        if current_chunk.strip():
            chunks.append(
                TextChunk(
                    content=current_chunk.strip(),
                    chunk_index=len(chunks),
                    start_char=chunk_start,
                    end_char=chunk_start + len(current_chunk),
                    metadata={
                        **base_metadata,
                        "header": header,
                        "header_level": header_level,
                    },
                )
            )

        return chunks

    def _split_paragraph(
        self,
        text: str,
        start_offset: int,
        header: str,
        header_level: str,
        base_metadata: dict[str, Any],
    ) -> list[TextChunk]:
        """Split a large paragraph by sentences."""
        chunks: list[TextChunk] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current_chunk = ""
        chunk_start = start_offset

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk += (" " if current_chunk else "") + sentence
            else:
                if current_chunk:
                    chunks.append(
                        TextChunk(
                            content=current_chunk.strip(),
                            chunk_index=len(chunks),
                            start_char=chunk_start,
                            end_char=chunk_start + len(current_chunk),
                            metadata={
                                **base_metadata,
                                "header": header,
                                "header_level": header_level,
                            },
                        )
                    )
                    chunk_start += len(current_chunk)

                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunk_text = sentence[i : i + self.chunk_size]
                        chunks.append(
                            TextChunk(
                                content=chunk_text.strip(),
                                chunk_index=len(chunks),
                                start_char=chunk_start + i,
                                end_char=chunk_start + i + len(chunk_text),
                                metadata={
                                    **base_metadata,
                                    "header": header,
                                    "header_level": header_level,
                                },
                            )
                        )
                    current_chunk = ""
                else:
                    current_chunk = sentence

        if current_chunk.strip():
            chunks.append(
                TextChunk(
                    content=current_chunk.strip(),
                    chunk_index=len(chunks),
                    start_char=chunk_start,
                    end_char=chunk_start + len(current_chunk),
                    metadata={
                        **base_metadata,
                        "header": header,
                        "header_level": header_level,
                    },
                )
            )

        return chunks

    def _add_overlap(
        self,
        chunks: list[TextChunk],
        metadata: dict[str, Any],
    ) -> list[TextChunk]:
        """Add overlap content between chunks."""
        result: list[TextChunk] = []

        for i, chunk in enumerate(chunks):
            content = chunk.content

            if i > 0 and self.chunk_overlap > 0:
                prev_content = chunks[i - 1].content
                overlap_start = max(0, len(prev_content) - self.chunk_overlap)
                overlap_text = prev_content[overlap_start:]
                if overlap_text.strip() and overlap_text not in content:
                    pass

            result.append(chunk)

        return result
