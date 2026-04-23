# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for src/orchestrator/pre_screener.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.pre_screener import (
    RankedResume,
    ResumePreScreener,
    extract_entities,
)


class TestExtractEntities:
    """Tests for extract_entities function."""

    def test_single_capitalized_word(self):
        result = extract_entities("Experience with Python and Java")
        assert "Python" in result
        assert "Java" in result

    def test_multi_word_entity(self):
        result = extract_entities("Experience with Google Cloud Platform")
        assert "Google Cloud Platform" in result

    def test_acronyms(self):
        result = extract_entities("Skills in SQL and GCP and AWS")
        assert "SQL" in result
        assert "GCP" in result
        assert "AWS" in result

    def test_stopwords_filtered(self):
        result = extract_entities("The candidate has Strong experience")
        assert "The" not in result
        assert "Strong" not in result

    def test_lowercase_ignored(self):
        result = extract_entities("experience with python")
        assert "python" not in result
        assert "experience" not in result

    def test_empty_string(self):
        assert extract_entities("") == set()

    def test_no_capitalized_words(self):
        assert extract_entities("this is all lowercase text") == set()

    def test_mixed_entities(self):
        text = "Apache Spark on Google Cloud with Python, SQL, and Airflow"
        result = extract_entities(text)
        assert "Apache Spark" in result
        assert "Google Cloud" in result
        assert "Python" in result
        assert "SQL" in result
        assert "Airflow" in result

    def test_common_resume_terms_filtered(self):
        text = "Years of Experience Working with Python"
        result = extract_entities(text)
        assert "Years" not in result
        assert "Experience" not in result
        assert "Working" not in result
        assert "Python" in result

    def test_jd_typical_content(self):
        text = (
            "We are looking for a Data Engineer with experience in "
            "Apache Spark, BigQuery, and Python. Knowledge of Docker and "
            "Kubernetes is a plus. Google Cloud Platform experience preferred."
        )
        result = extract_entities(text)
        assert "Apache Spark" in result
        assert "BigQuery" in result
        assert "Python" in result
        assert "Docker" in result
        assert "Kubernetes" in result
        assert "Google Cloud Platform" in result
        assert "We" not in result
        assert "Knowledge" not in result

    def test_technology_names_with_symbols(self):
        from src.orchestrator.pre_screener import extract_entities

        result = extract_entities("Proficient in C++, C#, .NET, and Node.js")
        assert "C++" in result
        assert "C#" in result
        assert ".NET" in result
        assert "Node.js" in result

    def test_resume_noise_words_filtered(self):
        from src.orchestrator.pre_screener import extract_entities

        text = "Senior Development Engineering Manager at Company University"
        result = extract_entities(text)
        assert "Senior" not in result
        assert "Development" not in result
        assert "Engineering" not in result
        assert "Manager" not in result
        assert "Company" not in result
        assert "University" not in result

    def test_months_filtered(self):
        from src.orchestrator.pre_screener import extract_entities

        result = extract_entities("Started January 2020, promoted March 2021")
        assert "January" not in result
        assert "March" not in result


class TestRankedResume:
    """Tests for RankedResume dataclass."""

    def test_default_values(self):
        r = RankedResume(
            reference_name="alice_chen",
            common_name="Alice Chen",
            file_path="/path/to/alice.pdf",
        )
        assert r.bm25_score == 0.0
        assert r.embedding_score == 0.0
        assert r.combined_score == 0.0
        assert r.entity_overlap == 0
        assert r.passed_bm25_filter is True
        assert r.rank == 0

    def test_with_scores(self):
        r = RankedResume(
            reference_name="alice",
            common_name="Alice",
            file_path="/alice.pdf",
            bm25_score=12.5,
            embedding_score=0.85,
            combined_score=0.72,
            entity_overlap=15,
            rank=1,
        )
        assert r.bm25_score == 12.5
        assert r.embedding_score == 0.85
        assert r.rank == 1


class TestResumePreScreenerFiltering:
    """Tests for filtering and ranking methods that don't require API calls."""

    def _make_resume(self, name: str, score: float = 0.5) -> RankedResume:
        return RankedResume(
            reference_name=name.lower().replace(" ", "_"),
            common_name=name,
            file_path=f"/path/{name}.pdf",
            combined_score=score,
            embedding_score=score * 0.8,
            bm25_score=score * 10,
        )

    def test_filter_to_top_k(self):
        resumes = [
            self._make_resume("Alice", 0.9),
            self._make_resume("Bob", 0.7),
            self._make_resume("Carol", 0.5),
            self._make_resume("Dave", 0.3),
        ]
        mock_embeddings = MagicMock()
        mock_embeddings.embed.return_value = [[0.1] * 10]
        mock_embeddings.embed_single.return_value = [0.1] * 10

        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        result = screener.filter_to_top_k(resumes, 2)
        assert len(result) == 2
        assert result[0].common_name == "Alice"
        assert result[1].common_name == "Bob"

    def test_filter_top_k_larger_than_list(self):
        resumes = [self._make_resume("Alice", 0.9)]
        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        result = screener.filter_to_top_k(resumes, 10)
        assert len(result) == 1

    def test_filter_top_k_zero(self):
        resumes = [self._make_resume("Alice", 0.9)]
        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        result = screener.filter_to_top_k(resumes, 0)
        assert len(result) == 0

    def test_build_data_rows(self):
        resumes = [
            self._make_resume("Alice Chen", 0.9),
            self._make_resume("Bob Martinez", 0.7),
        ]
        resumes[0].rank = 1
        resumes[1].rank = 2

        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        rows = screener.build_data_rows(resumes)
        assert len(rows) == 2
        assert rows[0]["id"] == 1
        assert rows[0]["batch_name"] == "alice_chen"
        assert rows[0]["candidate_name"] == "Alice Chen"
        assert rows[0]["_documents"] == '["alice_chen"]'
        assert rows[1]["id"] == 2

    def test_build_document_specs(self):
        resumes = [
            RankedResume(
                reference_name="alice_chen",
                common_name="Alice Chen",
                file_path="/path/alice.pdf",
                rank=1,
                combined_score=0.9,
            ),
        ]

        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        specs = screener.build_document_specs(resumes)
        assert len(specs) == 1
        assert specs[0]["reference_name"] == "alice_chen"
        assert specs[0]["common_name"] == "Alice Chen"
        assert specs[0]["file_path"] == "/path/alice.pdf"
        assert "resume" in specs[0]["tags"]
        assert "rank=1" in specs[0]["notes"]

    def test_build_report(self):
        resumes = [
            RankedResume(
                reference_name="alice",
                common_name="Alice",
                file_path="/alice.pdf",
                combined_score=0.9,
                embedding_score=0.85,
                bm25_score=12.0,
                entity_overlap=15,
                entity_overlap_ratio=0.75,
                passed_bm25_filter=True,
                rank=1,
            ),
            RankedResume(
                reference_name="bob",
                common_name="Bob",
                file_path="/bob.pdf",
                combined_score=0.3,
                embedding_score=0.2,
                bm25_score=2.0,
                entity_overlap=3,
                entity_overlap_ratio=0.15,
                passed_bm25_filter=False,
                rank=2,
            ),
        ]

        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        report = screener.build_report(resumes, top_k=1)
        assert report["total_candidates"] == 2
        assert report["bm25_filtered"] == 1
        assert report["top_k_selected"] == 1
        assert len(report["selected_candidates"]) == 1
        assert report["selected_candidates"][0]["reference_name"] == "alice"
        assert len(report["all_candidates"]) == 2
        assert "min_combined" in report["score_statistics"]
        assert "max_combined" in report["score_statistics"]
        assert "avg_combined" in report["score_statistics"]

    def test_build_report_empty(self):
        mock_embeddings = MagicMock()
        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_embeddings):
            with patch("src.orchestrator.pre_screener.DocumentProcessor"):
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        report = screener.build_report([], top_k=5)
        assert report["total_candidates"] == 0
        assert report["selected_candidates"] == []


class TestResumePreScreenerRanking:
    """Tests for the full ranking pipeline with mocked embeddings."""

    JD_TEXT = (
        "Senior Data Engineer\n\n"
        "We need someone with Apache Spark, BigQuery, Python, and SQL experience. "
        "Google Cloud Platform and Docker knowledge required. "
        "Kubernetes and Airflow are a plus."
    )

    @pytest.fixture
    def resume_folder(self, tmp_path: Path) -> Path:
        folder = tmp_path / "resumes"
        folder.mkdir()
        (folder / "alice_strong.txt").write_text(
            "Alice Chen\nSenior Data Engineer with 5 years experience.\n"
            "Skills: Apache Spark, BigQuery, Python, SQL, Docker.\n"
            "Google Cloud Platform certified. Kubernetes deployment experience."
        )
        (folder / "bob_medium.txt").write_text(
            "Bob Martinez\nBackend Developer.\nSkills: Python, SQL, Docker.\nSome cloud experience."
        )
        (folder / "carol_weak.txt").write_text(
            "Carol Johnson\nJunior Frontend Developer.\n"
            "Skills: HTML, CSS, JavaScript.\n"
            "Looking for opportunities."
        )
        return folder

    def _create_screener(self):
        mock_emb = MagicMock()
        dim = 8
        mock_emb.embed_single.return_value = [0.5] * dim
        mock_emb.embed.return_value = [[0.5] * dim] * 10
        mock_emb.cosine_similarity = MagicMock(side_effect=lambda a, b: 0.9)

        def _read_file(fp, rn, cn):
            return Path(fp).read_text(encoding="utf-8")

        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_emb):
            with patch("src.orchestrator.pre_screener.DocumentProcessor") as MockDP:
                mock_dp = MagicMock()
                mock_dp.get_document_content.side_effect = _read_file
                MockDP.return_value = mock_dp
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        screener._embeddings = mock_emb
        screener._doc_processor = mock_dp
        return screener

    def test_rank_resumes_returns_all(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        assert len(ranked) == 3
        assert all(isinstance(r, RankedResume) for r in ranked)

    def test_rank_resumes_assigns_ranks(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        ranks = [r.rank for r in ranked]
        assert sorted(ranks) == [1, 2, 3]

    def test_rank_resumes_populates_entity_overlap(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)

        alice = next(r for r in ranked if r.reference_name == "alice_strong")
        assert alice.entity_overlap > 0

        carol = next(r for r in ranked if r.reference_name == "carol_weak")
        assert carol.entity_overlap < alice.entity_overlap

    def test_rank_resumes_populates_combined_score(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        for r in ranked:
            assert r.combined_score >= 0.0

    def test_filter_after_ranking(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        top2 = screener.filter_to_top_k(ranked, 2)
        assert len(top2) == 2

    def test_bm25_scoring_differentiates_resumes(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)

        alice = next(r for r in ranked if r.reference_name == "alice_strong")
        carol = next(r for r in ranked if r.reference_name == "carol_weak")
        assert alice.bm25_score > carol.bm25_score

    def test_empty_folder_returns_empty(self, tmp_path):
        folder = tmp_path / "empty"
        folder.mkdir()
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, folder)
        assert ranked == []

    def test_build_data_rows_after_ranking(self, resume_folder):
        screener = self._create_screener()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        top2 = screener.filter_to_top_k(ranked, 2)
        rows = screener.build_data_rows(top2)
        assert len(rows) == 2
        assert all("batch_name" in r for r in rows)
        assert all("_documents" in r for r in rows)


class TestResumePreScreenerIntegration:
    """Integration-style tests with realistic embedding mock."""

    JD_TEXT = (
        "Senior Data Engineer\n\n"
        "Requirements: Apache Spark, BigQuery, Python, SQL. "
        "Google Cloud Platform and Docker required. "
        "Kubernetes and Airflow preferred."
    )

    @pytest.fixture
    def resume_folder(self, tmp_path: Path) -> Path:
        folder = tmp_path / "resumes"
        folder.mkdir()
        (folder / "alice.txt").write_text(
            "Alice Chen\nSenior Data Engineer\n"
            "Skills: Apache Spark, BigQuery, Python, SQL, Docker, "
            "Google Cloud Platform, Kubernetes, Airflow"
        )
        (folder / "bob.txt").write_text(
            "Bob Jones\nBackend Developer\nSkills: Python, SQL, Docker, Kubernetes"
        )
        (folder / "carol.txt").write_text(
            "Carol White\nFrontend Developer\nSkills: HTML, CSS, JavaScript, React"
        )
        return folder

    def _create_screener_with_realistic_embeddings(self):
        mock_emb = MagicMock()
        dim = 8

        def fake_embed(texts):
            if isinstance(texts, str):
                texts = [texts]
            vectors = []
            for text in texts:
                if "Spark" in text and "BigQuery" in text:
                    vectors.append([1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
                elif "Python" in text:
                    vectors.append([0.5, 0.4, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1])
                else:
                    vectors.append([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
            return vectors

        mock_emb.embed.side_effect = fake_embed
        mock_emb.embed_single.side_effect = lambda t: fake_embed([t])[0]
        mock_emb.cosine_similarity = MagicMock(
            side_effect=lambda a, b: (
                sum(x * y for x, y in zip(a, b))
                / (sum(x * x for x in a) ** 0.5 * sum(y * y for y in b) ** 0.5)
            )
        )

        def _read_file(fp, rn, cn):
            return Path(fp).read_text(encoding="utf-8")

        with patch("src.orchestrator.pre_screener.FFEmbeddings", return_value=mock_emb):
            with patch("src.orchestrator.pre_screener.DocumentProcessor") as MockDP:
                mock_dp = MagicMock()
                mock_dp.get_document_content.side_effect = _read_file
                MockDP.return_value = mock_dp
                screener = ResumePreScreener(embedding_model="mistral/mistral-embed")

        screener._embeddings = mock_emb
        screener._doc_processor = mock_dp
        return screener

    def test_alice_ranks_highest(self, resume_folder):
        screener = self._create_screener_with_realistic_embeddings()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        assert ranked[0].reference_name == "alice"

    def test_carol_ranks_lowest(self, resume_folder):
        screener = self._create_screener_with_realistic_embeddings()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        assert ranked[-1].reference_name == "carol"

    def test_entity_overlap_counts(self, resume_folder):
        screener = self._create_screener_with_realistic_embeddings()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)

        alice = next(r for r in ranked if r.reference_name == "alice")
        carol = next(r for r in ranked if r.reference_name == "carol")
        assert alice.entity_overlap >= 5
        assert carol.entity_overlap <= 2

    def test_full_pipeline_report(self, resume_folder):
        screener = self._create_screener_with_realistic_embeddings()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)
        top2 = screener.filter_to_top_k(ranked, 2)
        report = screener.build_report(ranked, 2)

        assert report["total_candidates"] == 3
        assert report["top_k_selected"] == 2
        assert len(report["selected_candidates"]) == 2
        assert report["selected_candidates"][0]["common_name"] == "alice"

    def test_combined_score_monotonic_with_relevance(self, resume_folder):
        screener = self._create_screener_with_realistic_embeddings()
        ranked = screener.rank_resumes(self.JD_TEXT, resume_folder)

        scores = [r.combined_score for r in ranked]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Rank {i + 1} score {scores[i]} < rank {i + 2} score {scores[i + 1]}"
            )


class TestPreScreeningConfig:
    """Tests for pre-screening configuration integration."""

    def test_config_loads_defaults(self):
        from src.config import get_config

        config = get_config()
        assert config.pre_screening.enabled is True
        assert config.pre_screening.top_k == 20
        assert config.pre_screening.bm25_weight == 0.3
        assert config.pre_screening.embedding_weight == 0.7
        assert config.pre_screening.embedding_model == "mistral/mistral-embed"

    def test_config_embedding_cache_size(self):
        from src.config import get_config

        config = get_config()
        assert config.pre_screening.embedding_cache_size == 512
