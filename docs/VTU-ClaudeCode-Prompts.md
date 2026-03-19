# VTU Smart Scheduler — Claude Code Prompts
# Copy each phase prompt and paste directly into Claude Code in VS Code

---

## ─────────────────────────────────────────
## PHASE 1 — Project Setup & Environment
## Estimated time: 5 hours
## ─────────────────────────────────────────

```
You are a Senior Python Backend Engineer. I am building a production-grade AI chatbot 
called "VTU Smart Scheduler" that helps students query VTU university exam schedules 
and circulars using natural language.

MY SETUP:
- OS: Windows 11
- LLM: Groq (Llama 3) — free and fast
- Vector DB: Pinecone (cloud)
- Backend: FastAPI
- Database: PostgreSQL (via Docker)
- Frontend: React + Tailwind CSS

YOUR TASK — Phase 1: Create the complete project structure and environment setup.

Create the following folder structure exactly:
vtu-smart-scheduler/
├── backend/
│   ├── api/
│   │   ├── routes/         (chat.py, circulars.py, schedule.py, notifications.py)
│   │   └── middleware/     (auth.py, rate_limit.py, error_handler.py)
│   ├── services/           (chat_service.py, circular_service.py, schedule_service.py)
│   ├── models/             (models.py — all SQLAlchemy ORM models)
│   ├── rag_pipeline/       (chunker.py, embedder.py, retriever.py, generator.py)
│   └── core/               (config.py, database.py, logger.py)
├── ai/
│   ├── embeddings/         (embedding_generator.py)
│   └── query_processing/   (intent_detector.py, entity_extractor.py)
├── scraper/                (vtu_scraper.py, pdf_downloader.py, pdf_parser.py)
├── notifications/          (email_notifier.py, telegram_notifier.py, notification_manager.py)
├── frontend/               (empty for now)
├── data/
│   ├── raw/
│   ├── processed/
│   └── pdfs/
├── tests/                  (test_scraper.py, test_rag.py, test_api.py)
├── docs/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md

FILES TO CREATE WITH FULL CONTENT:

1. requirements.txt — include these exact packages with versions:
   fastapi==0.111.0, uvicorn[standard]==0.29.0, sqlalchemy==2.0.30, alembic==1.13.1,
   psycopg2-binary==2.9.9, pydantic==2.7.1, pydantic-settings==2.2.1, python-dotenv==1.0.1,
   requests==2.32.2, beautifulsoup4==4.12.3, lxml==5.2.2, pdfplumber==0.11.0,
   PyPDF2==3.0.1, pytesseract==0.3.10, Pillow==10.3.0, spacy==3.7.4,
   python-dateutil==2.9.0, langchain==0.2.1, langchain-groq==0.1.4,
   langchain-pinecone==0.1.1, langchain-community==0.2.1,
   sentence-transformers==3.0.0, pinecone-client==3.2.2, groq==0.9.0,
   apscheduler==3.10.4, python-telegram-bot==21.2, pytest==8.2.1,
   pytest-asyncio==0.23.7, httpx==0.27.0, tenacity==8.3.0, loguru==0.7.2

2. .env.example — with ALL environment variables:
   APP_NAME, APP_ENV, APP_PORT, SECRET_KEY,
   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL,
   GROQ_API_KEY, GROQ_MODEL=llama3-8b-8192,
   PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX_NAME=vtu-circulars, PINECONE_DIMENSION=384,
   VTU_BASE_URL=https://vtu.ac.in, VTU_CIRCULARS_URL, SCRAPER_INTERVAL_HOURS=6, PDF_DOWNLOAD_PATH,
   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
   TELEGRAM_BOT_TOKEN

3. docker-compose.yml — PostgreSQL 16 + Redis 7, with health checks, named volumes

4. backend/core/config.py — Pydantic BaseSettings class loading all env vars,
   with @lru_cache get_settings() function, is_production and is_development properties

5. backend/core/database.py — SQLAlchemy engine with pool_pre_ping=True, pool_size=10,
   SessionLocal factory, Base declarative class, get_db() dependency, check_db_connection() function

6. backend/core/logger.py — Loguru logger configuration with file rotation,
   different log levels for dev vs production

7. backend/models/models.py — Complete SQLAlchemy ORM models for:
   - User (id, email, name, telegram_chat_id, semester, branch, is_active, timestamps)
   - Circular (id, title, url, pdf_path, content, circular_date, is_processed, is_indexed, scraped_at)
   - ExamSchedule (id, circular_id FK, subject, subject_code, semester, exam_date, exam_time, branch, academic_year)
   - Subscription (id, user_id FK, channel enum[email/telegram/firebase], notify_new_circular, notify_exam_update, is_active)
   - Notification (id, user_id FK, title, message, channel, status enum[pending/sent/failed], sent_at, error_message)
   All with proper relationships, __repr__ methods, and indexes.

8. backend/main.py — FastAPI app with:
   - asynccontextmanager lifespan (create tables on dev startup, check DB connection)
   - CORS middleware for localhost:3000 and localhost:5173
   - All 4 routers registered under /api/v1
   - /health endpoint returning app name, env, db status
   - Proper logging

9. backend/api/routes/ — stub files for chat.py, circulars.py, schedule.py, notifications.py
   Each with a router and one placeholder endpoint that returns a helpful message.

10. .gitignore — for Python, venv, .env, data/pdfs, __pycache__, .pytest_cache, logs

Add __init__.py to every Python package directory.
Add docstrings to every file explaining its purpose.
Make sure every file follows Python best practices and is production-ready.
```

---

## ─────────────────────────────────────────
## PHASE 2 — Web Scraper + PDF Pipeline
## Estimated time: 15 hours
## ─────────────────────────────────────────

```
You are a Senior Python Engineer specializing in web scraping and data pipelines.
We are building the VTU Smart Scheduler — an AI chatbot for VTU university students.

The project already has its base structure from Phase 1.
Your task is Phase 2: Build the complete web scraping and PDF processing pipeline.

CONTEXT:
- VTU website: https://vtu.ac.in
- We need to scrape circulars and exam schedule PDFs
- PDFs are saved to ./data/pdfs/
- Extracted text goes to ./data/processed/
- All scraped circular metadata saved to PostgreSQL using our existing models

CREATE AND FULLY IMPLEMENT these files:

1. scraper/vtu_scraper.py
   - Class: VTUScraper
   - Method: scrape_circulars() → returns list of dicts with title, url, date, category
   - Method: scrape_exam_schedules() → returns list of exam schedule links
   - Method: get_new_circulars(existing_urls: list) → returns only circulars not yet in DB
   - Method: detect_changes() → compares current page with last scrape hash
   - Use requests with proper headers (user-agent, timeout=30)
   - Use BeautifulSoup with lxml parser
   - Implement retry logic with tenacity (3 retries, exponential backoff)
   - Handle connection errors, timeouts, and HTTP errors gracefully
   - Log every scrape attempt with loguru
   - Rate limiting: add 2 second delay between requests

2. scraper/pdf_downloader.py
   - Class: PDFDownloader
   - Method: download_pdf(url, filename) → downloads to ./data/pdfs/, returns local path
   - Method: download_batch(pdf_urls: list) → downloads multiple with progress tracking
   - Method: is_already_downloaded(url) → check by URL hash to avoid re-downloading
   - Generate safe filenames from URLs (replace special chars)
   - Show download progress with file size
   - Verify PDF integrity after download (check file not corrupted)
   - Handle 404s, redirects, and timeouts

3. scraper/pdf_parser.py
   - Class: PDFParser
   - Method: extract_text(pdf_path) → primary extraction using pdfplumber
   - Method: extract_with_pypdf2(pdf_path) → fallback method
   - Method: extract_with_ocr(pdf_path) → for scanned PDFs using pytesseract + Pillow
   - Method: parse(pdf_path) → tries all methods in order, returns best result
   - Method: clean_text(raw_text) → removes headers/footers, extra whitespace, special chars
   - Method: extract_tables(pdf_path) → extract tabular data (exam schedules are often tables)
   - Returns structured dict: {text, tables, page_count, extraction_method, confidence_score}
   - Handle corrupted PDFs, password-protected PDFs, image-only PDFs

4. scraper/circular_detector.py
   - Class: CircularDetector
   - Tracks which circulars have been seen using a JSON file at ./data/raw/seen_circulars.json
   - Method: is_new(circular_url) → bool
   - Method: mark_as_seen(circular_url)
   - Method: get_unseen(circulars_list) → filters to only new ones

5. backend/services/circular_service.py
   - Class: CircularService
   - Method: save_circular(db, circular_data) → saves to PostgreSQL Circular model
   - Method: get_all_circulars(db, page, limit) → paginated list
   - Method: get_circular_by_id(db, id)
   - Method: search_circulars(db, query) → text search on title and content
   - Method: mark_as_processed(db, circular_id)
   - Method: get_unprocessed(db) → circulars not yet embedded into vector DB

6. scraper/pipeline.py
   - Class: ScrapingPipeline (orchestrates all the above)
   - Method: run() → full pipeline: scrape → download → parse → save to DB → return summary
   - Method: run_incremental() → only process new circulars since last run
   - Logs pipeline start/end, count of new circulars found, errors
   - Saves pipeline run metadata to ./data/raw/pipeline_log.json

IMPORTANT REQUIREMENTS:
- Every class must have full docstrings
- Every method must have type hints
- Use loguru for all logging (no print statements)
- Handle all edge cases: empty pages, network failures, bad PDFs
- Write it assuming the VTU website may be slow or unreliable
- Add a if __name__ == "__main__": block in pipeline.py to test it standalone
```

---

## ─────────────────────────────────────────
## PHASE 3 — NLP & Data Processing
## Estimated time: 12 hours
## ─────────────────────────────────────────

```
You are a Senior NLP Engineer. We are building the VTU Smart Scheduler AI chatbot.
Phase 1 (project setup) and Phase 2 (scraper) are already complete.

Your task is Phase 3: Build the complete NLP and text processing pipeline.

CONTEXT:
- Raw circular text comes from the PDF parser (Phase 2)
- We need to extract structured data: exam dates, subject names, semester numbers
- We also need to understand user queries: "When is my 5th sem DBMS exam?"
- Language: English (with some Indian English patterns like "as per the schedule")

CREATE AND FULLY IMPLEMENT these files:

1. ai/query_processing/intent_detector.py
   - Class: IntentDetector
   - Detects intent from user query using rule-based + spaCy approach
   - Supported intents:
     GET_EXAM_DATE ("when is my DBMS exam", "what date is physics exam")
     GET_EXAM_SCHEDULE ("show me 5th sem schedule", "all exams for 3rd sem")
     GET_CIRCULAR ("latest circular", "new notifications")
     GET_RESULTS ("results declared", "CIE results")
     GENERAL_QUERY (everything else)
   - Method: detect(query: str) → returns dict {intent, confidence, raw_query}
   - Use keyword matching + spaCy POS tagging for accuracy
   - Handle typos and abbreviations (sem/semester, sub/subject, dept/department)

2. ai/query_processing/entity_extractor.py
   - Class: EntityExtractor
   - Extracts structured entities from user queries using spaCy + regex
   - Entities to extract:
     SEMESTER: "5th sem", "5th semester", "sem 5", "fifth semester" → 5
     SUBJECT: "DBMS", "Data Structures", "ADA", "Maths", "Physics" → normalized name
     BRANCH: "CSE", "ECE", "ISE", "Mechanical", "Civil" → normalized
     YEAR: "2025-26", "first year", "2nd year" → normalized
     DATE: any date patterns
   - Method: extract(query: str) → returns dict {semester, subject, branch, year, date}
   - Build a SUBJECT_ALIASES dict: {"DS": "Data Structures", "ADA": "Analysis and Design of Algorithms",
     "DBMS": "Database Management Systems", "OS": "Operating Systems",
     "CN": "Computer Networks", "SE": "Software Engineering", etc.}
   - Handle partial matches: "data struct" → "Data Structures"

3. ai/query_processing/query_processor.py
   - Class: QueryProcessor (combines intent + entity extraction)
   - Method: process(query: str) → returns complete dict:
     {
       original_query: str,
       intent: str,
       entities: {semester, subject, branch},
       search_query: str,   ← optimized query for vector search
       filters: dict        ← for database filtering
     }
   - Method: build_search_query(intent, entities) → creates clean query for RAG retrieval
   - Example: "when is 5th sem DBMS exam" →
     {intent: "GET_EXAM_DATE", entities: {semester: 5, subject: "DBMS"}, 
      search_query: "DBMS exam date 5th semester"}

4. backend/services/nlp_service.py
   - Loads spaCy model (en_core_web_sm)
   - Wrapper around QueryProcessor for FastAPI use
   - Method: process_query(text: str) → processed query dict
   - Caches spaCy model on startup (don't reload per request)

5. data processing — create backend/services/text_processor.py
   - Class: TextProcessor (processes raw circular text from PDFs)
   - Method: clean(raw_text: str) → removes headers, footers, page numbers, 
     VTU letterhead boilerplate, extra whitespace
   - Method: extract_exam_dates(text: str) → finds all date patterns:
     "DD/MM/YYYY", "DD-MM-YYYY", "DDth Month YYYY", "Month DD, YYYY"
     Returns list of {date_str, parsed_date, context_around_date}
   - Method: extract_subjects(text: str) → finds subject names and codes
     Returns list of {subject_name, subject_code, semester}
   - Method: extract_semester_info(text: str) → detects which semesters the circular applies to
   - Method: structure_exam_schedule(text: str) → for exam schedule PDFs, 
     extracts table data into list of {subject, date, time, semester}
   - Method: process_circular(raw_text: str) → runs full pipeline,
     returns {cleaned_text, exam_dates, subjects, semesters, circular_type}
   - circular_type: "EXAM_SCHEDULE" | "RESULT" | "ADMISSION" | "GENERAL"

6. tests/test_nlp.py
   - Test IntentDetector with 10 sample queries
   - Test EntityExtractor with queries like "5th sem DBMS exam", "3rd semester physics"
   - Test TextProcessor.extract_exam_dates with sample circular text

IMPORTANT:
- Load spaCy model once at module level, not inside methods
- All methods must have type hints and docstrings
- Add confidence scores wherever possible
- Handle queries in all caps, all lowercase, with typos
```

---

## ─────────────────────────────────────────
## PHASE 4 — RAG Pipeline
## Estimated time: 18 hours
## ─────────────────────────────────────────

```
You are a Senior AI Engineer specializing in RAG (Retrieval-Augmented Generation) systems.
We are building the VTU Smart Scheduler. Phases 1, 2, 3 are complete.

Your task is Phase 4: Build the complete production-grade RAG pipeline.

SETUP:
- Embedding model: sentence-transformers all-MiniLM-L6-v2 (384 dimensions, free, fast)
- Vector database: Pinecone (cloud) — index name: "vtu-circulars", dimension: 384
- LLM: Groq with Llama 3 (llama3-8b-8192)
- Framework: LangChain

CREATE AND FULLY IMPLEMENT these files:

1. ai/embeddings/embedding_generator.py
   - Class: EmbeddingGenerator
   - Loads "all-MiniLM-L6-v2" from sentence-transformers on init
   - Method: generate(text: str) → returns list[float] (384 dimensions)
   - Method: generate_batch(texts: list[str]) → returns list[list[float]] (batched for speed)
   - Method: generate_query_embedding(query: str) → same as generate but logs query type
   - Cache the model on first load using @lru_cache or singleton pattern
   - Batch size: 32 for batch processing
   - Log embedding generation time

2. backend/rag_pipeline/chunker.py
   - Class: DocumentChunker
   - Method: chunk(text: str, source: str) → splits text into overlapping chunks
   - Chunk strategy:
     chunk_size = 512 characters
     chunk_overlap = 50 characters
     Split on sentence boundaries (don't cut mid-sentence)
   - Method: chunk_with_metadata(text: str, metadata: dict) → adds metadata to each chunk:
     {text, source_url, circular_title, circular_date, chunk_index, total_chunks}
   - Method: chunk_exam_schedule(structured_data: list) → special chunking for exam tables:
     each row (subject + date) becomes its own chunk for precise retrieval
   - Use LangChain RecursiveCharacterTextSplitter

3. backend/rag_pipeline/embedder.py
   - Class: VectorEmbedder
   - Connects to Pinecone using PINECONE_API_KEY from settings
   - Creates index if it doesn't exist (dimension=384, metric="cosine")
   - Method: embed_and_store(chunks: list[dict]) → embeds all chunks and upserts to Pinecone
     Each vector has metadata: {text, source_url, title, date, semester, chunk_index}
   - Method: embed_circular(circular: Circular model) → full pipeline for one circular
   - Method: delete_circular(circular_url: str) → removes all vectors for a circular
   - Method: get_index_stats() → returns count of vectors, index fullness
   - Batch upsert in groups of 100 (Pinecone limit)
   - Mark circular as is_indexed=True in DB after successful embedding

4. backend/rag_pipeline/retriever.py
   - Class: ContextRetriever
   - Method: retrieve(query: str, top_k: int = 5) → returns top_k most relevant chunks
   - Method: retrieve_with_filters(query: str, filters: dict, top_k: int = 5):
     Supports filters: semester=5, subject="DBMS"
     Uses Pinecone metadata filtering
   - Method: retrieve_exam_date(subject: str, semester: int) → specialized retrieval
     for exam date queries, returns most relevant result
   - Returns list of {text, score, metadata} sorted by relevance score
   - Minimum score threshold: 0.5 (don't return irrelevant results)
   - Log retrieval time and number of results

5. backend/rag_pipeline/generator.py
   - Class: ResponseGenerator
   - Initializes Groq client with GROQ_API_KEY, model=llama3-8b-8192
   - Method: generate(query: str, context_chunks: list[dict]) → returns AI response
   - Builds this prompt structure:
     SYSTEM: "You are VTU Exam Assistant. Answer ONLY based on the provided context.
              If the answer is not in the context, say 'I don't have that information.'
              Be concise. Always mention the exam date clearly if asked."
     CONTEXT: [formatted retrieved chunks]
     USER: [original query]
   - Method: format_context(chunks) → formats retrieved chunks cleanly for the prompt
   - Method: generate_with_citations(query, chunks) → includes source circular reference
   - Handle Groq API errors with tenacity retry (3 retries)
   - Max tokens: 1024, Temperature: 0.1 (factual, not creative)

6. backend/rag_pipeline/rag_chain.py
   - Class: RAGChain (orchestrates the full pipeline)
   - Method: query(user_query: str) → full end-to-end:
     1. Process query through QueryProcessor (Phase 3)
     2. Retrieve relevant chunks from Pinecone
     3. If no relevant chunks found, return "I don't have information about that"
     4. Generate response using Groq
     5. Return {answer, sources, intent, entities, retrieval_count, response_time_ms}
   - Method: index_circular(circular: Circular) → chunks + embeds one circular
   - Method: index_all_pending() → embeds all unindexed circulars from DB
   - Conversational memory: keep last 5 messages in context using LangChain ConversationBufferWindowMemory

7. tests/test_rag.py
   - Test embedding generation (check dimension = 384)
   - Test chunking (verify overlap, check metadata)
   - Test full RAG chain with mock query "When is the 5th sem DBMS exam?"

CRITICAL REQUIREMENTS:
- Never hallucinate — if context doesn't contain the answer, say so explicitly  
- All API keys loaded from settings, never hardcoded
- Log every step: query received, chunks retrieved, response generated, total time
- Handle Pinecone connection failures gracefully
```

---

## ─────────────────────────────────────────
## PHASE 5 — LLM Chatbot Layer
## Estimated time: 14 hours
## ─────────────────────────────────────────

```
You are a Senior AI Engineer. We are building the VTU Smart Scheduler.
Phases 1-4 are complete. The RAG pipeline is working.

Your task is Phase 5: Build the conversational AI chatbot layer on top of the RAG pipeline.

CREATE AND FULLY IMPLEMENT these files:

1. backend/services/chat_service.py
   - Class: ChatService (main chatbot orchestrator)
   - Maintains per-session conversation history (dict keyed by session_id)
   - Method: chat(session_id: str, message: str) → returns ChatResponse
   - Method: get_history(session_id: str) → returns last 10 messages
   - Method: clear_history(session_id: str)
   - Method: create_session() → returns new UUID session_id
   - ChatResponse schema: {answer, intent, entities, sources, session_id, response_time_ms, confidence}
   - Classify confidence: HIGH (score > 0.8), MEDIUM (0.5-0.8), LOW (< 0.5)
   - If confidence LOW, append: "Please verify this with the official VTU website."

2. backend/services/conversation_manager.py
   - Class: ConversationManager
   - Stores conversation history in-memory with TTL of 2 hours
   - Method: add_message(session_id, role, content)
   - Method: get_context(session_id) → last 5 exchanges formatted for LLM
   - Method: cleanup_expired() → removes sessions older than 2 hours
   - Tracks: message count per session, first message time, last message time
   - Method: get_stats() → returns {active_sessions, total_messages_today}

3. backend/api/routes/chat.py — FULL IMPLEMENTATION (replace stub)
   - POST /api/v1/chat
     Request body: {message: str, session_id: str | None}
     Response: {answer, intent, entities, sources, session_id, response_time_ms}
     If no session_id provided, create new one
   - GET /api/v1/chat/history/{session_id}
     Returns conversation history
   - DELETE /api/v1/chat/session/{session_id}
     Clears conversation history
   - Full Pydantic request/response models with validation
   - Message max length: 500 characters
   - Rate limit: 20 requests per minute per session (simple in-memory counter)

4. backend/api/routes/circulars.py — FULL IMPLEMENTATION
   - GET /api/v1/circulars
     Query params: page=1, limit=10, search=str
     Returns paginated list of circulars
   - GET /api/v1/circulars/{id}
     Returns single circular with full content
   - POST /api/v1/circulars/trigger-scrape
     Manually triggers the scraping pipeline (admin use)

5. backend/api/routes/schedule.py — FULL IMPLEMENTATION
   - GET /api/v1/exam-schedule
     Query params: semester=int, branch=str, subject=str
     Returns filtered exam schedule
   - GET /api/v1/exam-schedule/upcoming
     Returns exams in next 7 days

6. backend/api/middleware/error_handler.py
   - Global exception handler for FastAPI
   - Returns consistent error format: {error, message, status_code, timestamp}
   - Different handling for: ValidationError, DatabaseError, APIError, NotFoundError
   - Log all 500 errors with full traceback

7. backend/api/middleware/rate_limit.py
   - Simple in-memory rate limiter middleware
   - 60 requests per minute per IP
   - Returns 429 Too Many Requests with retry-after header

8. Sample conversation tests — create tests/test_chat.py:
   Test these queries end-to-end:
   - "When is my 5th sem DBMS exam?"
   - "Show me all exams for 3rd semester"
   - "What are the latest circulars?"
   - "Hello" (greeting — should respond warmly, not search)
   - "xyz garbage input" (should handle gracefully)

IMPORTANT:
- Session IDs are UUIDs — generate with python uuid module
- All endpoints return proper HTTP status codes
- Use Pydantic models for ALL request and response bodies
- Add OpenAPI descriptions to every endpoint (will show in /docs)
```

---

## ─────────────────────────────────────────
## PHASE 6 — Backend API (Complete)
## Estimated time: 14 hours
## ─────────────────────────────────────────

```
You are a Senior Backend Engineer. We are building the VTU Smart Scheduler.
Phases 1-5 are complete. The chatbot is working. Now we need to harden the API.

Your task is Phase 6: Complete and production-harden the FastAPI backend.

CREATE AND FULLY IMPLEMENT these files:

1. backend/api/routes/notifications.py — FULL IMPLEMENTATION
   - POST /api/v1/subscribe
     Body: {email, name, semester, branch, channels: ["email", "telegram"]}
     Creates User + Subscription in DB
     Returns: {user_id, session_id, message}
   - GET /api/v1/notifications
     Query params: user_id, page, limit
     Returns user's notification history
   - PUT /api/v1/subscribe/{user_id}
     Update subscription preferences
   - DELETE /api/v1/subscribe/{user_id}
     Unsubscribe

2. backend/services/schedule_service.py
   - Class: ScheduleService
   - Method: get_schedule(db, semester, branch, subject) → filtered exam schedule
   - Method: get_upcoming_exams(db, days=7) → exams in next N days
   - Method: save_exam_schedule(db, schedule_data: list) → bulk insert from circular
   - Method: get_by_subject(db, subject_name) → finds exam by subject name (fuzzy match)

3. backend/services/user_service.py
   - Class: UserService
   - Method: create_user(db, email, name, semester, branch) → creates User
   - Method: get_user_by_email(db, email)
   - Method: update_preferences(db, user_id, semester, branch)
   - Method: create_subscription(db, user_id, channels)

4. Pydantic schemas — create backend/api/schemas.py with ALL request/response models:
   - ChatRequest, ChatResponse
   - CircularResponse, CircularListResponse
   - ExamScheduleResponse, ExamScheduleListResponse
   - SubscribeRequest, SubscribeResponse
   - NotificationResponse
   - ErrorResponse
   - HealthResponse

5. backend/core/exceptions.py
   - Custom exception classes:
     VTUException (base), CircularNotFoundError, UserNotFoundError,
     ScrapingError, EmbeddingError, LLMError, DatabaseError
   - Each with status_code, message, and detail

6. Update backend/main.py:
   - Add startup event that checks Pinecone connection
   - Add startup event that checks Groq API key is valid
   - Add request logging middleware (log method, path, status, response time)
   - Add /health endpoint that checks DB, Pinecone, and Groq connectivity
   - Return proper 503 if any dependency is down

7. tests/test_api.py — integration tests using httpx:
   - Test POST /chat with valid message
   - Test GET /circulars returns list
   - Test GET /exam-schedule with semester filter
   - Test POST /subscribe with valid data
   - Test /health returns 200

REQUIREMENTS:
- All endpoints documented with OpenAPI descriptions
- Input validation on all fields (email format, semester 1-8, etc.)
- Consistent response format across all endpoints
- Database queries use pagination (never load all rows)
```

---

## ─────────────────────────────────────────
## PHASE 7 — Database Layer
## Estimated time: 10 hours
## ─────────────────────────────────────────

```
You are a Senior Database Engineer. We are building the VTU Smart Scheduler.
The models are defined. Now we need migrations, indexes, and query optimization.

Your task is Phase 7: Complete database setup with Alembic migrations and optimized queries.

CREATE AND FULLY IMPLEMENT:

1. Set up Alembic migrations:
   - Run: alembic init alembic
   - Configure alembic/env.py to use our DATABASE_URL from settings
   - Configure alembic/env.py to use our Base metadata from models
   - Create first migration: alembic/versions/001_initial_schema.py
     This migration creates all 5 tables with proper constraints and indexes

2. Add database indexes to models (update backend/models/models.py):
   - circulars: index on (scraped_at DESC) for latest-first queries
   - circulars: index on (is_indexed, is_processed) for pipeline queries
   - exam_schedules: composite index on (semester, subject) for common filter
   - exam_schedules: index on (exam_date) for upcoming exam queries
   - notifications: index on (user_id, status) for user notification queries

3. Create backend/core/database_utils.py:
   - Function: paginate(query, page: int, limit: int) → adds OFFSET/LIMIT
   - Function: get_or_create(db, model, **kwargs) → get existing or create new
   - Function: bulk_insert(db, model, data: list[dict]) → efficient bulk insert
   - Context manager: transaction(db) → wraps operations in try/commit/rollback

4. Update all service files to use optimized queries:
   - CircularService: use select() with specific columns (not SELECT *)
   - ScheduleService: use .filter() chaining, add .order_by(exam_date.asc())
   - All list queries: add pagination

5. Create a database seed script: scripts/seed_db.py
   - Creates 3 sample users
   - Creates 5 sample circulars with content
   - Creates sample exam schedule for 5th semester CSE
   - Creates sample subscriptions
   - Run with: python scripts/seed_db.py

6. Create scripts/reset_db.py:
   - Drops all tables and recreates them (dev only)
   - Confirm prompt before running

REQUIREMENTS:
- All migrations must be reversible (implement downgrade() in each migration)
- Never use raw SQL strings — always use SQLAlchemy ORM
- Add database connection pool monitoring logs
```

---

## ─────────────────────────────────────────
## PHASE 8 — Notification System
## Estimated time: 12 hours
## ─────────────────────────────────────────

```
You are a Senior Backend Engineer specializing in event-driven systems.
We are building the VTU Smart Scheduler notification system.

Your task is Phase 8: Build the complete notification pipeline.

CHANNELS TO IMPLEMENT: Email (SMTP) + Telegram Bot

CREATE AND FULLY IMPLEMENT:

1. notifications/email_notifier.py
   - Class: EmailNotifier
   - Uses smtplib with SMTP_SSL for Gmail
   - Loads SMTP config from settings
   - Method: send(to: str, subject: str, body: str, html: str = None)
   - Method: send_new_circular_alert(user, circular) → formatted email
   - Method: send_exam_reminder(user, exam_schedule) → exam reminder email
   - HTML email templates (inline in the method, clean and mobile-friendly)
   - Retry 3 times on failure
   - Log every send attempt with success/failure

2. notifications/telegram_notifier.py
   - Class: TelegramNotifier
   - Uses python-telegram-bot library
   - Method: send_message(chat_id: str, message: str)
   - Method: send_new_circular_alert(chat_id, circular)
   - Method: send_exam_reminder(chat_id, exam_schedule)
   - Format messages with Telegram markdown (bold dates, etc.)
   - Handle invalid chat_id, blocked bot, network errors

3. notifications/notification_manager.py
   - Class: NotificationManager (orchestrates all channels)
   - Method: notify_new_circular(circular: Circular, db)
     Gets all subscribed users → sends via their preferred channels
     Creates Notification records in DB for tracking
   - Method: notify_exam_update(exam: ExamSchedule, db)
   - Method: send_notification(user, notification_data, channel)
   - Method: retry_failed(db) → retries all FAILED notifications
   - Method: get_pending(db) → returns all PENDING notifications
   - Mark notifications SENT or FAILED in DB after attempt

4. backend/api/routes/notifications.py — add:
   - POST /api/v1/notifications/test
     Sends a test notification to verify setup
     Body: {user_id, channel}

5. The full notification workflow — implement in notifications/notification_manager.py:
   Scraper detects new circular
   → Save circular to DB
   → Process and chunk text
   → Embed into Pinecone
   → Get users subscribed to notify_new_circular
   → Send email to email subscribers
   → Send Telegram message to Telegram subscribers
   → Mark notifications as SENT in DB

REQUIREMENTS:
- Never expose email passwords in logs
- All notifications stored in DB before sending (for audit trail)
- Async sending — don't block the main thread
- Test mode: if APP_ENV=development, log the notification instead of sending it
```

---

## ─────────────────────────────────────────
## PHASE 9 — Frontend UI (React)
## Estimated time: 18 hours
## ─────────────────────────────────────────

```
You are a Senior Frontend Engineer specializing in React and Tailwind CSS.
We are building the VTU Smart Scheduler frontend.

Your task is Phase 9: Build the complete React chat interface.

SETUP:
- Use Vite + React + TypeScript
- Tailwind CSS for styling
- No UI component library (build custom components)
- API base URL: http://localhost:8000/api/v1

CREATE the full frontend application in the frontend/ folder:

Run these commands first:
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install axios tailwindcss @tailwindcss/vite

Then create these files:

1. src/types/index.ts — TypeScript interfaces:
   - ChatMessage {id, role: "user"|"assistant", content, timestamp, sources?, intent?}
   - ChatSession {session_id, messages, created_at}
   - Circular {id, title, url, circular_date, is_processed}
   - ExamSchedule {id, subject, semester, exam_date, exam_time, branch}
   - ApiResponse<T> {data, error, status}

2. src/api/client.ts — Axios instance:
   - baseURL from env
   - Request/response interceptors for error handling
   - Helper functions: chatApi.sendMessage(), circularApi.getAll(), scheduleApi.getSchedule()

3. src/hooks/useChat.ts — Custom React hook:
   - State: messages[], isLoading, sessionId, error
   - sendMessage(text: string) → calls API, adds to messages
   - clearChat() → clears history
   - Persists sessionId in localStorage

4. src/components/ChatWindow.tsx — Main chat UI:
   - Full height layout with scrollable message list
   - Auto-scroll to latest message
   - Shows typing indicator while waiting for response
   - Empty state: "Ask me about your VTU exam schedule!"

5. src/components/ChatMessage.tsx — Individual message bubble:
   - User messages: right-aligned, blue background
   - Assistant messages: left-aligned, white background with border
   - Show timestamp
   - If message has sources: show collapsible "Sources" section
   - If confidence is LOW: show warning banner "Please verify with VTU website"
   - Markdown rendering for assistant messages (bold dates, etc.)

6. src/components/ChatInput.tsx:
   - Textarea that grows with content (max 4 lines)
   - Send button + Enter to send (Shift+Enter for newline)
   - Character counter (500 max)
   - Disabled state while loading
   - Suggestion chips below input:
     "When is my DBMS exam?" | "5th sem schedule" | "Latest circulars"

7. src/components/Sidebar.tsx:
   - VTU Smart Scheduler logo/title
   - Navigation: Chat | Circulars | Exam Schedule
   - Subscribe button (opens modal)
   - Recent searches (last 5 queries from localStorage)
   - Collapsible on mobile

8. src/pages/CircularsPage.tsx:
   - Table/card list of all circulars
   - Search bar (filters by title)
   - Pagination
   - Click to view circular details

9. src/pages/SchedulePage.tsx:
   - Filter by semester (dropdown 1-8)
   - Filter by branch (CSE, ECE, ISE, etc.)
   - Calendar-style or table view of exam dates
   - Highlight exams in next 7 days

10. src/pages/SubscribePage.tsx (modal):
    - Form: name, email, semester, branch
    - Channel selection: Email checkbox, Telegram checkbox
    - Submit → POST /subscribe

DESIGN REQUIREMENTS:
- Clean, minimal, modern design
- Primary color: Blue (#2563EB)
- Mobile responsive (works on phone)
- Dark mode support using Tailwind dark: classes
- Loading skeletons (not spinners) while fetching data
- Error states with retry button
- No external UI libraries (pure Tailwind)
```

---

## ─────────────────────────────────────────
## PHASE 10 — Automation & Scheduler
## Estimated time: 7 hours
## ─────────────────────────────────────────

```
You are a Senior Backend Engineer. We are building the VTU Smart Scheduler.
All previous phases are complete. Now we automate everything.

Your task is Phase 10: Build the automated monitoring and scheduling system.

CREATE AND FULLY IMPLEMENT:

1. backend/services/scheduler_service.py
   - Uses APScheduler (AsyncIOScheduler)
   - Jobs to schedule:
     a) scrape_and_process() — every 6 hours (SCRAPER_INTERVAL_HOURS from settings)
        Runs: ScrapingPipeline.run_incremental() → embeds new circulars → notifies users
     b) retry_failed_notifications() — every 30 minutes
        Runs: NotificationManager.retry_failed()
     c) cleanup_old_sessions() — every 2 hours
        Runs: ConversationManager.cleanup_expired()
     d) health_check_log() — every 1 hour
        Logs: DB connection status, Pinecone stats, memory usage
   - Method: start() → starts the scheduler (called in FastAPI lifespan)
   - Method: stop() → graceful shutdown
   - Method: run_now(job_name: str) → triggers a job immediately (for testing/admin)
   - Method: get_job_status() → returns list of jobs with last_run, next_run, status

2. Update backend/main.py lifespan:
   - On startup: start the scheduler
   - On shutdown: stop the scheduler gracefully

3. Add admin endpoints in backend/api/routes/admin.py:
   - POST /api/v1/admin/trigger-scrape — runs scraping pipeline now
   - POST /api/v1/admin/reindex-all — re-embeds all circulars into Pinecone
   - GET /api/v1/admin/scheduler-status — returns job statuses
   - POST /api/v1/admin/retry-notifications — retries failed notifications
   - These endpoints are admin-only (check X-Admin-Key header against settings.secret_key)

4. Create scripts/manual_scrape.py:
   - Standalone script to run scraping pipeline manually
   - Usage: python scripts/manual_scrape.py
   - Shows progress and summary at the end

5. Create scripts/reindex_circulars.py:
   - Reprocesses and re-embeds all circulars in DB
   - Useful when changing embedding model or chunk strategy
   - Shows progress bar

REQUIREMENTS:
- Jobs must not overlap (use max_instances=1 in APScheduler)
- Log job start/end with duration
- If a job fails, log the error but don't crash the app
- Scheduler state should survive API restarts (use SQLAlchemy job store if possible)
```

---

## ─────────────────────────────────────────
## PHASE 11 — Deployment & Docker
## Estimated time: 12 hours
## ─────────────────────────────────────────

```
You are a Senior DevOps Engineer. We are deploying the VTU Smart Scheduler.

Your task is Phase 11: Complete Docker setup and deployment configuration.

CREATE AND FULLY IMPLEMENT:

1. Dockerfile for backend:
   - Base: python:3.11-slim
   - Install system deps: tesseract-ocr, libpq-dev, build-essential
   - Copy and install requirements.txt
   - Download spaCy model during build
   - Non-root user for security
   - Expose port 8000
   - CMD: uvicorn backend.main:app --host 0.0.0.0 --port 8000

2. Dockerfile for frontend (frontend/Dockerfile):
   - Multi-stage build:
     Stage 1 (builder): node:20-alpine, npm install, npm run build
     Stage 2 (serve): nginx:alpine, copy dist from stage 1
   - nginx.conf: serve React app, proxy /api/ to backend

3. docker-compose.yml (production, update existing):
   - Services: backend, frontend, postgres, redis
   - Backend depends on postgres health check
   - Environment variables from .env file
   - Named volumes for postgres_data, redis_data
   - Network: vtu-network (all services on same network)
   - Restart policy: unless-stopped

4. docker-compose.dev.yml (for development):
   - Backend with volume mount for hot reload
   - Frontend with Vite dev server on port 5173
   - Same postgres and redis as prod

5. .env.production (template):
   - All production env vars with comments
   - APP_ENV=production
   - Secure SECRET_KEY note

6. nginx.conf:
   - Serve frontend on port 80
   - Proxy /api/ requests to backend:8000
   - Gzip compression
   - Cache static assets

7. Deployment guides — create docs/:
   - docs/deploy-render.md: Step-by-step Render.com deployment for backend
   - docs/deploy-vercel.md: Step-by-step Vercel deployment for frontend
   - docs/setup-pinecone.md: How to create Pinecone index
   - docs/setup-groq.md: How to get Groq API key

8. GitHub Actions CI — create .github/workflows/test.yml:
   - Trigger: push to main, pull request
   - Jobs: lint (flake8), test (pytest), build-check
   - Use postgres service container for tests

REQUIREMENTS:
- Docker images must build successfully
- No secrets in Dockerfiles or docker-compose.yml (use .env)
- Backend image should be under 500MB
- Include health check endpoints in Docker config
```

---

## ─────────────────────────────────────────
## PHASE 12 — Testing, QA & Documentation
## Estimated time: 10 hours
## ─────────────────────────────────────────

```
You are a Senior QA Engineer. The VTU Smart Scheduler is feature-complete.

Your task is Phase 12: Complete test suite, QA, and final documentation.

CREATE AND FULLY IMPLEMENT:

1. tests/test_scraper.py — Unit tests:
   - Mock requests to test VTUScraper without hitting real VTU website
   - Test PDFParser with a sample PDF text string
   - Test CircularDetector tracks seen URLs correctly
   - Test retry logic triggers on connection errors

2. tests/test_nlp.py — NLP tests:
   - Test IntentDetector with 15 diverse queries
   - Test EntityExtractor extracts semester, subject correctly
   - Test TextProcessor.extract_exam_dates with date patterns
   - Test edge cases: empty string, very long text, no entities found

3. tests/test_rag.py — RAG pipeline tests:
   - Test embedding dimension = 384
   - Test chunker produces overlapping chunks
   - Test retriever returns results above score threshold
   - Mock Pinecone and Groq for unit tests

4. tests/test_api.py — Integration tests using httpx.AsyncClient:
   - Test all endpoints return correct status codes
   - Test chat endpoint with real query (mocked RAG)
   - Test subscription flow end-to-end
   - Test error handling (invalid input, missing fields)

5. conftest.py — pytest fixtures:
   - test database (SQLite in-memory for tests)
   - sample Circular, User, ExamSchedule objects
   - mock settings with test API keys
   - FastAPI test client

6. Final README.md (complete rewrite):
   - Project description and demo GIF placeholder
   - Full architecture diagram (ASCII art)
   - Prerequisites (Python 3.11, Docker, Groq key, Pinecone key)
   - Step-by-step local setup for Windows
   - API documentation summary (all endpoints)
   - Environment variables reference table
   - How the RAG pipeline works (simple explanation)
   - Deployment guide link
   - Troubleshooting section (common errors + fixes)
   - Contributing guide
   - License: MIT

7. docs/architecture.md:
   - Full system architecture explanation
   - Data flow diagrams (ASCII)
   - Component descriptions
   - Technology choices and why

8. Run final checks:
   - Ensure all imports resolve
   - Ensure all __init__.py files exist
   - Ensure no hardcoded API keys anywhere (grep for them)
   - Verify docker-compose up runs without errors
   - Run full test suite: pytest tests/ -v

REQUIREMENTS:
- At least 80% of code paths covered by tests
- All tests must pass
- README must be clear enough for a new developer to set up the project in 30 minutes
```
