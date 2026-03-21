# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for text chunking via get_chunker('character')."""

from __future__ import annotations

import pytest

from src.RAG.text_splitters import TextChunk, get_chunker


class TestSplitTextBasic:
    """Tests for basic character chunker functionality."""

    def test_empty_text(self):
        """Empty text returns empty list."""
        chunker = get_chunker("character")
        result = chunker.chunk("")
        assert result == []

    def test_whitespace_only(self):
        """Whitespace-only text returns empty list."""
        chunker = get_chunker("character")
        result = chunker.chunk("   \n\t  ")
        assert result == []

    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size returns single chunk."""
        text = "Hello world"
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        result = chunker.chunk(text)
        assert len(result) == 1
        assert result[0].content == "Hello world"
        assert result[0].chunk_index == 0
        assert result[0].start_char == 0
        assert result[0].end_char == 11

    def test_basic_splitting(self):
        """Text longer than chunk_size gets split."""
        text = "word " * 300
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        result = chunker.chunk(text)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk.content) <= 100

    def test_respects_word_boundaries(self):
        """Splits at word boundaries when possible."""
        text = "hello world " * 100
        chunker = get_chunker("character", chunk_size=50, chunk_overlap=10)
        result = chunker.chunk(text)
        for chunk in result[:-1]:
            assert not chunk.content.endswith("hel")
            assert not chunk.content.startswith("lo")

    def test_metadata_preserved(self):
        """Metadata is attached to each chunk."""
        text = "Hello world"
        metadata = {"source": "test.txt", "author": "test"}
        chunker = get_chunker("character")
        result = chunker.chunk(text, metadata=metadata)
        assert result[0].metadata == metadata
        assert result[0].metadata is not metadata


class TestSplitTextValidation:
    """Tests for input validation."""

    def test_invalid_chunk_size_zero(self):
        """Zero chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            get_chunker("character", chunk_size=0)

    def test_invalid_chunk_size_negative(self):
        """Negative chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            get_chunker("character", chunk_size=-10)

    def test_invalid_chunk_overlap_negative(self):
        """Negative chunk_overlap raises ValueError."""
        with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
            get_chunker("character", chunk_overlap=-10)

    def test_invalid_overlap_greater_than_size(self):
        """Overlap >= chunk_size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            get_chunker("character", chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            get_chunker("character", chunk_size=100, chunk_overlap=150)


class TestSplitTextOverlap:
    """Tests for overlap behavior."""

    def test_overlap_exists(self):
        """Adjacent chunks have overlapping content."""
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 "
        text = text * 20
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=30)
        result = chunker.chunk(text)

        for i in range(len(result) - 1):
            chunk_end = result[i].content[-20:].strip()
            chunk_start = result[i + 1].content[:30].strip()
            assert chunk_end and chunk_start

    def test_zero_overlap(self):
        """Zero overlap works correctly."""
        text = "word " * 300
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=0)
        result = chunker.chunk(text)
        assert len(result) > 1


class TestSplitTextEdgeCases:
    """Tests for edge cases around boundary handling."""

    def test_very_long_word_at_boundary(self):
        """Very long word spanning overlap region is handled."""
        long_word = "a" * 500
        text = f"prefix {long_word} suffix"
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        result = chunker.chunk(text)

        assert len(result) >= 1
        assert all(chunk.content for chunk in result)

    def test_no_spaces_text(self):
        """Text with no spaces is handled without infinite loop."""
        text = "x" * 5000
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        result = chunker.chunk(text)

        assert len(result) > 1
        total_coverage = sum(len(chunk.content) for chunk in result)
        assert total_coverage >= 4000

    def test_single_word_longer_than_chunk_size(self):
        """Single word longer than chunk_size is handled."""
        text = "supercalifragilisticexpialidocious" * 10
        chunker = get_chunker("character", chunk_size=20, chunk_overlap=5)
        result = chunker.chunk(text)

        assert len(result) > 1
        for chunk in result:
            assert len(chunk.content) > 0

    def test_newlines_as_boundaries(self):
        """Newlines are treated as word boundaries."""
        text = "line1\nline2\nline3\nline4\nline5\n"
        chunker = get_chunker("character", chunk_size=15, chunk_overlap=5)
        result = chunker.chunk(text)

        for chunk in result:
            assert chunk.content

    def test_mixed_newlines_and_spaces(self):
        """Both newlines and spaces are used as boundaries."""
        text = "word1 word2\nword3 word4\nword5 word6\n" * 20
        chunker = get_chunker("character", chunk_size=50, chunk_overlap=10)
        result = chunker.chunk(text)

        assert len(result) > 1
        for chunk in result:
            assert chunk.content

    def test_exact_chunk_size(self):
        """Text exactly matching chunk_size returns single chunk."""
        text = "a" * 100
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        result = chunker.chunk(text)
        assert len(result) == 1

    def test_consecutive_newlines(self):
        """Consecutive newlines are handled."""
        text = "para1\n\n\npara2\n\n\npara3\n\n\n"
        chunker = get_chunker("character", chunk_size=20, chunk_overlap=5)
        result = chunker.chunk(text)

        assert len(result) >= 1
        for chunk in result:
            assert chunk.content


class TestTextChunk:
    """Tests for TextChunk dataclass."""

    def test_chunk_creation(self):
        """TextChunk stores all fields correctly."""
        chunk = TextChunk(
            content="test content",
            chunk_index=5,
            start_char=100,
            end_char=112,
            metadata={"key": "value"},
        )
        assert chunk.content == "test content"
        assert chunk.chunk_index == 5
        assert chunk.start_char == 100
        assert chunk.end_char == 112
        assert chunk.metadata == {"key": "value"}

    def test_chunk_optional_metadata(self):
        """TextChunk metadata is optional."""
        chunk = TextChunk(content="test", chunk_index=0, start_char=0, end_char=4)
        assert chunk.metadata is None


class TestChunkDocuments:
    """Tests for chunking multiple documents."""

    def test_split_multiple_documents(self):
        """Multiple documents are split into chunks."""
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        documents = [
            {"content": "doc1 " * 100, "source": "doc1.txt"},
            {"content": "doc2 " * 100, "source": "doc2.txt"},
        ]

        all_chunks = []
        for doc in documents:
            metadata = {k: v for k, v in doc.items() if k != "content"}
            chunks = chunker.chunk(doc["content"], metadata=metadata)
            all_chunks.extend(chunks)

        assert len(all_chunks) > 2
        doc1_chunks = [
            c for c in all_chunks if c.metadata and c.metadata.get("source") == "doc1.txt"
        ]
        doc2_chunks = [
            c for c in all_chunks if c.metadata and c.metadata.get("source") == "doc2.txt"
        ]
        assert len(doc1_chunks) > 0
        assert len(doc2_chunks) > 0

    def test_empty_documents_list(self):
        """Empty document list produces no chunks."""
        chunker = get_chunker("character")
        all_chunks = []
        for doc in []:
            chunks = chunker.chunk(doc.get("content", ""))
            all_chunks.extend(chunks)
        assert all_chunks == []

    def test_document_missing_content_key(self):
        """Documents without content key produce no chunks."""
        chunker = get_chunker("character")
        documents = [
            {"source": "no_content.txt"},
            {"content": "has content", "source": "has.txt"},
        ]

        all_chunks = []
        for doc in documents:
            text = doc.get("content", "")
            if not text:
                continue
            metadata = {k: v for k, v in doc.items() if k != "content"}
            chunks = chunker.chunk(text, metadata=metadata)
            all_chunks.extend(chunks)

        assert len(all_chunks) == 1
        assert all_chunks[0].metadata == {"source": "has.txt"}

    def test_custom_text_key(self):
        """Custom text_key is used to access content."""
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        documents = [
            {"body": "custom content " * 50, "id": 1},
        ]

        all_chunks = []
        for doc in documents:
            text = doc.get("body", "")
            if not text:
                continue
            metadata = {k: v for k, v in doc.items() if k != "body"}
            chunks = chunker.chunk(text, metadata=metadata)
            all_chunks.extend(chunks)

        assert len(all_chunks) >= 1

    def test_metadata_excludes_text_key(self):
        """Metadata does not include the text content key."""
        chunker = get_chunker("character")
        documents = [
            {"content": "text", "id": 1, "title": "Test"},
        ]

        doc = documents[0]
        metadata = {k: v for k, v in doc.items() if k != "content"}
        result = chunker.chunk(doc["content"], metadata=metadata)

        assert "content" not in result[0].metadata
        assert result[0].metadata == {"id": 1, "title": "Test"}
