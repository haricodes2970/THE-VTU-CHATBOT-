# VTU Smart Scheduler — System Architecture

## Overview

The VTU Smart Scheduler is a full-stack AI chatbot application consisting of five major subsystems:

1. **Web Scraper** — Periodically fetches VTU circulars and exam schedules
2. **NLP Pipeline** — Understands user queries (intent + entity extraction)
3. **RAG Pipeline** — Retrieves relevant context and generates answers
4. **FastAPI Backend** — RESTful API serving all frontend requests
5. **React Frontend** — Chat UI, circulars browser, exam schedule viewer

---

## Data Flow

```
VTU Website
    │
    ▼ (every 6 hours via APScheduler)
VTUScraper.scrape_circulars()
    │
    ▼
PDFDownloader.download_pdf()
    │
    ▼
PDFParser.parse()  ←── pdfplumber → PyPDF2 → OCR fallback
    │
    ▼
CircularService.save_circular()  ──→  PostgreSQL
    │
    ▼
DocumentChunker.chunk_with_metadata()  (512 chars, 50 overlap)
    │
    ▼
EmbeddingGenerator.generate_batch()  ←── all-MiniLM-L6-v2
    │
    ▼
VectorEmbedder.embed_and_store()  ──→  Pinecone
    │
    ▼
NotificationManager.notify_new_circular()  ──→  Email / Telegram
```

## Query Flow

```
User: "When is my 5th sem DBMS exam?"
    │
    ▼
IntentDetector.detect()  →  GET_EXAM_DATE (confidence: 0.85)
    │
    ▼
EntityExtractor.extract()  →  {semester: 5, subject: "DBMS"}
    │
    ▼
QueryProcessor.build_search_query()
    →  "Database Management Systems exam date 5th semester"
    │
    ▼
EmbeddingGenerator.generate_query_embedding()  →  [0.12, -0.05, ...]
    │
    ▼
ContextRetriever.retrieve_with_filters(filters={semester: "5"}, top_k=5)
    │
    ▼
Pinecone.query()  →  [{text: "DBMS exam 10/12/2025...", score: 0.91}, ...]
    │
    ▼
ResponseGenerator.generate(query, chunks)
    │  Groq Llama3-8b: "Answer ONLY from context..."
    ▼
"DBMS exam is on 10 December 2025 at 10:30 AM. Source: 5th Sem Schedule."
    │
    ▼
ChatService.chat()  →  ChatResponse{answer, confidence: HIGH, sources, ...}
    │
    ▼
POST /api/v1/chat  →  JSON response to frontend
```

---

## Component Descriptions

### VTUScraper
Scrapes `vtu.ac.in/circulars` for PDF links. Uses BeautifulSoup + lxml.
Retries 3x with exponential backoff. Rate-limited to 2s between requests.

### PDFParser
Three-tier extraction: pdfplumber (layout-aware) → PyPDF2 → pytesseract OCR.
Cleans boilerplate (VTU letterhead, page numbers, footer patterns).
Returns `{text, tables, confidence_score, extraction_method}`.

### DocumentChunker
Uses LangChain `RecursiveCharacterTextSplitter` (512 chars, 50 overlap).
Special mode for exam schedule tables: one chunk per row for precise retrieval.
Each chunk carries metadata: `{source_url, circular_title, date, semester}`.

### EmbeddingGenerator
`all-MiniLM-L6-v2` from sentence-transformers (384 dimensions).
Loaded once via `lru_cache`. Batch size 32 for throughput.

### ContextRetriever
Queries Pinecone with optional metadata filters (`semester`, `subject`).
Minimum score threshold: 0.5 (filters irrelevant results).

### ResponseGenerator
Groq `llama3-8b-8192` with strict system prompt:
- Answer ONLY from context
- If not found: redirect to vtu.ac.in
- Temperature: 0.1 (factual)
- Max tokens: 1024

### ConversationManager
In-memory per-session history. TTL: 2 hours.
Provides last 5 exchanges as context to the LLM.

### NotificationManager
Creates `Notification` records (PENDING) before sending.
DEV mode: logs instead of sending.
Retry job runs every 30 minutes for FAILED records.

---

## Technology Choices

| Decision | Rationale |
|----------|-----------|
| **Groq** over OpenAI | Free tier, very fast inference (Llama 3) |
| **Pinecone** over local FAISS | Managed, scalable, no GPU needed |
| **all-MiniLM-L6-v2** | Small (384-dim), fast, good semantic quality |
| **spaCy** over transformer NER | Lightweight, fast, sufficient for structured entity extraction |
| **FastAPI** | Async support, auto-generated OpenAPI docs, Pydantic validation |
| **APScheduler** | Simple, no separate service needed (vs Celery) |
| **PostgreSQL** | Relational for structured data (users, subscriptions, notifications) |
