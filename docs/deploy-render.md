# Deploy Backend to Render.com

## Prerequisites
- Render account (free tier available)
- GitHub repo connected to Render

## Steps

### 1. Create a Web Service
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo `haricodes2970/THE-VTU-CHATBOT-`
3. Set:
   - **Root Directory**: `.` (project root)
   - **Build Command**: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Python Version**: 3.11

### 2. Add Environment Variables
In Render dashboard → Environment, add all variables from `.env.production`:
- `APP_ENV=production`
- `DATABASE_URL` (use Render PostgreSQL URL)
- `GROQ_API_KEY`
- `PINECONE_API_KEY`
- `SECRET_KEY` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
- All SMTP/Telegram vars

### 3. Create PostgreSQL Database
1. Render → New → PostgreSQL
2. Copy the **Internal Database URL** to `DATABASE_URL` env var

### 4. Run Migrations
After first deploy, open Render Shell:
```bash
alembic upgrade head
python scripts/seed_db.py
```

### 5. Verify
Visit `https://your-app.onrender.com/docs` — you should see the Swagger UI.
