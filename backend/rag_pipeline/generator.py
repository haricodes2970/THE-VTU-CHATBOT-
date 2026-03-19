"""
backend/rag_pipeline/generator.py
Generates answers using Groq (Llama 3) with retrieved context chunks.
"""
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings

SYSTEM_PROMPT = """You are VTU Exam Assistant — an AI helper for Visvesvaraya Technological University students.

Rules:
1. Answer ONLY based on the provided context. Do not invent facts.
2. If the answer is not in the context, say exactly: "I don't have that information in my knowledge base. Please check the official VTU website at vtu.ac.in"
3. Be concise and direct. When asked about exam dates, state the date clearly.
4. Always mention the source circular title if available.
5. Use simple, student-friendly language.
"""


class ResponseGenerator:
    """Generates LLM responses using Groq + Llama 3 with retrieved context."""

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
            title = chunk.get("metadata", {}).get("title", "")
            date = chunk.get("metadata", {}).get("date", "")
            text = chunk.get("text", "")
            header = f"[Source {i}"
            if title:
                header += f": {title}"
            if date:
                header += f" ({date})"
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
        Returns the answer string.
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
                max_tokens=1024,
                temperature=0.1,
            )
            answer = response.choices[0].message.content.strip()
            logger.debug(f"Generated answer ({len(answer)} chars)")
            return answer
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def generate_with_citations(self, query: str, chunks: list[dict]) -> dict:
        """
        Generate answer and include source references.
        Returns {answer, sources}.
        """
        answer = self.generate(query, chunks)
        sources = [
            {
                "title": c.get("metadata", {}).get("title", ""),
                "url": c.get("metadata", {}).get("source_url", ""),
                "score": c.get("score", 0),
            }
            for c in chunks
        ]
        return {"answer": answer, "sources": sources}
