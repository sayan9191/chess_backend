# Deployment Guide

## Important: platform fit

| Platform | Backend support | WebSocket | Notes |
|----------|------------------|-----------|-------|
| **Render** (free) | Yes | Yes | Recommended |
| **Railway** (free tier) | Yes | Yes | Recommended |
| **Fly.io** | Yes | Yes | Good for Docker deploy |
| **Vercel** | Serverless only | No | REST only; not suitable for chess WebSocket |
| **GitHub Pages** | No | No | Static frontend only — host API elsewhere |

This backend needs a **long-running Python process** and **WebSockets** for live games. Use Render or Railway, not Vercel/Pages.

---

## Install as a Python module

From the `backend/` directory:

```bash
# Minimal production (smallest footprint)
pip install -r requirements-minimal.txt

# Full local development
pip install -r requirements.txt
```

Or directly:

```bash
pip install .                          # core only (~8 deps)
pip install ".[server,migrate]"        # + fast uvicorn + migrations
pip install ".[all]"                   # everything including Stockfish wrapper
```

### CLI commands

```bash
chess-backend serve              # start API (uses PORT env on cloud)
chess-backend serve --reload     # local dev with hot reload
chess-backend migrate            # run Alembic migrations
chess-backend version            # print version
python -m app serve              # alternative entry
```

---

## Minimal dependencies (production)

Core install avoids heavy packages:

| Removed from core | Why |
|-------------------|-----|
| `stockfish` | Binary not available on free hosts; built-in random-move fallback |
| `passlib` / `bcrypt` | Phone auth uses JWT only, no passwords |
| `python-jose[cryptography]` | Replaced with lightweight `PyJWT` |
| `httpx` | Not required at runtime |
| `alembic` / `psycopg` | Optional `[migrate]` extra for build step only |
| `uvicorn[standard]` | Optional `[server]` extra (uvloop/httptools) |

---

## Deploy to Render (recommended, free)

1. Push repo to GitHub
2. Create **New Web Service** on [Render](https://render.com)
3. Connect repo, set root directory to `backend`
4. Render reads `render.yaml` automatically, or set manually:
   - **Build:** `pip install -r requirements-minimal.txt && pip install 'chess-backend[migrate]' && chess-backend migrate`
   - **Start:** `chess-backend serve --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `DATABASE_URL` — Supabase connection string (URL-encode password)
   - `JWT_SECRET_KEY` — random 32+ char string
   - `CORS_ORIGINS` — your frontend URL

---

## Deploy to Railway

1. Connect GitHub repo
2. Set root directory: `backend`
3. Railway detects `Procfile` or set start command:
   ```
   chess-backend serve --host 0.0.0.0 --port $PORT
   ```
4. Add env vars (same as Render)

---

## Docker

```bash
cd backend
docker build -t chess-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e JWT_SECRET_KEY="your-secret" \
  chess-backend
```

---

## Environment variables (required)

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/postgres
JWT_SECRET_KEY=your-secure-random-string-min-32-chars
CORS_ORIGINS=https://your-frontend.vercel.app
```

Optional:

```env
ENVIRONMENT=production
LOG_FORMAT=json
STOCKFISH_PATH=stockfish   # only if binary is installed on the host
```

---

## Frontend on Vercel / GitHub Pages

Host your **React/Next/static frontend** on Vercel or GitHub Pages. Point API calls to your Render/Railway backend URL:

```
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

WebSocket URL:

```
wss://your-backend.onrender.com/api/v1/games/{id}/ws?token=JWT
```
