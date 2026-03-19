# VTU Smart Scheduler

> AI-powered chatbot for querying VTU exam schedules and circulars using natural language.

---

## What It Does

Students ask questions in plain English:
- *"When is my 5th sem DBMS exam?"*
- *"Show me all exams for 3rd semester CSE"*
- *"Latest VTU circulars"*

The bot scrapes VTU circulars, parses PDFs, embeds them into a vector database, and uses Llama 3 (via Groq) to answer questions accurately.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER (Browser)                       │
│                React + Tailwind (Vite)                      │
└────────────────────────┬────────────────────────────────────┘
                         │  HTTP
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend (:8000)                    │
│  /api/v1/chat  /circulars  /exam-schedule  /subscribe       │
│  RateLimitMiddleware · ErrorHandler · CORS                   │
└──────┬─────────────────┬──────────────────┬─────────────────┘
       │                 │                  │
┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼───────┐
│ QueryProc.  │  │  RAG Chain   │  │ Scraper + PDF │
│ IntentDetect│  │ Chunker      │  │ VTUScraper    │
│ EntityExtract│  │ Embedder    │  │ PDFParser     │
└─────────────┘  │ Retriever   │  │ Pipeline      │
                 │ Generator   │  └───────────────┘
                 └──────┬──────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
┌────────▼────────┐          ┌─────────▼────────┐
│    Pinecone     │          │   Groq (Llama 3)  │
│  Vector DB      │          │   LLM API         │
│  (384-dim)      │          │                   │
└─────────────────┘          └──────────────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  ← Users, Circulars, ExamSchedules,
│   (Docker)      │    Subscriptions, Notifications
└─────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq (Llama 3 8B) — free & fast |
| Vector DB | Pinecone (cloud, free tier) |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (384-dim) |
| Backend | FastAPI + SQLAlchemy |
| Database | PostgreSQL 16 (Docker) |
| NLP | spaCy en_core_web_sm + custom rules |
| Scraping | BeautifulSoup + pdfplumber |
| Frontend | React + TypeScript + Tailwind CSS (Vite) |
| Scheduler | APScheduler |
| Notifications | SMTP (Gmail) + Telegram |

---

## Prerequisites (Windows)

- **Python 3.11+** — [python.org](https://python.org)
- **Docker Desktop** — [docker.com](https://docker.com)
- **Node.js 20+** — [nodejs.org](https://nodejs.org)
- **Git** — [git-scm.com](https://git-scm.com)
- **Groq API Key** — free at [console.groq.com](https://console.groq.com)
- **Pinecone API Key** — free at [app.pinecone.io](https://app.pinecone.io)

---

## Local Setup (Windows)

### 1. Clone the repository
```bash
git clone https://github.com/haricodes2970/THE-VTU-CHATBOT-.git
cd THE-VTU-CHATBOT-
```

### 2. Create Python virtual environment
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Configure environment
```bash
copy .env.example .env
```
Edit `.env` and fill in:
```
GROQ_API_KEY=your_groq_key_here
PINECONE_API_KEY=your_pinecone_key_here
```

### 4. Start databases
```bash
docker-compose up -d postgres redis
```
Wait ~10 seconds for PostgreSQL to be ready.

### 5. Run the backend
```bash
python -m backend.main
```
Visit **http://localhost:8000/docs** — you should see the Swagger UI.

### 6. (Optional) Seed sample data
```bash
python scripts/seed_db.py
```

### 7. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
Visit **http://localhost:5173**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send a message, get AI response |
| GET | `/api/v1/chat/history/{session_id}` | Get conversation history |
| DELETE | `/api/v1/chat/session/{session_id}` | Clear session |
| GET | `/api/v1/circulars` | List circulars (paginated, searchable) |
| GET | `/api/v1/circulars/{id}` | Get single circular |
| GET | `/api/v1/exam-schedule` | Filter exam schedule |
| GET | `/api/v1/exam-schedule/upcoming` | Exams in next 7 days |
| POST | `/api/v1/subscribe` | Subscribe to notifications |
| GET | `/health` | Health check |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq LLM API key | ✅ |
| `PINECONE_API_KEY` | Pinecone vector DB key | ✅ |
| `DATABASE_URL` | PostgreSQL connection URL | ✅ |
| `SECRET_KEY` | App secret (admin endpoints) | ✅ |
| `SMTP_USER` | Gmail address for email alerts | Optional |
| `SMTP_PASSWORD` | Gmail App Password | Optional |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Optional |
| `SCRAPER_INTERVAL_HOURS` | How often to scrape VTU | Default: 6 |

---

## How the RAG Pipeline Works

```
User Query
    ↓
QueryProcessor (IntentDetector + EntityExtractor)
    ↓
search_query = "DBMS exam date 5th semester"
    ↓
EmbeddingGenerator → 384-dim vector
    ↓
Pinecone.query(vector, top_k=5, filter={semester: 5})
    ↓
Retrieved chunks (text snippets from VTU PDFs)
    ↓
Groq Llama3: "Answer based ONLY on the context: ..."
    ↓
Answer + Sources + Confidence score
```

---

## Running Tests

```bash
# All tests (requires DB running)
pytest tests/ -v

# Skip tests requiring Pinecone/Groq
pytest tests/ -v --ignore=tests/test_rag.py

# Specific module
pytest tests/test_nlp.py -v
```

---

## Docker (Production)

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run migrations
docker-compose exec backend alembic upgrade head
```

---

## Deployment

- **Backend → Render.com**: see [docs/deploy-render.md](docs/deploy-render.md)
- **Frontend → Vercel**: see [docs/deploy-vercel.md](docs/deploy-vercel.md)
- **Pinecone setup**: see [docs/setup-pinecone.md](docs/setup-pinecone.md)
- **Groq key**: see [docs/setup-groq.md](docs/setup-groq.md)

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Database connection failed` | Run `docker-compose up -d postgres` |
| `spaCy model not found` | Run `python -m spacy download en_core_web_sm` |
| `Pinecone connection error` | Check `PINECONE_API_KEY` in `.env` |
| `Groq API error` | Check `GROQ_API_KEY` in `.env` |
| `Port 8000 already in use` | Change `APP_PORT=8001` in `.env` |
| Frontend `VITE_API_URL` not found | Check `frontend/.env.local` has `VITE_API_URL=http://localhost:8000/api/v1` |

---

## Project Structure

```
THE-VTU-BOT/
├── backend/
│   ├── api/routes/          # chat, circulars, schedule, notifications, admin
│   ├── api/middleware/       # rate_limit, error_handler
│   ├── core/                 # config, database, exceptions, logger
│   ├── models/               # SQLAlchemy ORM models
│   ├── rag_pipeline/         # chunker, embedder, retriever, generator, rag_chain
│   ├── services/             # chat, circular, schedule, user, nlp, scheduler
│   └── main.py
├── ai/
│   ├── embeddings/           # EmbeddingGenerator (all-MiniLM-L6-v2)
│   └── query_processing/     # IntentDetector, EntityExtractor, QueryProcessor
├── scraper/                  # VTUScraper, PDFDownloader, PDFParser, Pipeline
├── notifications/            # EmailNotifier, TelegramNotifier, NotificationManager
├── frontend/                 # React + TypeScript + Tailwind
├── alembic/                  # Database migrations
├── scripts/                  # seed_db, reset_db, manual_scrape, reindex
├── tests/                    # pytest test suite
├── docs/                     # Deployment guides
├── docker-compose.yml        # Production: postgres, redis, backend, frontend
├── docker-compose.dev.yml    # Development with hot reload
├── Dockerfile                # Backend image
└── .env.example              # Environment variable template
```

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "feat: add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

Built with ❤️ for VTU students
