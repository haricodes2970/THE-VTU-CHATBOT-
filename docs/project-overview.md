# VTU Smart Scheduler — Project Overview

A complete Q&A reference for understanding what this project is, how it works, and how to use it.

---

## What is this?

**VTU Smart Scheduler** is an AI-powered chatbot and notification system for students of **Visvesvaraya Technological University (VTU)**. It automatically scrapes official VTU circulars (exam timetables, fee notifications, PhD regulations, etc.), indexes them into a vector database, and lets students ask natural-language questions and get accurate, sourced answers instantly.

Instead of manually checking vtu.ac.in every day, students can just ask:
- "When is the 5th semester exam?"
- "What are the PhD submission requirements?"
- "Any new circulars about exam fees?"

---

## What problem does it solve?

VTU publishes important circulars as PDFs buried deep in their website. Students miss exam dates, fee deadlines, and regulation changes because:
1. There's no central notification system
2. PDFs are not searchable
3. Information is scattered across multiple pages

This bot solves all three: it scrapes, parses, indexes, and makes every circular instantly queryable.

---

## How does it work? (High-Level Flow)

```
VTU Website (vtu.ac.in)
        ↓
   Web Scraper (BeautifulSoup)
        ↓
   PDF Downloader + Parser (pdfplumber / PyPDF2 / Tesseract OCR)
        ↓
   Text Chunker → Embedding Generator (sentence-transformers)
        ↓
   Pinecone Vector Database (stored + indexed)
        ↓  ← User asks a question
   Query Embedder → Pinecone Similarity Search → Top-K chunks
        ↓
   Groq LLM (Llama 3.1) → Generates answer with source citations
        ↓
   React Chat UI (user sees answer)
```

Additionally:
- APScheduler runs the scraper every 6 hours automatically
- Email/Telegram notifications are sent when new circulars are published
- PostgreSQL stores circular metadata, users, and notification preferences

---

## What technologies are used?

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | REST API framework — handles all HTTP endpoints |
| **SQLAlchemy + PostgreSQL** | Database ORM + relational database for metadata |
| **Pydantic / pydantic-settings** | Data validation + environment config via `.env` |
| **APScheduler** | Background job scheduler (scrape every 6h, etc.) |
| **Uvicorn** | ASGI server that runs the FastAPI app |

### AI / RAG Pipeline
| Technology | Purpose |
|---|---|
| **sentence-transformers** (`all-MiniLM-L6-v2`) | Converts text into 384-dimensional vectors (embeddings) |
| **Pinecone** | Cloud vector database — stores and searches embeddings |
| **Groq API** (`llama-3.1-8b-instant`) | LLM that generates human-readable answers from context |

### Scraper
| Technology | Purpose |
|---|---|
| **BeautifulSoup4** | Parses VTU HTML pages to find circular links |
| **requests** | Downloads PDFs from VTU |
| **pdfplumber** | Primary PDF text + table extractor |
| **PyPDF2** | Fallback PDF extractor |
| **pytesseract + Pillow** | OCR for scanned/image-only PDFs |

### Frontend
| Technology | Purpose |
|---|---|
| **React + TypeScript** | UI framework |
| **Vite** | Fast dev build tool |
| **Tailwind CSS** | Utility-first styling |
| **Axios** | HTTP client for API calls |

### Infrastructure
| Technology | Purpose |
|---|---|
| **Docker + Docker Compose** | Containers for postgres, redis, backend, frontend |
| **Redis** | Caching layer |
| **Loguru** | Structured logging throughout the app |
| **Tenacity** | Auto-retry on Groq API calls |

---

## What is RAG?

**RAG = Retrieval-Augmented Generation**

Instead of asking the LLM to memorize VTU data (impossible), RAG:
1. **Retrieves** the most relevant document chunks from Pinecone for your question
2. **Augments** the LLM prompt with those chunks as context
3. **Generates** an answer that is grounded in the actual source documents

This means:
- Answers are accurate (the LLM can only use what was retrieved)
- Answers include source citations (which circular the info came from)
- No hallucinations about VTU-specific data
- Knowledge can be updated just by re-scraping — no model retraining needed

---

## What is Pinecone and why use it?

**Pinecone** is a managed vector database. Unlike a regular SQL database that searches by exact matches, Pinecone searches by **semantic similarity** — it finds text that *means* the same thing as your query, even if the words are different.

Example: "When is the final exam?" will match chunks containing "End Semester Examination schedule" because their vector representations are close in 384-dimensional space.

**Index details:**
- Name: `vtu-circulars`
- Dimension: 384 (matches `all-MiniLM-L6-v2` output)
- Metric: cosine similarity
- Region: AWS us-east-1

---

## What is Groq and why use it instead of OpenAI?

**Groq** is an LLM inference API that runs models on custom LPU (Language Processing Unit) hardware — it's **dramatically faster** than OpenAI for inference (often 10–20x). For a chatbot where response speed matters, Groq is ideal.

Model used: `llama-3.1-8b-instant` — Meta's Llama 3.1 8B parameter model, good balance of speed and quality.

---

## How is data scraped and indexed?

1. **Scraper** hits `https://vtu.ac.in/circulars` and finds all PDF links
2. Each PDF is downloaded to `data/pdfs/`
3. **PDF Parser** tries extraction in order: pdfplumber → PyPDF2 → Tesseract OCR
4. Extracted text is saved to PostgreSQL (`circulars` table)
5. **Chunker** splits text into ~500-character overlapping chunks
6. **Embedding Generator** converts each chunk to a 384-dim vector
7. Chunks + vectors are upserted into Pinecone with metadata (title, date, URL)

---

## How is a question answered?

1. User types a question in the React chat UI
2. Frontend sends `POST /api/v1/chat` with the question
3. Backend embeds the question using the same `all-MiniLM-L6-v2` model
4. Pinecone is queried for the top 5 most similar chunks (score ≥ 0.2)
5. Retrieved chunks are formatted as context
6. Groq LLM receives: system prompt + context + user question
7. LLM returns a grounded answer with source references
8. Answer is streamed back to the React UI

---

## How to run this locally

### Prerequisites
- Python 3.12 (not 3.13 or 3.14)
- Node.js 18+
- Docker Desktop (running)
- Groq API key (free at console.groq.com)
- Pinecone API key (free tier at pinecone.io)

### Steps

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd THE-VTU-BOT

# 2. Start databases
docker-compose up -d postgres redis

# 3. Set up Python env (must be 3.12)
py -3.12 -m venv venv
venv\Scripts\activate        # Windows
source venv/Scripts/activate # Mac/Linux

# 4. Install dependencies
pip install -r requirements.txt
pip install "pydantic[email]"

# 5. Configure environment
# Edit .env — fill in GROQ_API_KEY and PINECONE_API_KEY

# 6. Start backend
python -m backend.main

# 7. Trigger initial scrape (new terminal)
curl -X POST http://localhost:8000/api/v1/scraper/trigger

# 8. Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and start chatting.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/chat` | Ask a question, get an AI answer |
| GET | `/api/v1/circulars` | List all scraped circulars |
| POST | `/api/v1/scraper/trigger` | Manually trigger a scrape |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/admin/stats` | Admin stats (circular count, index size, etc.) |
| GET | `/docs` | Interactive API docs (Swagger UI) |

---

## Project Structure

```
THE-VTU-BOT/
├── backend/
│   ├── core/           # config, database connection, middleware
│   ├── api/            # FastAPI route handlers
│   ├── models/         # SQLAlchemy DB models
│   ├── rag_pipeline/   # retriever.py + generator.py
│   └── notifications/  # email + telegram senders
├── scraper/
│   ├── vtu_scraper.py  # BeautifulSoup scraper
│   ├── pdf_parser.py   # pdfplumber/PyPDF2/OCR
│   └── scheduler.py    # APScheduler jobs
├── ai/
│   └── embeddings/     # EmbeddingGenerator (sentence-transformers)
├── frontend/           # React + TypeScript + Vite
├── data/
│   ├── pdfs/           # downloaded PDFs (gitignored)
│   └── raw/            # seen_circulars.json (tracking)
├── docs/               # all documentation
├── docker-compose.yml
├── requirements.txt
└── .env                # secrets (gitignored)
```

---

## What can the bot answer?

**It can answer** anything present in scraped VTU circulars:
- Exam timetables and dates
- PhD/research regulations
- Fee structures
- College affiliation rules
- Mandatory disclosures
- New notifications as they are published

**It cannot answer:**
- Questions not covered by any scraped circular
- Real-time results or marks (not published as circulars)
- Information from circulars it failed to extract (image-only PDFs with OCR errors)

When it doesn't know, it says: *"I don't have that information in my knowledge base. Please check the official VTU website at vtu.ac.in"*

---

## How is knowledge updated?

Automatically — APScheduler runs the scraper every 6 hours. New circulars are:
1. Detected (URL not in `seen_circulars.json`)
2. Downloaded and parsed
3. Chunked and indexed into Pinecone
4. Notification sent to subscribed users

No manual action needed once the system is deployed.

---

## Security notes

- `SECRET_KEY` in `.env` is used for JWT token signing — generate a fresh one for production
- `.env` is gitignored — never commit it
- Database credentials in `.env` should be changed from defaults for production
- Groq and Pinecone API keys are scoped — rotate them if exposed
