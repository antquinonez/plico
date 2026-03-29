# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.orchestrator.document_processor import DocumentProcessor
from src.orchestrator.document_registry import DocumentRegistry


@pytest.fixture
def temp_cache_dir(tmp_path):
    cache_dir = tmp_path / "doc_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures" / "documents"


@pytest.fixture
def processor(temp_cache_dir):
    return DocumentProcessor(cache_dir=temp_cache_dir)


@pytest.fixture
def sample_documents(fixtures_dir):
    return [
        {
            "reference_name": "spec_doc",
            "common_name": "Technical Specification",
            "file_path": str(fixtures_dir / "spec_doc.md"),
            "notes": "Main spec document",
        },
        {
            "reference_name": "client_info",
            "common_name": "Client Information",
            "file_path": str(fixtures_dir / "client_info.txt"),
            "notes": "Client details",
        },
        {
            "reference_name": "config",
            "common_name": "Configuration",
            "file_path": str(fixtures_dir / "config.json"),
            "notes": "App configuration",
        },
    ]


@pytest.fixture
def registry(sample_documents, processor, fixtures_dir):
    return DocumentRegistry(
        documents=sample_documents,
        processor=processor,
        workbook_dir=str(fixtures_dir),
    )


class TestDocumentRegistryInit:
    def test_init_loads_documents(self, sample_documents, processor, fixtures_dir):
        registry = DocumentRegistry(
            documents=sample_documents,
            processor=processor,
            workbook_dir=str(fixtures_dir),
        )

        assert len(registry.documents) == 3
        assert "spec_doc" in registry.documents
        assert "client_info" in registry.documents
        assert "config" in registry.documents

    def test_init_skips_empty_reference_names(self, sample_documents, processor, fixtures_dir):
        sample_documents.append({"reference_name": None, "common_name": "Empty"})

        registry = DocumentRegistry(
            documents=sample_documents,
            processor=processor,
            workbook_dir=str(fixtures_dir),
        )

        assert len(registry.documents) == 3


class TestResolvePath:
    def test_resolve_path_absolute(self, registry):
        import platform

        if platform.system() == "Windows":
            abs_path = "C:\\absolute\\path\\to\\file.txt"
        else:
            abs_path = "/absolute/path/to/file.txt"

        result = registry.resolve_path(abs_path)

        assert os.path.isabs(result)
        assert result == abs_path

    def test_resolve_path_relative(self, registry, fixtures_dir):
        rel_path = "spec_doc.md"

        result = registry.resolve_path(rel_path)

        assert os.path.isabs(result)
        assert result.endswith("spec_doc.md")

    def test_resolve_path_with_subfolder(self, registry, fixtures_dir):
        rel_path = "subfolder/file.txt"

        result = registry.resolve_path(rel_path)

        workbook_dir = str(fixtures_dir)
        assert result.startswith(workbook_dir)


class TestValidateDocuments:
    def test_validate_documents_returns_valid_names(self, registry):
        result = registry.validate_documents()

        assert set(result) == {"spec_doc", "client_info", "config"}

    def test_validate_documents_raises_for_missing(self, sample_documents, processor, fixtures_dir):
        sample_documents.append(
            {
                "reference_name": "missing_doc",
                "common_name": "Missing",
                "file_path": "nonexistent_file.txt",
            }
        )

        registry = DocumentRegistry(
            documents=sample_documents,
            processor=processor,
            workbook_dir=str(fixtures_dir),
        )

        with pytest.raises(FileNotFoundError, match="Document.*not found"):
            registry.validate_documents()


class TestGetReferenceNames:
    def test_get_reference_names(self, registry):
        names = registry.get_reference_names()

        assert names == {"spec_doc", "client_info", "config"}


class TestGetDocumentConfig:
    def test_get_document_config_found(self, registry):
        config = registry.get_document_config("spec_doc")

        assert config is not None
        assert config["reference_name"] == "spec_doc"
        assert config["common_name"] == "Technical Specification"

    def test_get_document_config_not_found(self, registry):
        config = registry.get_document_config("nonexistent")

        assert config is None


class TestGetContent:
    def test_get_content_returns_document_content(self, registry):
        content = registry.get_content("spec_doc")

        assert "# Technical Specification" in content
        assert "## Overview" in content

    def test_get_content_raises_for_unknown_reference(self, registry):
        with pytest.raises(KeyError, match="Document reference not found"):
            registry.get_content("unknown_ref")

    def test_get_content_caches_in_memory(self, registry, processor):
        with patch.object(processor, "get_document_content") as mock_get:
            mock_get.return_value = "cached content"

            registry.get_content("spec_doc")
            registry.get_content("spec_doc")

            mock_get.assert_called_once()


class TestGetAllContent:
    def test_get_all_content_returns_dict(self, registry):
        result = registry.get_all_content(["spec_doc", "client_info"])

        assert isinstance(result, dict)
        assert "spec_doc" in result
        assert "client_info" in result
        assert "# Technical Specification" in result["spec_doc"]
        assert "Client Information Report" in result["client_info"]

    def test_get_all_content_raises_for_missing_ref(self, registry):
        with pytest.raises(KeyError):
            registry.get_all_content(["spec_doc", "nonexistent"])


class TestFormatReferencesBlock:
    def test_format_references_block_single_doc(self, registry):
        result = registry.format_references_block(["spec_doc"])

        assert result.startswith("<REFERENCES>")
        assert result.endswith("</REFERENCES>")
        assert "<DOC name='spec_doc'>" in result
        assert "# Technical Specification" in result
        assert "</DOC>" in result

    def test_format_references_block_multiple_docs(self, registry):
        result = registry.format_references_block(["spec_doc", "client_info"])

        assert result.startswith("<REFERENCES>")
        assert result.endswith("</REFERENCES>")
        assert "<DOC name='spec_doc'>" in result
        assert "<DOC name='client_info'>" in result

    def test_format_references_block_empty_list(self, registry):
        result = registry.format_references_block([])

        assert result == ""

    def test_format_references_block_preserves_order(self, registry):
        result = registry.format_references_block(["client_info", "spec_doc"])

        spec_pos = result.find("<DOC name='spec_doc'>")
        client_pos = result.find("<DOC name='client_info'>")

        assert client_pos < spec_pos


class TestInjectReferencesIntoPrompt:
    def test_inject_references_into_prompt(self, registry):
        prompt = "What is the main feature?"
        refs = ["spec_doc"]

        result = registry.inject_references_into_prompt(prompt, refs)

        assert result.startswith("<REFERENCES>")
        assert "<DOC name='spec_doc'>" in result
        assert "===" in result
        assert "Based on the documents above" in result
        assert prompt in result

    def test_inject_references_into_prompt_no_refs(self, registry):
        prompt = "Simple question"

        result = registry.inject_references_into_prompt(prompt, None)

        assert result == prompt

    def test_inject_references_into_prompt_empty_refs(self, registry):
        prompt = "Simple question"

        result = registry.inject_references_into_prompt(prompt, [])

        assert result == prompt


class TestFormatReferencesBlockEdgeCases:
    def test_format_references_block_all_refs_missing(self, registry):
        """Test format_references_block returns empty string when get_all_content returns empty."""
        from unittest.mock import patch

        with patch.object(registry, "get_all_content", return_value={}):
            result = registry.format_references_block(["nonexistent1", "nonexistent2"])

        assert result == ""

    def test_format_references_block_mixed_valid_invalid(self, registry):
        """Test format_references_block includes only references present in the result dict."""
        from unittest.mock import patch

        partial_content = {"spec_doc": "content A", "client_info": "content B"}
        with patch.object(registry, "get_all_content", return_value=partial_content):
            result = registry.format_references_block(["spec_doc", "missing_ref", "client_info"])

        assert "<DOC name='spec_doc'>" in result
        assert "<DOC name='client_info'>" in result
        assert "missing_ref" not in result


class TestInjectReferencesIntoPromptEdgeCases:
    def test_inject_references_returns_prompt_when_refs_block_empty(self, registry):
        """Test inject_references returns original prompt when refs_block is empty."""
        from unittest.mock import patch

        prompt = "Simple question"
        with patch.object(registry, "format_references_block", return_value=""):
            result = registry.inject_references_into_prompt(prompt, ["nonexistent"])

        assert result == prompt


class TestSemanticSearch:
    def test_semantic_search_raises_without_rag_client(self, registry):
        """Test semantic_search raises RuntimeError when no RAG client configured."""
        with pytest.raises(RuntimeError, match="RAG client not configured"):
            registry.semantic_search("test query")

    def test_semantic_search_with_rag_client(self, processor, fixtures_dir, tmp_path):
        """Test semantic_search delegates to RAG client."""
        from unittest.mock import MagicMock

        mock_rag = MagicMock()
        mock_rag.search.return_value = [
            {"content": "result text", "metadata": {"reference_name": "doc1"}, "score": 0.95}
        ]

        registry = DocumentRegistry(
            documents=[],
            processor=processor,
            workbook_dir=str(fixtures_dir),
            rag_client=mock_rag,
        )

        results = registry.semantic_search("query", n_results=3)

        mock_rag.search.assert_called_once_with(
            "query", n_results=3, where=None, query_expansion=None, rerank=None
        )
        assert len(results) == 1
        assert results[0]["content"] == "result text"

    def test_semantic_search_with_filter_and_options(self, processor, fixtures_dir):
        """Test semantic_search passes filter, query_expansion, and rerank."""
        from unittest.mock import MagicMock

        mock_rag = MagicMock()
        mock_rag.search.return_value = []

        registry = DocumentRegistry(
            documents=[],
            processor=processor,
            workbook_dir=str(fixtures_dir),
            rag_client=mock_rag,
        )

        registry.semantic_search(
            "query",
            n_results=5,
            where={"reference_name": "doc1"},
            query_expansion=True,
            rerank=True,
        )

        mock_rag.search.assert_called_once_with(
            "query",
            n_results=5,
            where={"reference_name": "doc1"},
            query_expansion=True,
            rerank=True,
        )


class TestFormatSemanticResults:
    def test_format_semantic_results_empty(self, registry):
        """Test format_semantic_results returns empty string for empty results."""
        result = registry.format_semantic_results([])

        assert result == ""

    def test_format_semantic_results_formats_content(self, registry):
        """Test format_semantic_results formats results with source and score."""
        results = [
            {"content": "chunk one", "metadata": {"reference_name": "doc1"}, "score": 0.95},
            {"content": "chunk two", "metadata": {"reference_name": "doc2"}, "score": 0.85},
        ]

        result = registry.format_semantic_results(results)

        assert "[1] (source: doc1, relevance: 0.95)" in result
        assert "chunk one" in result
        assert "[2] (source: doc2, relevance: 0.85)" in result
        assert "chunk two" in result

    def test_format_semantic_results_truncates_by_max_chars(self, registry):
        """Test format_semantic_results stops when max_chars exceeded."""
        results = [
            {"content": "A" * 100, "metadata": {"reference_name": "doc1"}, "score": 0.95},
            {"content": "B" * 100, "metadata": {"reference_name": "doc2"}, "score": 0.85},
        ]

        result = registry.format_semantic_results(results, max_chars=50)

        assert "A" * 100 not in result
        assert len(result) <= 50

    def test_format_semantic_results_unknown_source(self, registry):
        """Test format_semantic_results uses 'unknown' when metadata missing."""
        results = [
            {"content": "text", "metadata": {}, "score": 0.5},
        ]

        result = registry.format_semantic_results(results)

        assert "(source: unknown, relevance: 0.50)" in result


class TestInjectSemanticQuery:
    def test_inject_semantic_query_empty_query(self, registry):
        """Test inject_semantic_query returns original prompt when query is empty."""
        prompt = "What is this?"

        result = registry.inject_semantic_query(prompt, semantic_query="")

        assert result == prompt

    def test_inject_semantic_query_no_results(self, processor, fixtures_dir):
        """Test inject_semantic_query returns original prompt when no results found."""
        from unittest.mock import MagicMock

        mock_rag = MagicMock()
        mock_rag.search.return_value = []

        registry = DocumentRegistry(
            documents=[],
            processor=processor,
            workbook_dir=str(fixtures_dir),
            rag_client=mock_rag,
        )

        prompt = "What is this?"
        result = registry.inject_semantic_query(prompt, semantic_query="search query")

        assert result == prompt

    def test_inject_semantic_query_with_results(self, processor, fixtures_dir):
        """Test inject_semantic_query injects context when results found."""
        from unittest.mock import MagicMock

        mock_rag = MagicMock()
        mock_rag.search.return_value = [
            {"content": "relevant text", "metadata": {"reference_name": "doc1"}, "score": 0.95}
        ]

        registry = DocumentRegistry(
            documents=[],
            processor=processor,
            workbook_dir=str(fixtures_dir),
            rag_client=mock_rag,
        )

        prompt = "Summarize"
        result = registry.inject_semantic_query(
            prompt, semantic_query="search", semantic_filter={"tag": "info"}
        )

        assert "<RELEVANT_CONTEXT>" in result
        assert "relevant text" in result
        assert "</RELEVANT_CONTEXT>" in result
        assert "Based on the context above" in result
        assert prompt in result


class TestIndexAllDocuments:
    def test_index_all_documents_no_rag_client(self, registry):
        """Test index_all_documents returns empty dict when no RAG client."""
        result = registry.index_all_documents()

        assert result == {}

    def test_index_all_documents_with_rag_client(self, processor, fixtures_dir, tmp_path):
        """Test index_all_documents indexes all registered documents."""
        from unittest.mock import MagicMock, patch

        mock_rag = MagicMock()

        doc_file = tmp_path / "index_test.txt"
        doc_file.write_text("Content to index")

        registry = DocumentRegistry(
            documents=[
                {
                    "reference_name": "test_doc",
                    "common_name": "Test",
                    "file_path": str(doc_file),
                    "tags": ["test"],
                    "chunking_strategy": "character",
                }
            ],
            processor=processor,
            workbook_dir=str(tmp_path),
            rag_client=mock_rag,
        )

        with (
            patch.object(processor, "get_document_checksum", return_value="abc123"),
            patch.object(processor, "index_to_rag", return_value=5),
        ):
            result = registry.index_all_documents()

        assert result == {"test_doc": 5}

    def test_index_all_documents_missing_file(self, processor, fixtures_dir):
        """Test index_all_documents skips missing files."""
        from unittest.mock import MagicMock

        mock_rag = MagicMock()

        registry = DocumentRegistry(
            documents=[
                {
                    "reference_name": "missing",
                    "common_name": "Missing",
                    "file_path": "/nonexistent/file.txt",
                }
            ],
            processor=processor,
            workbook_dir=str(fixtures_dir),
            rag_client=mock_rag,
        )

        result = registry.index_all_documents()

        assert result == {}

    def test_index_all_documents_indexing_error(self, processor, fixtures_dir, tmp_path):
        """Test index_all_documents handles indexing errors gracefully."""
        from unittest.mock import MagicMock, patch

        mock_rag = MagicMock()

        doc_file = tmp_path / "error_doc.txt"
        doc_file.write_text("Content")

        registry = DocumentRegistry(
            documents=[
                {
                    "reference_name": "error_doc",
                    "common_name": "Error Doc",
                    "file_path": str(doc_file),
                }
            ],
            processor=processor,
            workbook_dir=str(tmp_path),
            rag_client=mock_rag,
        )

        with (
            patch.object(processor, "get_document_checksum", return_value="abc"),
            patch.object(processor, "index_to_rag", side_effect=RuntimeError("index failed")),
        ):
            result = registry.index_all_documents()

        assert result == {"error_doc": 0}


class TestClearCache:
    def test_clear_cache_clears_content_cache(self, registry):
        registry.get_content("spec_doc")

        assert "spec_doc" in registry._content_cache

        registry.clear_cache()

        assert len(registry._content_cache) == 0
