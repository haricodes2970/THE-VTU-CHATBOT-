"""
backend/rag_pipeline/generator.py
Generates answers using Groq (Llama 3.1) with retrieved context chunks.
Includes generate_with_fallback for structured bot behavior when answer not found.
"""
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings

SYSTEM_PROMPT = """
You are VTU Exam Assistant. You help VTU students find exam dates
from official VTU timetables.

STRICT RULES:
1. Answer ONLY from the context chunks provided. Never make up dates.
2. VTU timetable text is often messy from PDF extraction. Look carefully
   for date patterns like: 12/12/2025, December 12, 10:00 FN, 02:00 AN.
   FN = Forenoon (10:00 AM). AN = Afternoon (2:00 PM).
3. When you find exam dates, respond in EXACTLY this format:
   📅 [Subject Name]
   Date: [DD/MM/YYYY]
   Time: [10:00 AM / 2:00 PM]
   Session: [exam session e.g. Dec 2025/Jan 2026]
   Scheme: [2021/2022/etc]
   ⚠️ Updated timetable available as of [published_date] —
      verify at vtu.ac.in before your exam.
4. If context has multiple timetables for same subject, use the one
   with the MOST RECENT published_date. Say
   "⚠️ Updated timetable available as of [date]" in your response.
5. If you genuinely cannot find the exam date in context:
   Respond with exactly: "NOT_FOUND"
   Do not say "I don't have information". Just: "NOT_FOUND"
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

        entities = session_entities or {}
        has_context = bool(
            entities.get("semester")
            or entities.get("scheme")
            or entities.get("course_type")
        )

        if not has_context:
            logger.info("NOT_FOUND with no session context — asking for details")
            return _ASK_FOR_DETAILS

        # User already gave context but still not found — show fallback PDF
        if fallback_pdf_url:
            scheme = entities.get("scheme", "2021")
            logger.info(f"NOT_FOUND with context — showing fallback PDF: {fallback_pdf_url}")
            return _FALLBACK_WITH_PDF.format(
                scheme=scheme, pdf_url=fallback_pdf_url
            )

        # Try to fetch PDF URL from DB as last resort
        if db is not None:
            from backend.rag_pipeline.retriever import ContextRetriever
            pdf_url = ContextRetriever().get_latest_timetable_pdf_url(
                scheme=entities.get("scheme"),
                course_type=entities.get("course_type"),
                db=db,
            )
            if pdf_url:
                scheme = entities.get("scheme", "2021")
                return _FALLBACK_WITH_PDF.format(scheme=scheme, pdf_url=pdf_url)

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
