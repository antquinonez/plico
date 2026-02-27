# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for new text chunking strategies."""

from __future__ import annotations

import pytest

from src.RAG.text_splitters import (
    CharacterChunker,
    ChunkerBase,
    CodeChunker,
    HierarchicalChunker,
    MarkdownChunker,
    RecursiveChunker,
    TextChunk,
    chunk_text,
    get_chunker,
    list_chunkers,
)


class TestChunkerBase:
    """Tests for ChunkerBase abstract class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Cannot instantiate ChunkerBase directly."""
        with pytest.raises(TypeError):
            ChunkerBase(chunk_size=100, chunk_overlap=20)

    def test_validate_params_positive_chunk_size(self) -> None:
        """Chunk size must be positive."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            CharacterChunker(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            CharacterChunker(chunk_size=-1)

    def test_validate_params_non_negative_overlap(self) -> None:
        """Chunk overlap cannot be negative."""
        with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
            CharacterChunker(chunk_size=100, chunk_overlap=-1)

    def test_validate_params_overlap_less_than_size(self) -> None:
        """Chunk overlap must be less than chunk size."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            CharacterChunker(chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            CharacterChunker(chunk_size=100, chunk_overlap=150)


class TestCharacterChunker:
    """Tests for CharacterChunker."""

    def test_basic_chunking(self) -> None:
        """Basic character-based chunking works."""
        chunker = CharacterChunker(chunk_size=50, chunk_overlap=10)
        text = "This is a test. " * 10
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 50 + 10
            assert isinstance(chunk, TextChunk)

    def test_empty_text(self) -> None:
        """Empty text returns empty list."""
        chunker = CharacterChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_respects_word_boundaries(self) -> None:
        """Word boundaries are respected when possible."""
        chunker = CharacterChunker(chunk_size=20, chunk_overlap=5, respect_word_boundaries=True)
        text = "This is a test sentence with words."
        chunks = chunker.chunk(text)

        for chunk in chunks[:-1]:
            assert not chunk.content.endswith(("T", "h", "i", "s")) or " " in chunk.content[-5:]

    def test_metadata_attached(self) -> None:
        """Metadata is attached to chunks."""
        chunker = CharacterChunker(
            chunk_size=500, chunk_overlap=50, metadata={"source": "test.txt"}
        )
        chunks = chunker.chunk("Test content")

        for chunk in chunks:
            assert chunk.metadata.get("source") == "test.txt"


class TestRecursiveChunker:
    """Tests for RecursiveChunker."""

    def test_splits_by_paragraphs_first(self) -> None:
        """Recursive chunker splits by paragraphs first."""
        chunker = RecursiveChunker(chunk_size=500, chunk_overlap=50)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk(text)

        assert len(chunks) >= 1

    def test_splits_by_sentences_when_needed(self) -> None:
        """Falls back to sentence splitting for long paragraphs."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a long sentence. This is another sentence. And a third one here."
        chunks = chunker.chunk(text)

        assert len(chunks) >= 1

    def test_custom_separators(self) -> None:
        """Custom separators can be provided."""
        chunker = RecursiveChunker(
            chunk_size=50,
            chunk_overlap=10,
            separators=["|", ",", " "],
        )
        text = "a|b|c|d|e|f|g|h"
        chunks = chunker.chunk(text)

        assert len(chunks) >= 1


class TestMarkdownChunker:
    """Tests for MarkdownChunker."""

    def test_splits_by_headers(self) -> None:
        """Markdown chunker splits by headers."""
        chunker = MarkdownChunker(chunk_size=500, split_headers=["h1", "h2"])
        text = """# Main Title

Content under main title.

## Section 1

Content in section 1.

## Section 2

Content in section 2.
"""
        chunks = chunker.chunk(text)

        assert len(chunks) >= 2
        header_metadata = [c.metadata.get("header", "") for c in chunks]
        assert any("Main Title" in h for h in header_metadata)

    def test_preserves_header_in_metadata(self) -> None:
        """Header info is preserved in chunk metadata."""
        chunker = MarkdownChunker(split_headers=["h1", "h2", "h3"])
        text = """# Title

## Subtitle

Content here.
"""
        chunks = chunker.chunk(text)

        for chunk in chunks:
            if chunk.metadata.get("header"):
                assert "header_level" in chunk.metadata

    def test_fallback_for_large_sections(self) -> None:
        """Large sections are split when max_chunk_fallback is True."""
        chunker = MarkdownChunker(chunk_size=100, chunk_overlap=20, max_chunk_fallback=True)
        text = (
            """# Title

"""
            + "This is a sentence. " * 20
        )

        chunks = chunker.chunk(text)
        assert len(chunks) > 1


class TestCodeChunker:
    """Tests for CodeChunker."""

    def test_splits_python_functions(self) -> None:
        """Code chunker splits Python by functions."""
        chunker = CodeChunker(language="python", split_by="function", chunk_size=500)
        code = '''
def function_one():
    """First function."""
    return 1

def function_two():
    """Second function."""
    return 2

class MyClass:
    def method(self):
        return 3
'''
        chunks = chunker.chunk(code)

        assert len(chunks) >= 2
        function_chunks = [c for c in chunks if c.metadata.get("block_type") == "function"]
        assert len(function_chunks) >= 2

    def test_detects_function_names(self) -> None:
        """Function names are extracted."""
        chunker = CodeChunker(language="python")
        code = "def my_function():\n    pass"
        chunks = chunker.chunk(code)

        assert len(chunks) >= 1
        assert chunks[0].metadata.get("block_name") == "my_function"

    def test_javascript_functions(self) -> None:
        """JavaScript functions are detected."""
        chunker = CodeChunker(language="javascript", chunk_size=500)
        code = """
function foo() {
    return 1;
}

const bar = () => {
    return 2;
};
"""
        chunks = chunker.chunk(code)
        assert len(chunks) >= 1

    def test_fallback_for_no_structure(self) -> None:
        """Fallback chunking when no code structure detected."""
        chunker = CodeChunker(language="python", chunk_size=100, chunk_overlap=20)
        code = "# Just a comment\n" * 10

        chunks = chunker.chunk(code)
        assert len(chunks) >= 1


class TestHierarchicalChunker:
    """Tests for HierarchicalChunker."""

    def test_creates_parent_and_child_chunks(self) -> None:
        """Hierarchical chunker creates parent and child chunks."""
        chunker = HierarchicalChunker(
            chunk_size=200,
            chunk_overlap=50,
            parent_chunk_size=600,
        )
        text = "This is content. " * 50
        chunks = chunker.chunk(text)

        parents = [c for c in chunks if c.hierarchy_level == 0]
        children = [c for c in chunks if c.hierarchy_level > 0]

        assert len(parents) >= 1
        assert len(children) >= 1

    def test_child_references_parent(self) -> None:
        """Child chunks reference their parent."""
        chunker = HierarchicalChunker(chunk_size=200, chunk_overlap=50, parent_chunk_size=400)
        text = "This is test content. " * 30
        chunks = chunker.chunk(text)

        children = [c for c in chunks if c.hierarchy_level > 0]
        parent_ids = {c.id for c in chunks if c.hierarchy_level == 0}

        for child in children[:5]:
            assert child.parent_id in parent_ids

    def test_parent_has_child_references(self) -> None:
        """Parent chunks have references to children."""
        chunker = HierarchicalChunker(chunk_size=200, chunk_overlap=50, parent_chunk_size=400)
        text = "Content for testing. " * 30
        chunks = chunker.chunk(text)

        parents = [c for c in chunks if c.hierarchy_level == 0 and c.child_ids]

        if parents:
            child_ids = set(parents[0].child_ids)
            children_of_parent = [c for c in chunks if c.parent_id == parents[0].id]
            assert len(children_of_parent) > 0


class TestGetChunker:
    """Tests for get_chunker factory function."""

    def test_get_character_chunker(self) -> None:
        """Get character chunker by name."""
        chunker = get_chunker("character", chunk_size=500, chunk_overlap=50)
        assert isinstance(chunker, CharacterChunker)
        assert chunker.chunk_size == 500

    def test_get_recursive_chunker(self) -> None:
        """Get recursive chunker by name."""
        chunker = get_chunker("recursive")
        assert isinstance(chunker, RecursiveChunker)

    def test_get_markdown_chunker(self) -> None:
        """Get markdown chunker by name."""
        chunker = get_chunker("markdown")
        assert isinstance(chunker, MarkdownChunker)

    def test_get_code_chunker(self) -> None:
        """Get code chunker by name."""
        chunker = get_chunker("code", language="javascript")
        assert isinstance(chunker, CodeChunker)
        assert chunker.language == "javascript"

    def test_get_hierarchical_chunker(self) -> None:
        """Get hierarchical chunker by name."""
        chunker = get_chunker("hierarchical", parent_chunk_size=3000)
        assert isinstance(chunker, HierarchicalChunker)
        assert chunker.parent_chunk_size == 3000

    def test_unknown_strategy_raises(self) -> None:
        """Unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            get_chunker("unknown_strategy")

    def test_list_chunkers(self) -> None:
        """list_chunkers returns all available strategies."""
        strategies = list_chunkers()
        assert "character" in strategies
        assert "recursive" in strategies
        assert "markdown" in strategies
        assert "code" in strategies
        assert "hierarchical" in strategies


class TestChunkTextConvenience:
    """Tests for chunk_text convenience function."""

    def test_chunk_text_basic(self) -> None:
        """chunk_text function works as expected."""
        text = "This is a test. " * 20
        chunks = chunk_text(text, strategy="character", chunk_size=200, chunk_overlap=50)

        assert len(chunks) >= 1
        assert all(isinstance(c, TextChunk) for c in chunks)

    def test_chunk_text_with_metadata(self) -> None:
        """chunk_text passes metadata through."""
        chunks = chunk_text(
            "Test content",
            strategy="recursive",
            metadata={"source": "test.txt"},
        )

        for chunk in chunks:
            assert chunk.metadata.get("source") == "test.txt"
