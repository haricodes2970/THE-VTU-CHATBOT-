@echo off
REM ═══════════════════════════════════════════════════════════
REM  VTU Smart Scheduler — Windows Setup Script
REM  Run this once to get everything ready
REM ═══════════════════════════════════════════════════════════

echo.
echo  VTU Smart Scheduler Setup
echo  ─────────────────────────
echo.

REM ── Step 1: Check Python ─────────────────────────────────
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM ── Step 2: Check Docker ──────────────────────────────────
docker --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [WARN] Docker not found. Install Docker Desktop from https://docker.com
    echo        Skipping database startup...
) ELSE (
    echo [OK] Docker found
    echo [..] Starting PostgreSQL and Redis...
    docker-compose up -d
    echo [OK] Databases started
)

REM ── Step 3: Create virtual environment ───────────────────
IF NOT EXIST "venv" (
    echo [..] Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
) ELSE (
    echo [OK] Virtual environment exists
)

REM ── Step 4: Activate and install deps ────────────────────
echo [..] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo [OK] Dependencies installed

REM ── Step 5: Download spaCy model ─────────────────────────
echo [..] Downloading spaCy English model...
python -m spacy download en_core_web_sm --quiet
echo [OK] spaCy model ready

REM ── Step 6: Create .env ───────────────────────────────────
IF NOT EXIST ".env" (
    copy .env.example .env
    echo [OK] .env created — EDIT IT with your API keys before running the app
) ELSE (
    echo [OK] .env already exists
)

REM ── Step 7: Create data directories ──────────────────────
IF NOT EXIST "data\pdfs" mkdir data\pdfs
IF NOT EXIST "data\raw" mkdir data\raw
IF NOT EXIST "data\processed" mkdir data\processed
echo [OK] Data directories ready

echo.
echo  ─────────────────────────────────────────────────────────
echo  Setup complete!
echo.
echo  Next steps:
echo    1. Edit .env with your GROQ_API_KEY and PINECONE_API_KEY
echo    2. Run:  venv\Scripts\activate
echo    3. Run:  python -m backend.main
echo    4. Open: http://localhost:8000/docs
echo  ─────────────────────────────────────────────────────────
echo.
pause
