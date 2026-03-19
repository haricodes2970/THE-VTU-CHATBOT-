"""
tests/test_rag.py
Unit tests for the RAG pipeline — embeddings, chunking, retrieval (mocked).
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.rag_pipeline.chunker import DocumentChunker


# ── Embedding tests ───────────────────────────────────────────────────────────

class TestEmbeddingGenerator:
    def test_embedding_dimension(self):
        from ai.embeddings.embedding_generator import EmbeddingGenerator
        gen = EmbeddingGenerator()
        embedding = gen.generate("test text for VTU exam")
        assert len(embedding) == 384, f"Expected 384 dimensions, got {len(embedding)}"

    def test_batch_embedding(self):
        from ai.embeddings.embedding_generator import EmbeddingGenerator
        gen = EmbeddingGenerator()
        texts = ["DBMS exam date", "5th semester schedule", "VTU circular"]
        embeddings = gen.generate_batch(texts)
        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 384

    def test_query_embedding_returns_list(self):
        from ai.embeddings.embedding_generator import EmbeddingGenerator
        gen = EmbeddingGenerator()
        result = gen.generate_query_embedding("when is my DBMS exam?")
        assert isinstance(result, list)
        assert len(result) == 384


# ── Chunker tests ─────────────────────────────────────────────────────────────

class TestDocumentChunker:
    chunker = DocumentChunker()

    SAMPLE_TEXT = (
        "The 5th semester examination for Computer Science Engineering will be held "
        "from 10th December 2025. Students must carry their hall tickets. "
        "Database Management Systems exam is on 10/12/2025 at 10:30 AM. "
        "Data Structures exam is on 12/12/2025 at 10:30 AM. "
        "Operating Systems exam is on 14/12/2025 at 2:00 PM. "
        "All students must report 30 minutes before the exam. Mobiles are not allowed."
    )

    def test_chunk_returns_list(self):
        chunks = self.chunker.chunk(self.SAMPLE_TEXT, source="test")
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_chunk_metadata_keys(self):
        chunks = self.chunker.chunk(self.SAMPLE_TEXT, source="http://vtu.ac.in/test.pdf")
        for chunk in chunks:
            assert "text" in chunk
            assert "chunk_index" in chunk
            assert "total_chunks" in chunk

    def test_chunk_with_metadata(self):
        meta = {
            "source_url": "http://vtu.ac.in/circular.pdf",
            "circular_title": "5th Sem Exam Schedule",
            "circular_date": "2025-11-01",
        }
        chunks = self.chunker.chunk_with_metadata(self.SAMPLE_TEXT, meta)
        assert all(c["source_url"] == meta["source_url"] for c in chunks)
        assert all(c["circular_title"] == meta["circular_title"] for c in chunks)

    def test_empty_text_returns_empty(self):
        assert self.chunker.chunk("") == []
        assert self.chunker.chunk("   ") == []

    def test_chunk_exam_schedule(self):
        schedule = [
            {"subject": "DBMS", "date": "10/12/2025", "time": "10:30 AM", "semester": 5},
            {"subject": "OS", "date": "12/12/2025", "time": "10:30 AM", "semester": 5},
        ]
        chunks = self.chunker.chunk_exam_schedule(schedule)
        assert len(chunks) == 2
        assert "DBMS" in chunks[0]["text"]
        assert "10/12/2025" in chunks[0]["text"]

    def test_overlap_produces_multiple_chunks_on_long_text(self):
        long_text = " ".join(["VTU exam schedule information"] * 100)
        chunks = self.chunker.chunk(long_text, source="test")
        assert len(chunks) > 1


# ── RAG Chain (mocked) ────────────────────────────────────────────────────────

class TestRAGChain:
    @patch("backend.rag_pipeline.rag_chain.ContextRetriever")
    @patch("backend.rag_pipeline.rag_chain.ResponseGenerator")
    def test_query_returns_expected_keys(self, mock_gen_cls, mock_ret_cls):
        mock_retriever = MagicMock()
        mock_generator = MagicMock()
        mock_ret_cls.return_value = mock_retriever
        mock_gen_cls.return_value = mock_generator

        mock_retriever.retrieve.return_value = [
            {"text": "DBMS exam is on 10/12/2025", "score": 0.9, "metadata": {"title": "Schedule", "source_url": ""}}
        ]
        mock_retriever.retrieve_with_filters.return_value = []
        mock_generator.generate_with_citations.return_value = {
            "answer": "DBMS exam is on 10 December 2025.",
            "sources": [],
        }

        from backend.rag_pipeline.rag_chain import RAGChain
        chain = RAGChain()
        result = chain.query("When is my 5th sem DBMS exam?")

        assert "answer" in result
        assert "sources" in result
        assert "intent" in result
        assert "retrieval_count" in result
        assert "response_time_ms" in result

    @patch("backend.rag_pipeline.rag_chain.ContextRetriever")
    @patch("backend.rag_pipeline.rag_chain.ResponseGenerator")
    def test_no_context_returns_no_info_response(self, mock_gen_cls, mock_ret_cls):
        mock_retriever = MagicMock()
        mock_ret_cls.return_value = mock_retriever
        mock_retriever.retrieve.return_value = []
        mock_retriever.retrieve_with_filters.return_value = []

        from backend.rag_pipeline.rag_chain import RAGChain
        chain = RAGChain()
        result = chain.query("random garbage xyz query")

        assert result["retrieval_count"] == 0
        assert "vtu.ac.in" in result["answer"].lower()
