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

    def test_chunk_whitespace_only(self) -> None:
        """Test chunk with whitespace-only text returns empty."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk("   \n\n   \t\t   ")

        assert chunks == []

    def test_chunk_with_overlap(self) -> None:
        """Test chunk creates proper overlap between chunks."""
        chunker = RecursiveChunker(chunk_size=50, chunk_overlap=20)
        text = "A" * 30 + " " + "B" * 30 + " " + "C" * 30
        chunks = chunker.chunk(text)

        assert len(chunks) > 1

    def test_chunk_large_text_splitting(self) -> None:
        """Test splitting of text that exceeds chunk_size."""
        chunker = RecursiveChunker(chunk_size=50, chunk_overlap=10)
        text = "word " * 100
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 60

    def test_split_recursive_empty_separators(self) -> None:
        """Test _split_text_recursive with empty separators list."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        result = chunker._split_text_recursive("test text", [])

        assert result == ["test text"]

    def test_split_recursive_character_mode(self) -> None:
        """Test _split_text_recursive with empty string separator."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        result = chunker._split_text_recursive("abc", [""])

        assert len(result) == 3
        assert result == ["a", "b", "c"]

    def test_split_recursive_without_keep_separator(self) -> None:
        """Test _split_text_recursive with keep_separator=False."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20, keep_separator=False)
        text = "part1, part2, part3"
        result = chunker._split_text_recursive(text, [", "])

        assert ", " not in "".join(result)

    def test_split_recursive_empty_splits(self) -> None:
        """Test _split_text_recursive when splits become empty."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        result = chunker._split_text_recursive("", ["\n\n", "\n"])

        assert result == []

    def test_split_large_text_respects_word_boundaries(self) -> None:
        """Test _split_large_text finds last space."""
        chunker = RecursiveChunker(chunk_size=20, chunk_overlap=5)
        text = "word1 word2 word3 word4 word5"
        result = chunker._split_large_text(text, 0)

        assert len(result) >= 1

    def test_get_overlap_text(self) -> None:
        """Test _get_overlap_text method."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        chunks = [("This is some text that is longer than overlap", 0, 45)]
        overlap = chunker._get_overlap_text(chunks)

        assert len(overlap) <= 20

    def test_get_overlap_text_empty_chunks(self) -> None:
        """Test _get_overlap_text with empty chunks."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        overlap = chunker._get_overlap_text([])

        assert overlap == ""

    def test_get_overlap_text_shorter_than_overlap(self) -> None:
        """Test _get_overlap_text when combined text is shorter than overlap."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=50)
        chunks = [("Short", 0, 5)]
        overlap = chunker._get_overlap_text(chunks)

        assert overlap == "Short"

    def test_finalize_chunks_empty(self) -> None:
        """Test _finalize_chunks with empty chunks."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        result: list[TextChunk] = []
        chunker._finalize_chunks([], result, {})

        assert result == []

    def test_finalize_chunks_whitespace_only(self) -> None:
        """Test _finalize_chunks with whitespace-only text."""
        chunker = RecursiveChunker(chunk_size=100, chunk_overlap=20)
        result: list[TextChunk] = []
        chunker._finalize_chunks([("   ", 0, 3)], result, {})

        assert result == []

    def test_chunk_position_tracking(self) -> None:
        """Test that chunks have correct position tracking."""
        chunker = RecursiveChunker(chunk_size=50, chunk_overlap=10)
        text = "A" * 20 + " " + "B" * 20 + " " + "C" * 20
        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.end_char <= len(text)

    def test_text_longer_than_chunk_with_no_spaces(self) -> None:
        """Test handling text without spaces longer than chunk_size."""
        chunker = RecursiveChunker(chunk_size=20, chunk_overlap=5)
        text = "a" * 100
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


class TestCodeChunkerExtended:
    """Extended tests for CodeChunker edge cases."""

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only text returns empty list."""
        chunker = CodeChunker(language="python")
        assert chunker.chunk("   \n\t  ") == []

    def test_fallback_chunking(self) -> None:
        """Fallback chunking triggers when no structural blocks found."""
        chunker = CodeChunker(language="python", chunk_size=50, chunk_overlap=10)
        code = "# comment\nx = 1\ny = 2\n"
        code = code * 10

        chunks = chunker.chunk(code)
        assert len(chunks) >= 1
        non_fallback = [c for c in chunks if c.metadata.get("block_type") != "fallback"]
        assert len(non_fallback) == 0 or all(
            c.metadata.get("block_type") in ("module_level", "fallback") for c in chunks
        )

    def test_split_by_class(self) -> None:
        """split_by='class' detects classes and functions."""
        chunker = CodeChunker(language="python", split_by="class", chunk_size=500)
        code = """
class MyClass:
    def method_one(self):
        return 1

class AnotherClass:
    def method_two(self):
        return 2

def standalone_func():
    return 3
"""
        chunks = chunker.chunk(code)
        assert len(chunks) >= 2

    def test_split_by_module(self) -> None:
        """split_by='module' detects both classes and functions."""
        chunker = CodeChunker(language="python", split_by="module", chunk_size=500)
        code = """
class MyClass:
    pass

def my_func():
    pass
"""
        chunks = chunker.chunk(code)
        assert len(chunks) >= 2

    def test_extract_name_for_class(self) -> None:
        """Class names are extracted."""
        chunker = CodeChunker(language="python", split_by="module")
        code = "class MyClassName:\n    pass"
        chunks = chunker.chunk(code)
        assert len(chunks) >= 1
        class_chunks = [c for c in chunks if c.metadata.get("block_type") == "class"]
        assert len(class_chunks) >= 1
        assert class_chunks[0].metadata.get("block_name") == "MyClassName"

    def test_get_overlap_lines_zero_overlap(self) -> None:
        """_get_overlap_lines returns empty list when overlap is 0."""
        chunker = CodeChunker(language="python", chunk_size=100, chunk_overlap=0)
        result = chunker._get_overlap_lines(["line1", "line2"])
        assert result == []

    def test_get_overlap_lines_empty_input(self) -> None:
        """_get_overlap_lines returns empty list for empty input."""
        chunker = CodeChunker(language="python", chunk_size=100, chunk_overlap=20)
        result = chunker._get_overlap_lines([])
        assert result == []

    def test_large_block_split(self) -> None:
        """Large blocks are split into sub-chunks."""
        chunker = CodeChunker(language="python", chunk_size=50, chunk_overlap=10)
        code = "def big_function():\n"
        code += "    x = 1\n" * 20

        chunks = chunker.chunk(code)
        assert len(chunks) >= 2
        assert all(c.metadata.get("block_type") == "function" for c in chunks)

    def test_language_defaults_to_python(self) -> None:
        """Default language is python."""
        chunker = CodeChunker()
        assert chunker.language == "python"

    def test_generic_language_fallback(self) -> None:
        """Unknown language falls back to generic patterns."""
        chunker = CodeChunker(language="brainfuck", chunk_size=500)
        code = "function test()\n  return 1\n"
        chunks = chunker.chunk(code)
        assert len(chunks) >= 1

    def test_metadata_includes_language(self) -> None:
        """Chunks include language in metadata."""
        chunker = CodeChunker(language="python")
        chunks = chunker.chunk("def foo():\n    pass")
        assert chunks[0].metadata.get("language") == "python"

    def test_empty_code_returns_empty(self) -> None:
        """Empty code returns empty list."""
        chunker = CodeChunker(language="python")
        assert chunker.chunk("") == []


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
