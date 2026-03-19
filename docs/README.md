# VTU Smart Scheduler

AI-powered chatbot for querying VTU exam schedules and circulars using natural language.

## Stack

| Layer | Technology |
|---|---|
| LLM | Groq (Llama 3) |
| Vector DB | Pinecone |
| Backend | FastAPI |
| Database | PostgreSQL |
| NLP | spaCy + LangChain |
| Scraping | BeautifulSoup + pdfplumber |

## Quick Start (Windows)

### Prerequisites
- Python 3.11+
- Docker Desktop
- Git

### 1. Clone and setup

```bat
git clone <your-repo-url>
cd vtu-smart-scheduler
setup.bat
```

### 2. Add API keys

Edit `.env`:
```
GROQ_API_KEY=your_key_from_console.groq.com
PINECONE_API_KEY=your_key_from_app.pinecone.io
```

### 3. Run the backend

```bat
venv\Scripts\activate
python -m backend.main
```

### 4. Open API docs

Visit: http://localhost:8000/docs

## Project Structure

```
vtu-smart-scheduler/
├── backend/
│   ├── api/routes/        # FastAPI route handlers
│   ├── core/              # Config, database, settings
│   ├── models/            # SQLAlchemy ORM models
│   ├── rag_pipeline/      # RAG: chunker, embedder, retriever
│   ├── services/          # Business logic layer
│   └── main.py            # App entry point
├── ai/
│   ├── embeddings/        # Embedding generation
│   └── query_processing/  # Intent detection, entity extraction
├── scraper/               # VTU website scraper + PDF parser
├── notifications/         # Email, Telegram notifiers
├── frontend/              # React + Tailwind UI
├── data/                  # PDFs, raw and processed data
├── tests/                 # pytest test suite
├── docker-compose.yml     # PostgreSQL + Redis
├── requirements.txt       # Python dependencies
└── setup.bat              # Windows one-click setup
```

## Development Phases

| Phase | Component | Status |
|---|---|---|
| 1 | Project setup | Done |
| 2 | Scraper + PDF pipeline | Next |
| 3 | NLP processing | Pending |
| 4 | RAG pipeline | Pending |
| 5 | LLM chatbot | Pending |
| 6 | FastAPI backend | Pending |
| 7 | Database models | Pending |
| 8 | Notifications | Pending |
| 9 | Frontend UI | Pending |
| 10 | Automation | Pending |
| 11 | Deployment | Pending |
| 12 | Testing & docs | Pending |
