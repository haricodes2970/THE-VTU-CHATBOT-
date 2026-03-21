"""
backend/rag_pipeline/generator.py
Generates answers using Groq (Llama 3.1) with retrieved context chunks.
Includes generate_with_fallback for structured bot behavior when answer not found.
"""
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings

SYSTEM_PROMPT = """
You are VTU Exam Assistant. You help VTU students find exam timetables
from official VTU circular data.

The context chunks contain timetable metadata — title, scheme, semester,
exam session, published date, and a PDF download link. The actual per-subject
dates are inside the PDF. Your job is to match the user's query to the right
timetable and direct them to it.

RULES:
1. Answer ONLY from the context chunks provided. Never invent information.
2. When you find a relevant timetable, respond in this format:
   📅 [Title]
   Scheme: [scheme] | Semester: [semester_range] | Session: [exam_session]
   Published: [published_date]
   📎 Download timetable PDF: [pdf_url]
   ⚠️ Always verify dates at vtu.ac.in before your exam.
3. If multiple timetables match, show the one with the most recent published_date first.
4. If the context contains timetable info but no exact subject dates — that is fine.
   Show the timetable metadata and PDF link. The student can check dates in the PDF.
5. If no relevant timetable exists in context at all:
   Respond with exactly: "NOT_FOUND"
6. Never mention Pinecone, vectors, embeddings, or internal systems.
"""

_ASK_FOR_DETAILS = (
    "Could you tell me your semester and branch? "
    "For example: '5th sem CSE 2021 scheme BE/BTech'\n"
    "This will help me find the right timetable for you."
)

_FALLBACK_WITH_PDF = (
    "I couldn't find that specific exam date in my knowledge base.\n"
    "Here is the latest {scheme} scheme timetable PDF from VTU:\n"
    "📎 {pdf_url}\n"
    "You can also check: vtu.ac.in/en/category/examination/time-table/"
)

_FALLBACK_NO_PDF = (
    "I couldn't find that specific exam date in my knowledge base.\n"
    "Please check the official VTU timetable page:\n"
    "vtu.ac.in/en/category/examination/time-table/"
)


class ResponseGenerator:
    """Generates LLM responses using Groq + Llama 3.1 with retrieved context."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=settings.groq_api_key)
        return self._client

    def format_context(self, chunks: list[dict]) -> str:
        """Format retrieved chunks into a clean context string for the prompt."""
        if not chunks:
            return "No relevant context found."
        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            title = meta.get("title", "")
            date = meta.get("published_date", "") or meta.get("date", "")
            scheme = meta.get("scheme", "")
            session = meta.get("exam_session", "")
            text = chunk.get("text", "")

            header = f"[Source {i}"
            if title:
                header += f": {title}"
            if scheme:
                header += f" | Scheme: {scheme}"
            if session:
                header += f" | Session: {session}"
            if date:
                header += f" | Published: {date}"
            header += "]"
            parts.append(f"{header}\n{text}")
        return "\n\n".join(parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def generate(self, query: str, context_chunks: list[dict]) -> str:
        """
        Generate an answer for the query using the provided context chunks.
        Returns the answer string (may be "NOT_FOUND").
        """
        context = self.format_context(context_chunks)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            },
        ]
        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=512,
                temperature=0.0,
            )
            answer = response.choices[0].message.content.strip()
            logger.debug(f"Generated answer ({len(answer)} chars)")
            return answer
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def generate_with_fallback(
        self,
        query: str,
        context_chunks: list[dict],
        fallback_pdf_url: str | None = None,
        session_id: str | None = None,
        session_entities: dict | None = None,
        db=None,
    ) -> str:
        """
        Generate answer. If NOT_FOUND:
          - If no semester/branch in session history → ask for details
          - If already asked and still not found → show latest PDF URL
        """
        answer = self.generate(query, context_chunks)

        if answer != "NOT_FOUND":
            return answer

        # NOT_FOUND — if we have retrieved chunks, show their PDF links directly
        if context_chunks:
            seen = set()
            lines = ["Here are the closest VTU timetables I found:\n"]
            for chunk in context_chunks:
                meta = chunk.get("metadata", {})
                title = meta.get("title", "VTU Timetable")
                scheme = meta.get("scheme", "")
                session = meta.get("exam_session", "")
                semester = meta.get("semester_range", "")
                pdf = meta.get("pdf_url", "") or meta.get("source_url", "")
                if not pdf or pdf in seen:
                    continue
                seen.add(pdf)
                label = title
                if scheme:
                    label += f" | Scheme: {scheme}"
                if semester:
                    label += f" | Sem: {semester}"
                if session:
                    label += f" | {session}"
                lines.append(f"📎 {label}\n{pdf}\n")
            if len(lines) > 1:
                lines.append("⚠️ Verify dates at vtu.ac.in before your exam.")
                return "\n".join(lines)

        # No chunks — ask for details or show generic fallback
        entities = session_entities or {}
        has_context = bool(
            entities.get("semester")
            or entities.get("scheme")
            or entities.get("course_type")
        )
        if not has_context:
            return _ASK_FOR_DETAILS

        if fallback_pdf_url:
            scheme = entities.get("scheme", "2021")
            return _FALLBACK_WITH_PDF.format(scheme=scheme, pdf_url=fallback_pdf_url)

        return _FALLBACK_NO_PDF

    def generate_with_citations(self, query: str, chunks: list[dict]) -> dict:
        """
        Generate answer and include source references.
        Returns {answer, sources}.
        """
        answer = self.generate(query, chunks)
        sources = [
            {
                "title": c.get("metadata", {}).get("title", ""),
                "url": c.get("metadata", {}).get("pdf_url", "")
                or c.get("metadata", {}).get("source_url", ""),
                "score": c.get("score", 0),
                "scheme": c.get("metadata", {}).get("scheme", ""),
                "exam_session": c.get("metadata", {}).get("exam_session", ""),
            }
            for c in chunks
        ]
        return {"answer": answer, "sources": sources}
