# Deployment Debugging — Lessons Learned

Bugs encountered while deploying to **Vercel (frontend)** + **Render (backend)**.
All were fixed and the bot is now live at `the-vtu-chatbot.vercel.app`.

---

## Bug 1 — Vercel TypeScript Build Failure: `import.meta.env` not recognised

**Error:**
```
src/api/client.ts(6,30): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
```

**Cause:**
`tsconfig.json` did not include `"types": ["vite/client"]`. Without this, TypeScript doesn't know that Vite extends `ImportMeta` with `.env`.

**Fix:**
```json
// frontend/tsconfig.json
"types": ["vite/client"]
```

**Lesson:** Any Vite project using `import.meta.env` needs `vite/client` in tsconfig types or the build will fail in CI even if it works locally.

---

## Bug 2 — Vercel Build Failure: UUID imported via ESM URL

**Error:**
```
src/hooks/useChat.ts(4,30): error TS2307: Cannot find module 'https://esm.sh/uuid@9'
```

**Cause:**
`uuid` was imported via a CDN URL (`https://esm.sh/uuid@9`) instead of as an npm package. This works in the browser at runtime but TypeScript can't resolve it at build time, and `uuid` was never in `package.json`.

**Fix:**
Replaced with the browser built-in:
```ts
const uuidv4 = () => crypto.randomUUID();
```

**Lesson:** Never import npm packages via ESM CDN URLs in a bundled Vite/TypeScript project. Always install via `npm install` or use native browser APIs where available.

---

## Bug 3 — Render Crash: `email-validator` not installed

**Error:**
```
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

**Cause:**
`notifications.py` uses `EmailStr` from pydantic, which requires the `email-validator` package. We had `pydantic` in `requirements.txt` but not `pydantic[email]`.

**Fix:**
```
# requirements.txt
pydantic[email]>=2.7.1
```

**Lesson:** `pydantic[email]` is a separate optional dependency. Any model using `EmailStr` will crash at import time without it — not at runtime, making it easy to miss locally if you never exercise that route.

---

## Bug 4 — Render OOM: Out of Memory (512MB limit exceeded)

**Error:**
```
==> Out of memory (used over 512Mi)
Child process died repeatedly
```

**Cause:**
`sentence-transformers` depends on `torch`. Even on CPU, importing `torch` at Python startup loads ~300–400MB into RAM. Combined with spaCy, LangChain, FastAPI, and the rest of the stack, this blew past Render free tier's 512MB limit before serving a single request.

The intermediate attempt to install CPU-only torch (`--index-url https://download.pytorch.org/whl/cpu`) reduced download size but didn't solve the runtime memory issue — torch still consumes the same RAM regardless of CPU/GPU variant.

**Fix:**
Replaced `sentence-transformers` with `fastembed`:
- `fastembed` uses ONNX Runtime instead of PyTorch
- Same `all-MiniLM-L6-v2` model, same 384-dim output
- Memory footprint ~50MB vs ~400MB
- Pinecone index completely unchanged — zero re-indexing needed

```
# requirements.txt
fastembed>=0.3.0   # replaces sentence-transformers
```

```python
# ai/embeddings/embedding_generator.py
from fastembed import TextEmbedding
model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
embeddings = list(model.embed([text]))[0].tolist()
```

**Lesson:** `sentence-transformers` is fine locally but completely unsuitable for free-tier cloud deployments. Always check the runtime memory cost of ML libraries, not just download size. ONNX-based alternatives (fastembed, optimum) are dramatically lighter.

---

## Bug 5 — Render: Two Workers Doubled Memory Usage

**Cause:**
`Dockerfile` had `--workers 2` in the uvicorn start command. Each worker is a separate Python process — so 2 workers = 2× memory. On a 512MB instance this is fatal.

**Fix:**
```dockerfile
# Before
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# After
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Lesson:** Never use multiple uvicorn workers on free-tier deployments. Single worker is fine for low-traffic apps.

---

## Bug 6 — CORS Blocking Vercel Frontend

**Cause:**
CORS origins were hardcoded in `backend/main.py`:
```python
allow_origins=["http://localhost:3000", "http://localhost:5173"]
```
The Vercel frontend (`https://the-vtu-chatbot.vercel.app`) was not in the list, so all API calls were blocked by the browser.

**Fix:**
Made CORS configurable via env var:
```python
# backend/core/config.py
allowed_origins: str = "http://localhost:3000,http://localhost:5173"

# backend/main.py
allow_origins=[o.strip() for o in settings.allowed_origins.split(",")]
```

Then in Render environment:
```
ALLOWED_ORIGINS=https://the-vtu-chatbot.vercel.app
```

**Lesson:** Never hardcode CORS origins. Always read from an env var so production domains can be added without code changes.

---

## Bug 7 — Frontend Showing "Not Found" After Deploy

**Cause:**
`VITE_API_URL` in Vercel was either missing or pointing to the wrong Render URL. The frontend was hitting an incorrect API endpoint.

**Fix:**
In Vercel → Settings → Environment Variables:
```
VITE_API_URL=https://the-vtu-chatbot.onrender.com/api/v1
```

**Lesson:** After every backend URL change, update the frontend env var in Vercel and redeploy. Vercel bakes `VITE_*` variables into the static bundle at build time — changing them requires a redeploy.

---

## Summary Table

| # | Where | Error | Root Cause | Fix |
|---|---|---|---|---|
| 1 | Vercel | `import.meta.env` TS error | Missing `vite/client` types | Add to tsconfig |
| 2 | Vercel | UUID ESM URL not resolved | CDN import in bundled project | Use `crypto.randomUUID()` |
| 3 | Render | `email-validator` missing | `pydantic[email]` not in requirements | Add `pydantic[email]` |
| 4 | Render | OOM 512MB | `torch` import ~400MB RAM | Replace with `fastembed` (ONNX) |
| 5 | Render | OOM 512MB | 2 uvicorn workers = 2× RAM | Drop to 1 worker |
| 6 | Browser | CORS blocked | Hardcoded localhost origins | Read from `ALLOWED_ORIGINS` env var |
| 7 | Frontend | "Not Found" | Wrong `VITE_API_URL` in Vercel | Set correct Render URL |
