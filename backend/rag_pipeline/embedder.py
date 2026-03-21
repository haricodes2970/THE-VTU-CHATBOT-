"""
backend/rag_pipeline/embedder.py
Embeds document chunks and upserts them to Pinecone vector database.

Vector ID scheme: c{circular_id}_{chunk_index}
This allows prefix-based deletion and atomic namespace swapping.
"""
import time
from typing import Optional

from loguru import logger

from ai.embeddings.embedding_generator import EmbeddingGenerator
from backend.core.config import settings

PINECONE_BATCH_SIZE = 100
MAIN_NAMESPACE = ""  # default Pinecone namespace


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
        time.sleep(10)

    return pc.Index(settings.pinecone_index_name)


class VectorEmbedder:
    """Embeds text chunks and stores them in Pinecone."""

    def __init__(self):
        self._generator = EmbeddingGenerator()
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = _get_pinecone_index()
        return self._index

    # ── Metadata builder ──────────────────────────────────────────

    def _build_vector_metadata(self, chunk: dict, circular, chunk_index: int) -> dict:
        """Build Pinecone metadata dict with all required fields."""
        return {
            "text": chunk["text"][:1000],
            "circular_id": circular.id,
            "source_url": str(getattr(circular, "url", "")),
            "title": str(getattr(circular, "title", ""))[:200],
            "date": str(getattr(circular, "circular_date", "") or ""),
            "scheme": str(getattr(circular, "scheme", "") or ""),
            "course_type": str(getattr(circular, "course_type", "") or ""),
            "exam_session": str(getattr(circular, "exam_session", "") or ""),
            "semester_range": str(getattr(circular, "semester_range", "") or ""),
            "published_date": str(getattr(circular, "circular_date", "") or ""),
            "is_latest": not bool(getattr(circular, "is_superseded", False)),
            "pdf_url": str(getattr(circular, "url", "")),
            "chunk_index": str(chunk_index),
        }

    # ── Core upsert ───────────────────────────────────────────────

    def _upsert_vectors(
        self, vectors: list[tuple], namespace: str = MAIN_NAMESPACE
    ) -> int:
        """Batch upsert vectors to a Pinecone namespace. Returns count upserted."""
        upserted = 0
        for i in range(0, len(vectors), PINECONE_BATCH_SIZE):
            batch = vectors[i: i + PINECONE_BATCH_SIZE]
            self.index.upsert(vectors=batch, namespace=namespace)
            upserted += len(batch)
            logger.debug(
                f"Upserted batch {i // PINECONE_BATCH_SIZE + 1}: "
                f"{len(batch)} vectors (namespace='{namespace}')"
            )
        return upserted

    # ── Build vectors from circular ───────────────────────────────

    def _build_vectors_for_circular(self, circular) -> list[tuple]:
        """
        Chunk circular content, generate embeddings, return list of
        (vector_id, embedding, metadata) tuples ready for Pinecone upsert.
        """
        from backend.rag_pipeline.chunker import DocumentChunker

        if not getattr(circular, "content", None):
            logger.warning(f"Circular {circular.id} has no content to embed")
            return []

        chunker = DocumentChunker()
        chunks = chunker.chunk_with_metadata(
            circular.content,
            {
                "source_url": circular.url,
                "circular_title": circular.title,
                "circular_date": circular.circular_date,
            },
        )

        if not chunks:
            return []

        texts = [c["text"] for c in chunks]
        embeddings = self._generator.generate_batch(texts)

        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vid = f"c{circular.id}_{i}"
            metadata = self._build_vector_metadata(chunk, circular, i)
            vectors.append((vid, embedding, metadata))

        return vectors

    # ── Public embed methods ──────────────────────────────────────

    def embed_circular(self, circular, db=None) -> int:
        """
        Full pipeline for one Circular model instance.
        Chunks, embeds, upserts to main namespace, marks is_indexed=True.
        Returns number of vectors upserted.
        """
        vectors = self._build_vectors_for_circular(circular)
        if not vectors:
            return 0

        count = self._upsert_vectors(vectors, namespace=MAIN_NAMESPACE)
        logger.info(f"Embedded circular {circular.id}: {count} vectors")

        if db is not None and count > 0:
            from sqlalchemy import text as _text
            db.execute(
                _text("UPDATE circulars SET is_indexed = TRUE WHERE id = :id"),
                {"id": circular.id},
            )
            db.commit()
            logger.info(f"Marked circular {circular.id} as indexed")

        return count

    def embed_circular_to_namespace(self, circular, namespace: str, db=None) -> int:
        """
        Embed circular into a specific namespace (used during atomic re-index).
        Does NOT mark is_indexed in DB.
        Returns chunk count.
        """
        vectors = self._build_vectors_for_circular(circular)
        if not vectors:
            return 0
        count = self._upsert_vectors(vectors, namespace=namespace)
        logger.info(
            f"Embedded circular {circular.id} → namespace '{namespace}': {count} vectors"
        )
        return count

    def embed_and_store(self, chunks: list[dict]) -> int:
        """
        Embed raw chunks (no circular object) and upsert to main namespace.
        Legacy method — prefer embed_circular for proper metadata.
        """
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self._generator.generate_batch(texts)

        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{chunk.get('source_url', 'doc')}_{chunk.get('chunk_index', i)}"
            metadata = {
                "text": chunk["text"][:1000],
                "source_url": str(chunk.get("source_url", "")),
                "title": str(chunk.get("circular_title", "")),
                "date": str(chunk.get("circular_date", "")),
                "semester": str(chunk.get("semester", "")),
                "chunk_index": str(chunk.get("chunk_index", i)),
                "is_latest": True,
            }
            vectors.append((vector_id, embedding, metadata))

        return self._upsert_vectors(vectors, namespace=MAIN_NAMESPACE)

    # ── Atomic re-index ───────────────────────────────────────────

    def atomic_replace_circular(
        self, old_circular_id: int, new_circular, db=None
    ) -> bool:
        """
        Atomically replace old circular's Pinecone vectors with new ones.

        Steps:
          1. Build vectors from new circular (compute embeddings once)
          2. Upsert to temp namespace, verify count > 0
          3. Delete old vectors from main namespace
          4. Upsert same vectors to main namespace
          5. Delete temp namespace
          Returns True on success; on failure keeps old vectors intact.
        """
        temp_ns = f"temp_{old_circular_id}"

        vectors = self._build_vectors_for_circular(new_circular)
        if not vectors:
            logger.error(
                f"Atomic re-index: new circular {new_circular.id} has no content"
            )
            return False

        try:
            # Step 1: Upsert to temp namespace
            logger.info(
                f"Atomic re-index [{old_circular_id}→{new_circular.id}]: "
                f"upserting {len(vectors)} vectors to temp namespace '{temp_ns}'"
            )
            self._upsert_vectors(vectors, namespace=temp_ns)

            # Step 2: Verify temp has vectors
            time.sleep(2)  # allow Pinecone consistency
            stats = self.index.describe_index_stats()
            ns_data = (stats.get("namespaces") or {}).get(temp_ns, {})
            temp_count = ns_data.get("vector_count", 0)

            if temp_count == 0:
                logger.error(
                    f"Atomic re-index: temp namespace '{temp_ns}' has 0 vectors — aborting"
                )
                self.delete_namespace(temp_ns)
                return False

            logger.info(
                f"Atomic re-index: verified {temp_count} vectors in temp namespace"
            )

            # Step 3: Delete old vectors from main
            self.delete_circular_vectors(old_circular_id)

            # Step 4: Upsert to main namespace (same pre-computed vectors)
            self._upsert_vectors(vectors, namespace=MAIN_NAMESPACE)

            # Step 5: Cleanup temp namespace
            self.delete_namespace(temp_ns)

            if db is not None:
                new_circular.is_indexed = True
                db.commit()

            logger.info(
                f"Atomic re-index complete: {len(vectors)} vectors for "
                f"circular {new_circular.id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Atomic re-index failed [{old_circular_id}→{new_circular.id}]: {e}"
            )
            try:
                self.delete_namespace(temp_ns)
            except Exception:
                pass
            return False

    # ── Delete helpers ────────────────────────────────────────────

    def delete_circular_vectors(self, circular_id: int) -> None:
        """
        Delete all vectors for a circular using Pinecone list-by-prefix.
        Vector IDs follow pattern: c{circular_id}_{chunk_index}
        """
        prefix = f"c{circular_id}_"
        try:
            deleted = 0
            for id_batch in self.index.list(prefix=prefix, namespace=MAIN_NAMESPACE):
                if id_batch:
                    self.index.delete(ids=id_batch, namespace=MAIN_NAMESPACE)
                    deleted += len(id_batch)
            logger.info(
                f"Deleted {deleted} vectors for circular {circular_id} "
                f"(prefix='{prefix}')"
            )
        except Exception as e:
            logger.error(
                f"Error deleting vectors for circular {circular_id}: {e}"
            )

    def delete_namespace(self, namespace: str) -> None:
        """Delete all vectors in a Pinecone namespace."""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted namespace '{namespace}'")
        except Exception as e:
            logger.error(f"Error deleting namespace '{namespace}': {e}")

    # ── Stats ─────────────────────────────────────────────────────

    def get_index_stats(self) -> dict:
        """Return total vector count and dimension."""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", settings.pinecone_dimension),
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"total_vectors": 0, "dimension": settings.pinecone_dimension}
