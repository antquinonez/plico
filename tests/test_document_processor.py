# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import os
from pathlib import Path

import pytest

from src.orchestrator.document_processor import DocumentProcessor


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


class TestDocumentProcessorInit:
    def test_init_creates_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()

        DocumentProcessor(cache_dir=str(cache_dir))

        assert cache_dir.exists()

    def test_init_uses_env_api_key(self, temp_cache_dir, monkeypatch):
        monkeypatch.setenv("LLAMACLOUD_TOKEN", "test-token-from-env")

        proc = DocumentProcessor(cache_dir=temp_cache_dir)

        assert proc.api_key == "test-token-from-env"

    def test_init_explicit_api_key_overrides_env(self, temp_cache_dir, monkeypatch):
        monkeypatch.setenv("LLAMACLOUD_TOKEN", "env-token")

        proc = DocumentProcessor(cache_dir=temp_cache_dir, api_key="explicit-token")

        assert proc.api_key == "explicit-token"


class TestComputeChecksum:
    def test_compute_checksum_returns_hex_string(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"

        checksum = processor.compute_checksum(str(file_path))

        assert isinstance(checksum, str)
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_compute_checksum_consistent(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"

        checksum1 = processor.compute_checksum(str(file_path))
        checksum2 = processor.compute_checksum(str(file_path))

        assert checksum1 == checksum2

    def test_compute_checksum_different_files(self, processor, fixtures_dir):
        file1 = fixtures_dir / "client_info.txt"
        file2 = fixtures_dir / "spec_doc.md"

        checksum1 = processor.compute_checksum(str(file1))
        checksum2 = processor.compute_checksum(str(file2))

        assert checksum1 != checksum2


class TestGetChecksumPrefix:
    def test_get_checksum_prefix_default_length(self, processor):
        checksum = "a1b2c3d4e5f67890" + "0" * 48

        prefix = processor.get_checksum_prefix(checksum)

        assert prefix == "a1b2c3d4"

    def test_get_checksum_prefix_custom_length(self, temp_cache_dir):
        processor = DocumentProcessor(cache_dir=temp_cache_dir, checksum_length=12)
        checksum = "a1b2c3d4e5f6" + "0" * 52

        prefix = processor.get_checksum_prefix(checksum)

        assert prefix == "a1b2c3d4e5f6"


class TestGetParquetPath:
    def test_get_parquet_path_format(self, processor, temp_cache_dir):
        checksum = "a1b2c3d4" + "0" * 56
        base_name = "My Document"

        path = processor.get_parquet_path(checksum, base_name)

        assert str(path).startswith(temp_cache_dir)
        assert "a1b2c3d4@My_Document.parquet" in str(path)

    def test_get_parquet_path_sanitizes_name(self, processor):
        checksum = "a1b2c3d4" + "0" * 56
        base_name = "My Document (v2).pdf"

        path = processor.get_parquet_path(checksum, base_name)

        assert "My_Document__v2_.parquet" in str(path)


class TestNeedsParsing:
    def test_needs_parsing_true_when_no_cache(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"

        result = processor.needs_parsing(str(file_path), "client_info")

        assert result is True

    def test_needs_parsing_false_when_cached(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"
        checksum = processor.compute_checksum(str(file_path))
        content = "test content"
        processor.store_document(str(file_path), "client_info", "Client Info", content)

        result = processor.needs_parsing(str(file_path), "client_info")

        assert result is False

    def test_needs_parsing_raises_for_missing_file(self, processor, tmp_path):
        missing_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            processor.needs_parsing(str(missing_file), "missing")


class TestParseDocument:
    def test_parse_text_file_directly(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"

        content = processor.parse_document(str(file_path))

        assert "Client Information Report" in content
        assert "CLI-001" in content

    def test_parse_markdown_file(self, processor, fixtures_dir):
        file_path = fixtures_dir / "spec_doc.md"

        content = processor.parse_document(str(file_path))

        assert "# Technical Specification" in content
        assert "## Overview" in content

    def test_parse_json_file(self, processor, fixtures_dir):
        file_path = fixtures_dir / "config.json"

        content = processor.parse_document(str(file_path))

        assert "TestProduct" in content
        assert '"version"' in content

    @pytest.mark.llamaparse
    def test_parse_pdf_requires_api_key(self, temp_cache_dir, fixtures_dir):
        processor = DocumentProcessor(cache_dir=temp_cache_dir, api_key=None)

        pdf_path = fixtures_dir / "sample.pdf"
        if not pdf_path.exists():
            pytest.skip("No sample PDF available")

        with pytest.raises(ValueError, match="LlamaParse API key required"):
            processor.parse_document(str(pdf_path))


class TestStoreDocument:
    def test_store_document_creates_parquet(self, processor, fixtures_dir, temp_cache_dir):
        file_path = fixtures_dir / "client_info.txt"
        content = processor.parse_document(str(file_path))

        parquet_path = processor.store_document(str(file_path), "test_ref", "Test Doc", content)

        assert os.path.exists(parquet_path)
        assert parquet_path.endswith(".parquet")

    def test_store_document_parquet_has_correct_schema(self, processor, fixtures_dir):
        import polars as pl

        file_path = fixtures_dir / "client_info.txt"
        content = "test content"
        parquet_path = processor.store_document(str(file_path), "test_ref", "Test Doc", content)

        df = pl.read_parquet(parquet_path)

        assert "reference_name" in df.columns
        assert "common_name" in df.columns
        assert "original_path" in df.columns
        assert "checksum" in df.columns
        assert "content" in df.columns
        assert "parsed_at" in df.columns
        assert "file_size" in df.columns


class TestLoadDocument:
    def test_load_document_returns_dict(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"
        content = "test content for loading"
        parquet_path = processor.store_document(str(file_path), "load_test", "Load Test", content)

        doc_data = processor.load_document(parquet_path)

        assert isinstance(doc_data, dict)
        assert doc_data["reference_name"] == "load_test"
        assert doc_data["common_name"] == "Load Test"
        assert doc_data["content"] == content


class TestGetDocumentContent:
    def test_get_document_content_parses_first_time(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"

        content = processor.get_document_content(str(file_path), "client_info", "Client Info")

        assert "Client Information Report" in content

    def test_get_document_content_uses_cache(self, processor, fixtures_dir, tmp_path):
        file_path = fixtures_dir / "client_info.txt"
        content1 = processor.get_document_content(str(file_path), "cached_doc", "Cached Doc")

        content2 = processor.get_document_content(str(file_path), "cached_doc", "Cached Doc")

        assert content1 == content2


class TestClearCache:
    def test_clear_cache_removes_files(self, processor, fixtures_dir):
        file_path = fixtures_dir / "client_info.txt"
        processor.store_document(str(file_path), "doc1", "Doc 1", "content1")
        processor.store_document(str(file_path), "doc2", "Doc 2", "content2")

        count = processor.clear_cache()

        assert count == 2
        cache_files = list(Path(processor.cache_dir).glob("*.parquet"))
        assert len(cache_files) == 0


class TestTextExtensions:
    def test_text_extensions_includes_common_types(self):
        from src.config import get_config

        config = get_config()
        text_extensions = config.document_processor.text_extensions
        assert ".txt" in text_extensions
        assert ".md" in text_extensions
        assert ".py" in text_extensions
        assert ".json" in text_extensions
        assert ".csv" in text_extensions
        assert ".xml" in text_extensions
        assert ".yaml" in text_extensions
        assert ".html" in text_extensions
