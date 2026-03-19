# Debugging Lessons Learned — VTU Smart Scheduler

A personal reference of every real problem hit during setup, what caused it, and how to never repeat it.

---

## 1. Wrong Python Version (3.14 → 3.12)

**What happened:** `langchain-pinecone` and `Pillow` failed to build because there were no wheels for Python 3.14.

**Rule:** Always use **Python 3.12** for this project. Python 3.14 is too new for the AI/ML package ecosystem.

**How to check:**
```bash
python --version   # must say 3.12.x
py -3.12 --version
```

**Fix if wrong:**
```bash
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Wrong Virtual Environment Activated

**What happened:** `No module named 'fastapi'` even after installing it — because the old `.venv` was activated instead of the correct `venv`.

**Rule:** This project uses `venv/` (not `.venv/`). Always verify which env is active.

**How to check:**
```bash
# PowerShell — should show venv\Scripts\python.exe
Get-Command python | Select-Object -ExpandProperty Source
```

**Fix:**
```bash
venv\Scripts\activate          # Windows PowerShell / CMD
source venv/Scripts/activate   # Git Bash
```

---

## 3. Missing `email-validator` Package

**What happened:** `No module named 'email_validator'` on startup — FastAPI's `EmailStr` type requires it but it's not installed by default.

**Fix:**
```bash
pip install "pydantic[email]"
```

---

## 4. Groq Model Decommissioned

**What happened:** Backend threw `404 model not found` for `llama3-8b-8192` — Groq removed this model from their API.

**Rule:** The `.env` file overrides code defaults (pydantic-settings reads `.env` first). Changing only `config.py` is not enough.

**Fix:**
1. Edit `.env`:  `GROQ_MODEL=llama-3.1-8b-instant`
2. **Fully restart** the backend (Ctrl+C then re-run). Auto-reload does NOT pick up `.env` changes because `@lru_cache` on settings is already cached.

**Current working model:** `llama-3.1-8b-instant`

---

## 5. Config Not Reloading After `.env` Change

**What happened:** Changed `.env`, saved, uvicorn auto-reloaded — but the old model name was still used.

**Why:** `backend/core/config.py` uses `@lru_cache` on `get_settings()`. The cached `Settings` object is never recreated on hot-reload.

**Rule:** After any `.env` change, always do a **full restart** (Ctrl+C → re-run `python -m backend.main`).

---

## 6. Docker Desktop Not Running

**What happened:** `docker-compose up -d postgres redis` → `unable to get image 'redis:7-alpine': failed to connect to the docker API`.

**Fix:** Open Docker Desktop app and wait for it to fully start (the whale icon stops animating). Then re-run the compose command.

---

## 7. Pinecone Index Didn't Exist (404 on First Run)

**What happened:** `Resource vtu-circulars not found` on every query — the Pinecone index had never been created.

**Why:** The index is created lazily by the ingestion pipeline on first scrape. If no data has been scraped yet, the index doesn't exist.

**Fix:** Trigger a scrape first:
```bash
curl http://localhost:8000/api/v1/scraper/trigger
```
The scraper auto-creates the index if missing.

---

## 8. Scraper Skipping All Circulars (`seen_circulars.json`)

**What happened:** After re-indexing attempts, the scraper logged "already seen" for all 32 circulars and indexed nothing new.

**Why:** `data/raw/seen_circulars.json` tracks which URLs were previously scraped. Once a URL is in that file, it is permanently skipped.

**Fix:** Delete the file to force a full re-scrape:
```bash
# PowerShell
Remove-Item data/raw/seen_circulars.json
```

---

## 9. Pinecone `MIN_SCORE = 0.5` Too High

**What happened:** Queries returned 0 results even though data was indexed in Pinecone — all matches had similarity scores of 0.20–0.40.

**Why:** The default threshold of 0.5 filtered everything out. Sentence-transformer cosine similarity scores for short queries against longer chunks naturally land in the 0.2–0.4 range.

**Fix:** In `backend/rag_pipeline/retriever.py`, lowered:
```python
MIN_SCORE = 0.2   # was 0.5
```

---

## 10. Tesseract OCR Not in PATH

**What happened:** `tesseract: command not found` in the terminal even after `winget install tesseract-ocr.tesseract`.

**Why:** `winget` installs to a new PATH location that only affects **new** terminals. Existing terminals don't pick it up.

**Temporary fix (current PowerShell session only):**
```powershell
$env:PATH += ";C:\Users\sriha\AppData\Local\Programs\Tesseract-OCR"
```

**Permanent fix (already applied):** Hardcoded path in `scraper/pdf_parser.py`:
```python
tesseract_path = r"C:\Users\sriha\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
```

---

## 11. Image-Only PDFs Return Empty Text

**What happened:** 7 circulars (affiliation forms, anti-ragging, grievance) had `content = ""` in the database even after OCR.

**Why:** `save_circular` in the scraper checks if a circular already exists in the DB by URL and **skips it** without updating the content field. Since these were first scraped before OCR worked, they got saved with empty content and are never re-processed.

**Rule:** OCR only helps newly scraped PDFs. To reprocess existing empty records, you must either:
- Delete those rows from the database, or
- Add an `upsert` (update if content is empty) logic to `save_circular`

These 7 are non-critical admin forms. Exam timetables and manuals are text-based and extracted fine.

---

## 12. PowerShell `curl` vs `Invoke-WebRequest` Syntax

**What happened:** `curl -H "Content-Type: application/json"` failed in PowerShell — `curl` is an alias for `Invoke-WebRequest` with different syntax.

**Fix — always use this in PowerShell:**
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/scraper/trigger" `
  -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"force": true}'
```

Or use Git Bash where real `curl` works normally.

---

## 13. `.env.production` Used as `.env`

**What happened:** Backend tried to connect to `your-db-host.example.com` — the production template had placeholder values.

**Fix:** The `.env` file must have real local values:
```
POSTGRES_HOST=localhost
DATABASE_URL=postgresql://vtu_user:vtu_password@localhost:5432/vtu_scheduler
```

---

## 14. PowerShell `rmdir` / `rm -rf` Syntax

**What happened:** `rmdir /s /q venv` is CMD syntax, not PowerShell. Throws an error.

**Fix in PowerShell:**
```powershell
Remove-Item -Recurse -Force venv
```

---

## Quick Checklist Before Every Dev Session

- [ ] Docker Desktop is running
- [ ] `venv\Scripts\activate` is active (not `.venv`)
- [ ] `python --version` shows 3.12.x
- [ ] PostgreSQL + Redis containers are up: `docker ps`
- [ ] Backend starts without errors: `python -m backend.main`
- [ ] Frontend dev server: `cd frontend && npm run dev`
