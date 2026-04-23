# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Embedding-based resume pre-screener for cost reduction.

Ranks resumes against a job description using a two-tier pipeline:
  Tier 1 — BM25 keyword filtering on extracted named entities
  Tier 2 — Dense embedding cosine similarity ranking

Returns a ranked list of candidates so that only the top-K need to be
sent through the full LLM evaluation pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_config
from ..RAG.FFEmbeddings import FFEmbeddings
from .discovery import DocumentSpec, discover_documents
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

_ENTITY_RE = re.compile(
    r"(?:"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"  # multi-word: "Google Cloud Platform"
    r"|[A-Z][a-z]+[A-Z][A-Za-z]*"  # camelCase: "BigQuery", "JavaScript"
    r"|[A-Z]{2,}"  # acronyms: "GCP", "SQL"
    r"|[A-Z]\+\+"  # C++, F++
    r"|[A-Z]#"  # C#, F#
    r"|\.NET"  # .NET
    r"|[A-Z][a-z]+\.js"  # Node.js, Vue.js, React.js
    r"|[A-Z][a-z]+"  # single capitalized: "Python"
    r")(?=\b|[^a-zA-Z0-9]|$)"
)

_STOPWORDS = frozenset(
    {
        "The",
        "And",
        "With",
        "For",
        "From",
        "This",
        "That",
        "Not",
        "Are",
        "Was",
        "Has",
        "Had",
        "Been",
        "Being",
        "Will",
        "Would",
        "Could",
        "Should",
        "May",
        "Might",
        "Must",
        "Shall",
        "Can",
        "Does",
        "Did",
        "But",
        "Our",
        "Your",
        "Their",
        "His",
        "Her",
        "Its",
        "Who",
        "What",
        "When",
        "Where",
        "How",
        "Why",
        "All",
        "Each",
        "Every",
        "Both",
        "Few",
        "More",
        "Most",
        "Other",
        "Some",
        "Such",
        "Than",
        "Too",
        "Very",
        "Just",
        "Also",
        "About",
        "After",
        "Before",
        "Between",
        "Into",
        "Through",
        "During",
        "Here",
        "There",
        "Which",
        "While",
        "Then",
        "Once",
        "We",
        "They",
        "Knowledge",
        "Years",
        "Year",
        "Experience",
        "Work",
        "Working",
        "Including",
        "Include",
        "Based",
        "Using",
        "Use",
        "Strong",
        "Excellent",
        "Good",
        "Ability",
        "Looking",
        "Required",
        "Preferred",
        "Senior",
        "Junior",
        "Lead",
        "Manager",
        "Director",
        "Coordinator",
        "Specialist",
        "Analyst",
        "Consultant",
        "Associate",
        "Assistant",
        "Executive",
        "Intern",
        "Team",
        "Group",
        "Department",
        "Division",
        "Company",
        "Organization",
        "Corporation",
        "University",
        "College",
        "Institute",
        "Development",
        "Engineering",
        "Management",
        "Operations",
        "Research",
        "Design",
        "Analysis",
        "Strategy",
        "Planning",
        "Implementation",
        "Maintenance",
        "Support",
        "Service",
        "Services",
        "Solutions",
        "Systems",
        "Platform",
        "Platforms",
        "Technology",
        "Technologies",
        "Product",
        "Products",
        "Project",
        "Projects",
        "Program",
        "Programs",
        "January",
        "February",
        "March",
        "April",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    }
)


@dataclass
class RankedResume:
    """A resume with its pre-screening scores and metadata."""

    reference_name: str
    common_name: str
    file_path: str
    bm25_score: float = 0.0
    embedding_score: float = 0.0
    combined_score: float = 0.0
    entity_overlap: int = 0
    entity_overlap_ratio: float = 0.0
    passed_bm25_filter: bool = True
    rank: int = 0


def extract_entities(text: str) -> set[str]:
    """Extract capitalized named entities from text.

    Identifies multi-word capitalized sequences (e.g., "Google Cloud Platform"),
    acronyms (e.g., "GCP", "SQL"), and single capitalized terms (e.g., "Python").
    Common English stopwords and generic resume terms are filtered out.

    Args:
        text: Input text to extract entities from.

    Returns:
        Set of extracted entity strings.

    """
    raw = set(_ENTITY_RE.findall(text))
    return raw - _STOPWORDS


class ResumePreScreener:
    """Two-tier resume ranking pipeline.

    Tier 1 uses BM25 scoring on named entities extracted from the JD to
    quickly filter out resumes with negligible keyword overlap. Tier 2
    computes dense embedding similarity between the JD and each surviving
    resume for precise semantic ranking.

    Args:
        embedding_model: LiteLLM model string (e.g., ``"mistral/mistral-embed"``).
        cache_dir: Directory for parsed document cache.
        bm25_min_score: Minimum BM25 score to pass tier 1 filter.
        bm25_min_overlap_ratio: Minimum fraction of JD entities that must appear.
        bm25_weight: Weight for BM25 score in combined ranking (0-1).
        embedding_weight: Weight for embedding score in combined ranking (0-1).
        embedding_cache_size: LRU cache size for embedding model.

    """

    def __init__(
        self,
        embedding_model: str = "mistral/mistral-embed",
        cache_dir: str | None = None,
        bm25_min_score: float = 0.0,
        bm25_min_overlap_ratio: float = 0.0,
        bm25_weight: float = 0.3,
        embedding_weight: float = 0.7,
        embedding_cache_size: int = 512,
    ) -> None:
        config = get_config()
        self._cache_dir = cache_dir or config.paths.ffai_data
        self._bm25_min_score = bm25_min_score
        self._bm25_min_overlap_ratio = bm25_min_overlap_ratio
        self._bm25_weight = bm25_weight
        self._embedding_weight = embedding_weight

        self._embeddings = FFEmbeddings(
            model=embedding_model,
            cache_enabled=True,
            cache_size=embedding_cache_size,
        )
        self._doc_processor = DocumentProcessor(
            cache_dir=self._cache_dir,
        )

        logger.info(
            f"ResumePreScreener initialized: model={embedding_model}, "
            f"bm25_weight={bm25_weight}, embedding_weight={embedding_weight}"
        )

    def rank_resumes(
        self,
        jd_text: str,
        resumes_folder: str | Path,
        extensions: set[str] | None = None,
    ) -> list[RankedResume]:
        """Rank resumes against a job description.

        Executes the two-tier pipeline:
        1. Parse all resumes and extract entities
        2. Tier 1: BM25 filter on entity overlap
        3. Tier 2: Embedding similarity ranking
        4. Combine scores and return ranked list

        Args:
            jd_text: Full text of the job description.
            resumes_folder: Path to folder containing resume files.
            extensions: File extensions to include (defaults to standard set).

        Returns:
            List of RankedResume objects sorted by combined_score descending.

        """
        doc_specs = discover_documents(
            resumes_folder,
            extensions=extensions,
            absolute_paths=True,
            tags=["resume"],
        )
        if not doc_specs:
            logger.warning(f"No documents found in {resumes_folder}")
            return []

        logger.info(f"Pre-screening {len(doc_specs)} resumes against JD")

        jd_entities = extract_entities(jd_text)
        logger.info(f"Extracted {len(jd_entities)} entities from JD: {sorted(jd_entities)[:20]}")

        parsed = self._parse_all(doc_specs)
        if not parsed:
            logger.warning("No resumes could be parsed")
            return []

        ranked = self._score_bm25(jd_text, jd_entities, parsed)
        ranked = self._score_embeddings(jd_text, ranked)
        ranked = self._combine_scores(ranked)
        ranked.sort(key=lambda r: r.combined_score, reverse=True)

        for i, r in enumerate(ranked, start=1):
            r.rank = i

        logger.info(
            f"Pre-screening complete: {len(ranked)} ranked, "
            f"{sum(1 for r in ranked if r.passed_bm25_filter)} passed BM25 filter"
        )
        return ranked

    def filter_to_top_k(
        self,
        ranked: list[RankedResume],
        top_k: int,
    ) -> list[RankedResume]:
        """Return only the top-K ranked resumes.

        Args:
            ranked: Full ranked list from ``rank_resumes()``.
            top_k: Number of top candidates to return.

        Returns:
            Top-K RankedResume objects.

        """
        return ranked[:top_k]

    def build_data_rows(
        self,
        ranked: list[RankedResume],
    ) -> list[dict[str, Any]]:
        """Build data rows suitable for manifest data.yaml from ranked resumes.

        Args:
            ranked: Ranked resume list (typically already filtered to top-K).

        Returns:
            List of dicts with id, batch_name, candidate_name, _documents.

        """
        rows: list[dict[str, Any]] = []
        for idx, resume in enumerate(ranked, start=1):
            rows.append(
                {
                    "id": idx,
                    "batch_name": resume.reference_name,
                    "candidate_name": resume.common_name,
                    "_documents": f'["{resume.reference_name}"]',
                }
            )
        return rows

    def build_document_specs(
        self,
        ranked: list[RankedResume],
    ) -> list[DocumentSpec]:
        """Build document specs for manifest documents.yaml from ranked resumes.

        Args:
            ranked: Ranked resume list (typically already filtered to top-K).

        Returns:
            List of DocumentSpec dicts for manifest documents.yaml.

        """
        specs: list[DocumentSpec] = []
        for resume in ranked:
            specs.append(
                {
                    "reference_name": resume.reference_name,
                    "common_name": resume.common_name,
                    "file_path": resume.file_path,
                    "tags": "resume",
                    "chunking_strategy": "",
                    "notes": (f"pre-screen rank={resume.rank}, score={resume.combined_score:.4f}"),
                }
            )
        return specs

    def build_report(
        self,
        ranked: list[RankedResume],
        top_k: int,
    ) -> dict[str, Any]:
        """Build a pre-screening report dictionary.

        Args:
            ranked: Full ranked list.
            top_k: Number of candidates that will proceed.

        Returns:
            Dict with summary statistics and per-resume details.

        """
        selected = self.filter_to_top_k(ranked, top_k)
        return {
            "total_candidates": len(ranked),
            "bm25_filtered": sum(1 for r in ranked if not r.passed_bm25_filter),
            "top_k_selected": len(selected),
            "score_statistics": {
                "min_combined": min((r.combined_score for r in ranked), default=0.0),
                "max_combined": max((r.combined_score for r in ranked), default=0.0),
                "avg_combined": (
                    sum(r.combined_score for r in ranked) / len(ranked) if ranked else 0.0
                ),
            },
            "selected_candidates": [
                {
                    "rank": r.rank,
                    "reference_name": r.reference_name,
                    "common_name": r.common_name,
                    "combined_score": round(r.combined_score, 4),
                    "embedding_score": round(r.embedding_score, 4),
                    "bm25_score": round(r.bm25_score, 4),
                    "entity_overlap": r.entity_overlap,
                }
                for r in selected
            ],
            "all_candidates": [
                {
                    "rank": r.rank,
                    "reference_name": r.reference_name,
                    "common_name": r.common_name,
                    "combined_score": round(r.combined_score, 4),
                    "passed_bm25": r.passed_bm25_filter,
                }
                for r in ranked
            ],
        }

    def _parse_all(
        self,
        doc_specs: list[DocumentSpec],
    ) -> list[tuple[DocumentSpec, str]]:
        """Parse all documents and return (spec, text) pairs.

        Args:
            doc_specs: Document specifications from discovery.

        Returns:
            List of (DocumentSpec, text_content) tuples.

        """
        parsed: list[tuple[DocumentSpec, str]] = []
        for spec in doc_specs:
            file_path = spec["file_path"]
            ref_name = spec["reference_name"]
            common_name = spec["common_name"]
            try:
                content = self._doc_processor.get_document_content(file_path, ref_name, common_name)
                if content.strip():
                    parsed.append((spec, content))
                else:
                    logger.warning(f"Empty content for {ref_name}, skipping")
            except Exception as e:
                logger.warning(f"Failed to parse {ref_name}: {e}")
        return parsed

    def _score_bm25(
        self,
        jd_text: str,
        jd_entities: set[str],
        parsed: list[tuple[DocumentSpec, str]],
    ) -> list[RankedResume]:
        """Apply Tier 1 BM25 scoring on entity overlap.

        Args:
            jd_text: Job description text (used as BM25 query).
            jd_entities: Entities extracted from the JD.
            parsed: (spec, text) pairs for each resume.

        Returns:
            List of RankedResume with BM25 scores populated.

        """
        from ..RAG.indexing.bm25_index import BM25Index

        results: list[RankedResume] = []

        bm25 = BM25Index()
        for spec, text in parsed:
            bm25.add_document(spec["reference_name"], text)

        bm25_results = {r["id"]: r["score"] for r in bm25.search(jd_text, n_results=len(parsed))}

        for spec, text in parsed:
            ref_name = spec["reference_name"]
            resume_entities = extract_entities(text)
            overlap = jd_entities & resume_entities
            overlap_ratio = len(overlap) / len(jd_entities) if jd_entities else 0.0

            bm25_score = bm25_results.get(ref_name, 0.0)

            passed = True
            if bm25_score < self._bm25_min_score:
                passed = False
            if overlap_ratio < self._bm25_min_overlap_ratio:
                passed = False

            results.append(
                RankedResume(
                    reference_name=ref_name,
                    common_name=spec["common_name"],
                    file_path=spec["file_path"],
                    bm25_score=bm25_score,
                    entity_overlap=len(overlap),
                    entity_overlap_ratio=overlap_ratio,
                    passed_bm25_filter=passed,
                )
            )

        return results

    def _score_embeddings(
        self,
        jd_text: str,
        resumes: list[RankedResume],
    ) -> list[RankedResume]:
        """Apply Tier 2 embedding similarity scoring.

        Only resumes that passed the BM25 filter are embedded. Those that
        failed get an embedding_score of 0.0.

        Args:
            jd_text: Job description text.
            resumes: RankedResume list with BM25 scores populated.

        Returns:
            Same list with embedding_score populated.

        """
        passing = [r for r in resumes if r.passed_bm25_filter]

        if not passing:
            logger.warning("No resumes passed BM25 filter, embedding all as fallback")
            passing = resumes

        jd_embedding = self._embeddings.embed_single(jd_text)

        batch_texts = []
        for r in passing:
            try:
                content = self._doc_processor.get_document_content(
                    r.file_path, r.reference_name, r.common_name
                )
                batch_texts.append(content)
            except Exception as e:
                logger.warning(f"Failed to read {r.reference_name} for embedding: {e}")
                batch_texts.append("")

        if batch_texts:
            resume_embeddings = self._embed_batch(batch_texts)
            for r, emb in zip(passing, resume_embeddings):
                r.embedding_score = FFEmbeddings.cosine_similarity(jd_embedding, emb)

        return resumes

    def _embed_batch(
        self,
        texts: list[str],
        batch_size: int = 20,
        max_chars: int = 8000,
    ) -> list[list[float]]:
        """Embed texts in API-safe batches.

        Splits texts into batches to avoid API token limits, and truncates
        individual texts to stay within per-item limits.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts per API call.
            max_chars: Maximum characters per text (truncated if longer).

        Returns:
            List of embedding vectors in the same order as input.

        """
        truncated = [t[:max_chars] if len(t) > max_chars else t for t in texts]

        all_embeddings: list[list[float]] = []
        for i in range(0, len(truncated), batch_size):
            chunk = truncated[i : i + batch_size]
            logger.info(
                f"Embedding batch {i // batch_size + 1}/"
                f"{(len(truncated) + batch_size - 1) // batch_size} "
                f"({len(chunk)} texts)"
            )
            batch_embs = self._embeddings.embed(chunk)
            all_embeddings.extend(batch_embs)

        return all_embeddings

    def _combine_scores(self, resumes: list[RankedResume]) -> list[RankedResume]:
        """Compute combined score from BM25 and embedding scores.

        Uses configured weights. Resumes that failed BM25 filter get
        their BM25 contribution zeroed but still receive embedding scores.

        Args:
            resumes: RankedResume list with both scores populated.

        Returns:
            Same list with combined_score populated.

        """
        bm25_scores = [r.bm25_score for r in resumes]
        emb_scores = [r.embedding_score for r in resumes]

        max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1.0
        max_emb = max(emb_scores) if emb_scores and max(emb_scores) > 0 else 1.0

        for r in resumes:
            norm_bm25 = r.bm25_score / max_bm25
            norm_emb = r.embedding_score / max_emb
            r.combined_score = self._bm25_weight * norm_bm25 + self._embedding_weight * norm_emb

        return resumes
