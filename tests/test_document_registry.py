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
        abs_path = "/absolute/path/to/file.txt"

        result = registry.resolve_path(abs_path)

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


class TestClearCache:
    def test_clear_cache_clears_content_cache(self, registry):
        registry.get_content("spec_doc")

        assert "spec_doc" in registry._content_cache

        registry.clear_cache()

        assert len(registry._content_cache) == 0
