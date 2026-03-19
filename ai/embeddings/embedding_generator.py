"""
ai/embeddings/embedding_generator.py
Generates 384-dimensional embeddings using fastembed (ONNX, no torch required).
"""
import time
from functools import lru_cache

from loguru import logger

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 32


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the embedding model (singleton)."""
    from fastembed import TextEmbedding
    logger.info(f"Loading embedding model: {MODEL_NAME}")
    model = TextEmbedding(model_name=MODEL_NAME)
    logger.info("Embedding model loaded")
    return model


class EmbeddingGenerator:
    """Generates sentence embeddings using all-MiniLM-L6-v2 (384 dimensions)."""

    @property
    def model(self):
        return _load_model()

    def generate(self, text: str) -> list[float]:
        """Generate a single embedding vector for the given text."""
        t0 = time.perf_counter()
        embedding = list(self.model.embed([text]))[0].tolist()
        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(f"Embedding generated in {elapsed:.1f}ms (dim={len(embedding)})")
        return embedding

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts in batches.
        Returns list of embedding vectors.
        """
        t0 = time.perf_counter()
        embeddings = [e.tolist() for e in self.model.embed(texts, batch_size=BATCH_SIZE)]
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(f"Batch of {len(texts)} embedded in {elapsed:.1f}ms")
        return embeddings

    def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a user query (same as generate, with extra logging)."""
        logger.debug(f"Generating query embedding for: {query[:80]}")
        return self.generate(query)
