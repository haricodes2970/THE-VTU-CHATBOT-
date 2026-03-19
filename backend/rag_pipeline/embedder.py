"""
backend/rag_pipeline/embedder.py
Embeds document chunks and upserts them to Pinecone vector database.
"""
import time
from typing import Optional

from loguru import logger

from ai.embeddings.embedding_generator import EmbeddingGenerator
from backend.core.config import settings

PINECONE_BATCH_SIZE = 100


def _get_pinecone_index():
    """Connect to Pinecone and return the index object."""
    from pinecone import Pinecone, ServerlessSpec
    pc = Pinecone(api_key=settings.pinecone_api_key)

    existing = [idx.name for idx in pc.list_indexes()]
    if settings.pinecone_index_name not in existing:
        logger.info(f"Creating Pinecone index: {settings.pinecone_index_name}")
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.pinecone_dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        import time as _time
        _time.sleep(10)

    return pc.Index(settings.pinecone_index_name)


class VectorEmbedder:
    """Embeds text chunks and stores them in Pinecone."""

    def __init__(self):
        self._generator = EmbeddingGenerator()
        self._index = None  # lazy connect

    @property
    def index(self):
        if self._index is None:
            self._index = _get_pinecone_index()
        return self._index

    def embed_and_store(self, chunks: list[dict]) -> int:
        """
        Embed all chunks and upsert to Pinecone in batches of 100.
        Returns number of vectors upserted.
        """
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self._generator.generate_batch(texts)

        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{chunk.get('source_url', 'doc')}_{chunk.get('chunk_index', i)}"
            # Sanitise for Pinecone (string values only in metadata)
            metadata = {
                "text": chunk["text"][:1000],
                "source_url": str(chunk.get("source_url", "")),
                "title": str(chunk.get("circular_title", "")),
                "date": str(chunk.get("circular_date", "")),
                "semester": str(chunk.get("semester", "")),
                "chunk_index": str(chunk.get("chunk_index", i)),
            }
            vectors.append((vector_id, embedding, metadata))

        # Batch upsert
        upserted = 0
        for i in range(0, len(vectors), PINECONE_BATCH_SIZE):
            batch = vectors[i: i + PINECONE_BATCH_SIZE]
            self.index.upsert(vectors=batch)
            upserted += len(batch)
            logger.debug(f"Upserted batch {i//PINECONE_BATCH_SIZE + 1}: {len(batch)} vectors")

        logger.info(f"Total upserted: {upserted} vectors")
        return upserted

    def embed_circular(self, circular, db=None) -> int:
        """
        Full pipeline for one Circular model instance.
        Chunks text, embeds, stores, and marks is_indexed=True in DB.
        """
        from backend.rag_pipeline.chunker import DocumentChunker
        if not circular.content:
            logger.warning(f"Circular {circular.id} has no content to embed")
            return 0

        chunker = DocumentChunker()
        chunks = chunker.chunk_with_metadata(
            circular.content,
            {
                "source_url": circular.url,
                "circular_title": circular.title,
                "circular_date": circular.circular_date,
            },
        )

        count = self.embed_and_store(chunks)

        if db is not None and count > 0:
            circular.is_indexed = True
            db.commit()
            logger.info(f"Marked circular {circular.id} as indexed")

        return count

    def delete_circular(self, circular_url: str) -> None:
        """Remove all vectors for a given circular URL."""
        try:
            # Pinecone doesn't support delete by metadata filter in free tier;
            # list-based delete requires knowing IDs. Log a warning.
            logger.warning(
                f"Delete by URL not fully supported on free Pinecone tier: {circular_url}"
            )
        except Exception as e:
            logger.error(f"Error deleting vectors for {circular_url}: {e}")

    def get_index_stats(self) -> dict:
        """Return vector count and index fullness."""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", settings.pinecone_dimension),
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"total_vectors": 0, "dimension": settings.pinecone_dimension}
