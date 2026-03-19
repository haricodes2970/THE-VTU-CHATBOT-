"""
backend/rag_pipeline/chunker.py
Splits documents into overlapping chunks for vector storage.
"""
from loguru import logger

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


class DocumentChunker:
    """Splits text into overlapping chunks with metadata."""

    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(self, text: str, source: str = "") -> list[dict]:
        """
        Split text into overlapping chunks.
        Returns list of {text, source, chunk_index, total_chunks}.
        """
        if not text or not text.strip():
            return []

        raw_chunks = self._splitter.split_text(text)
        chunks = [
            {
                "text": chunk,
                "source": source,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            }
            for i, chunk in enumerate(raw_chunks)
        ]
        logger.debug(f"Split into {len(chunks)} chunks (source={source[:40]})")
        return chunks

    def chunk_with_metadata(self, text: str, metadata: dict) -> list[dict]:
        """
        Split text and attach metadata dict to each chunk.
        Metadata keys: source_url, circular_title, circular_date, etc.
        """
        base_chunks = self.chunk(text, source=metadata.get("source_url", ""))
        for chunk in base_chunks:
            chunk.update({
                "source_url": metadata.get("source_url", ""),
                "circular_title": metadata.get("circular_title", ""),
                "circular_date": str(metadata.get("circular_date", "")),
            })
        return base_chunks

    def chunk_exam_schedule(self, structured_data: list[dict]) -> list[dict]:
        """
        Special chunking for exam schedule rows.
        Each row (subject + date + time) becomes its own chunk.
        """
        chunks = []
        for i, row in enumerate(structured_data):
            subject = row.get("subject", "")
            date = row.get("date", "")
            time_slot = row.get("time", "")
            semester = row.get("semester", "")

            text = f"Exam: {subject}"
            if date:
                text += f" | Date: {date}"
            if time_slot:
                text += f" | Time: {time_slot}"
            if semester:
                text += f" | Semester: {semester}"

            chunks.append({
                "text": text,
                "source": "exam_schedule",
                "chunk_index": i,
                "total_chunks": len(structured_data),
                "subject": subject,
                "exam_date": date,
                "exam_time": time_slot,
                "semester": semester,
            })
        return chunks
