# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""ChromaDB-based vector store for RAG functionality."""

from __future__ import annotations

import logging
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except Exception:
    chromadb = None
    Settings = None
    CHROMADB_AVAILABLE = False

from .FFEmbeddings import FFEmbeddings
from .text_splitter import TextChunk

logger = logging.getLogger(__name__)


class FFVectorStore:
    """ChromaDB-backed vector store for document embeddings.

    Provides persistent storage and similarity search for text chunks
    using embeddings from FFEmbeddings.

    Args:
        collection_name: Name of the ChromaDB collection.
        persist_dir: Directory for persistent storage.
        embedding_model: FFEmbeddings instance or model string.
        client: Optional pre-configured ChromaDB client.

    Raises:
        ImportError: If chromadb is not installed or incompatible.

    Example:
        >>> store = FFVectorStore("my_collection", "./chroma_db")
        >>> store.add_chunks([TextChunk(content="Hello world", chunk_index=0, ...)])
        >>> results = store.search("greeting", n_results=5)

    """

    def __init__(
        self,
        collection_name: str = "ffclients_kb",
        persist_dir: str = "./chroma_db",
        embedding_model: FFEmbeddings | str | None = None,
        client: Any | None = None,
    ) -> None:
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is not installed or not compatible with this Python version. "
                "Install with: pip install chromadb>=0.4.0. "
                "Note: chromadb may have compatibility issues with Python 3.14+."
            )

        self.collection_name = collection_name
        self.persist_dir = persist_dir

        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )

        if embedding_model is None:
            self._embeddings = FFEmbeddings()
        elif isinstance(embedding_model, str):
            self._embeddings = FFEmbeddings(model=embedding_model)
        else:
            self._embeddings = embedding_model

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"FFVectorStore initialized: collection={collection_name}, "
            f"persist_dir={persist_dir}, count={self._collection.count()}"
        )

    def add_chunks(
        self,
        chunks: list[TextChunk],
        ids: list[str] | None = None,
        index_type: str = "default",
        document_checksum: str = "",
    ) -> int:
        """Add text chunks to the vector store.

        Args:
            chunks: List of TextChunk objects to add.
            ids: Optional list of unique IDs for each chunk.
                 If not provided, IDs are generated.
            index_type: The indexing strategy used (for clean index management).
            document_checksum: Checksum of the source document.

        Returns:
            Number of chunks added.

        """
        if not chunks:
            return 0

        from datetime import datetime

        texts = [chunk.content for chunk in chunks]

        embeddings = self._embeddings.embed(texts)

        indexed_at = datetime.now().isoformat()

        if ids is None:
            ids = [
                f"{(chunk.metadata or {}).get('reference_name', 'doc')}_{index_type}_{chunk.chunk_index}_{i}"
                for i, chunk in enumerate(chunks)
            ]

        metadatas = []
        for chunk in chunks:
            meta = chunk.metadata or {}
            meta["_chunk_index"] = chunk.chunk_index
            meta["_start_char"] = chunk.start_char
            meta["_end_char"] = chunk.end_char
            meta["index_type"] = index_type
            meta["document_checksum"] = document_checksum
            meta["indexed_at"] = indexed_at
            metadatas.append(meta)

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(chunks)} chunks to collection {self.collection_name}")
        return len(chunks)

    def add_documents(
        self,
        documents: list[dict],
        text_key: str = "content",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> int:
        """Add documents with automatic chunking.

        Args:
            documents: List of document dicts containing text.
            text_key: Key to access text content in each document.
            chunk_size: Maximum characters per chunk.
            chunk_overlap: Overlap between chunks.

        Returns:
            Total number of chunks added.

        """
        from .text_splitter import split_documents

        chunks = split_documents(
            documents,
            text_key=text_key,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        return self.add_chunks(chunks)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            query: Query text to search for.
            n_results: Maximum number of results to return.
            where: Optional metadata filter (e.g., {"reference_name": "doc1"}).
            where_document: Optional document content filter.

        Returns:
            List of result dicts with keys: id, content, metadata, distance.

        """
        query_embedding = self._embeddings.embed_single(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )

        formatted_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted_results.append(
                    {
                        "id": doc_id,
                        "content": results["documents"][0][i] if results["documents"] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )

        logger.debug(f"Search returned {len(formatted_results)} results for query: {query[:50]}...")
        return formatted_results

    def delete(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
    ) -> int:
        """Delete documents from the store.

        Args:
            ids: List of document IDs to delete.
            where: Metadata filter for documents to delete.

        Returns:
            Number of documents deleted.

        """
        if ids is None and where is None:
            raise ValueError("Must provide either ids or where filter")

        self._collection.delete(ids=ids, where=where)
        logger.info(f"Deleted documents from collection {self.collection_name}")
        return 0

    def delete_by_reference(self, reference_name: str) -> None:
        """Delete all chunks from a specific document.

        Args:
            reference_name: The reference_name metadata to match.

        """
        self._collection.delete(where={"reference_name": reference_name})
        logger.info(f"Deleted all chunks for reference: {reference_name}")

    def delete_by_reference_and_type(self, reference_name: str, index_type: str) -> int:
        """Delete chunks for a specific document and index type.

        Args:
            reference_name: The reference_name metadata to match.
            index_type: The index_type metadata to match.

        Returns:
            Number of chunks deleted (approximate).

        """
        self._collection.delete(
            where={"$and": [{"reference_name": reference_name}, {"index_type": index_type}]}
        )
        logger.info(f"Deleted chunks for reference={reference_name}, index_type={index_type}")
        return 0

    def get_indexed_documents(self, index_type: str | None = None) -> list[dict[str, Any]]:
        """Get list of indexed documents with their checksums and index types.

        Args:
            index_type: Optional filter by index type.

        Returns:
            List of dicts with reference_name, index_type, document_checksum, indexed_at.

        """
        where_filter = None
        if index_type:
            where_filter = {"index_type": index_type}

        results = self._collection.get(
            where=where_filter,
            include=["metadatas"],
        )

        indexed_docs = {}
        if results["metadatas"]:
            for meta in results["metadatas"]:
                ref_name = meta.get("reference_name")
                idx_type = meta.get("index_type", "unknown")
                checksum = meta.get("document_checksum", "")
                indexed_at = meta.get("indexed_at", "")

                if ref_name:
                    key = (ref_name, idx_type)
                    if key not in indexed_docs or (
                        indexed_at and indexed_at > indexed_docs[key].get("indexed_at", "")
                    ):
                        indexed_docs[key] = {
                            "reference_name": ref_name,
                            "index_type": idx_type,
                            "document_checksum": checksum,
                            "indexed_at": indexed_at,
                        }

        return list(indexed_docs.values())

    def needs_reindex(self, reference_name: str, checksum: str, index_type: str) -> bool:
        """Check if a document needs re-indexing.

        Args:
            reference_name: Document reference name.
            checksum: Current document checksum.
            index_type: Target index type.

        Returns:
            True if document needs re-indexing (not found or checksum changed).

        """
        results = self._collection.get(
            where={
                "$and": [
                    {"reference_name": reference_name},
                    {"index_type": index_type},
                ]
            },
            include=["metadatas"],
            limit=1,
        )

        if not results["metadatas"] or len(results["metadatas"]) == 0:
            logger.debug(f"Document {reference_name} not indexed with type {index_type}")
            return True

        existing_checksum = results["metadatas"][0].get("document_checksum", "")
        if existing_checksum != checksum:
            logger.info(
                f"Document {reference_name} checksum changed "
                f"({existing_checksum[:8]} -> {checksum[:8]}), needs reindex"
            )
            return True

        logger.debug(f"Document {reference_name} already indexed with type {index_type}")
        return False

    def count(self) -> int:
        """Get the number of documents in the collection."""
        return self._collection.count()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dict with collection stats including count and metadata info.

        """
        count = self._collection.count()

        return {
            "collection_name": self.collection_name,
            "count": count,
            "persist_dir": self.persist_dir,
            "embedding_model": self._embeddings.model,
        }

    def list_documents(self) -> list[str]:
        """List unique document reference names in the collection.

        Returns:
            List of unique reference_name values.

        """
        results = self._collection.get(include=["metadatas"])

        reference_names = set()
        if results["metadatas"]:
            for meta in results["metadatas"]:
                if "reference_name" in meta:
                    reference_names.add(meta["reference_name"])

        return sorted(reference_names)

    def get_all_documents(self) -> list[dict[str, Any]]:
        """Get all documents in the collection.

        Returns:
            List of all documents with id, content, and metadata.

        """
        results = self._collection.get(include=["documents", "metadatas"])

        documents = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                documents.append(
                    {
                        "id": doc_id,
                        "content": results["documents"][i] if results["documents"] else "",
                        "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    }
                )

        return documents

    def clear(self) -> None:
        """Clear all documents from the collection."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Cleared collection: {self.collection_name}")
