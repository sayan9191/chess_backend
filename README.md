# Chess Backend API

Production-ready FastAPI backend for a Chess Application with PostgreSQL (Supabase), JWT authentication, WebSocket gameplay, and Stockfish engine integration.

## Tech Stack

- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg
- PostgreSQL (Supabase)
- Alembic migrations
- Pydantic v2
- python-chess + Stockfish
- JWT authentication

## Project Structure

```
backend/
├── app/
│   ├── api/           # REST & WebSocket route handlers
│   ├── core/          # Config, database, security, logging
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic request/response schemas
│   ├── repositories/  # Data access layer
│   ├── services/      # Business logic
│   ├── dependencies/  # FastAPI dependency injection
│   ├── utils/         # Chess helpers, exceptions
│   ├── middleware/    # Logging, exception handlers
│   └── main.py        # Application factory
├── alembic/           # Database migrations
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## Install as a module

```bash
# Minimal production (best for free cloud hosts)
pip install -r requirements-minimal.txt

# Full local development
pip install -r requirements.txt
```

```bash
chess-backend serve          # start server
chess-backend migrate        # run DB migrations
python -m app serve          # alternative
```

See **[DEPLOY.md](./DEPLOY.md)** for Render, Railway, Docker, and platform notes.

> **Note:** Vercel and GitHub Pages cannot run this backend (no WebSocket, no long-running Python). Host the API on **Render** or **Railway** (free), and your frontend on Vercel/Pages.

## Quick Start (development)

### 1. Prerequisites

- Python 3.12+
- PostgreSQL (Supabase)
- [Stockfish](https://stockfishchess.org/download/) installed locally

```bash
# macOS
brew install stockfish
```

### 2. Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or requirements-minimal.txt for production
cp .env.example .env   # Edit with your credentials
```

### 3. Run Migrations

```bash
alembic upgrade head
```

### 4. Start Server

```bash
chess-backend serve --reload
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/auth/register` | Register with phone + name |
| POST | `/api/v1/auth/login` | Login with phone |
| GET | `/api/v1/users/me` | Current user profile |
| POST | `/api/v1/games` | Create new game |
| GET | `/api/v1/games` | List user games |
| GET | `/api/v1/games/{id}` | Get game details |
| GET | `/api/v1/games/{id}/state` | Board state |
| POST | `/api/v1/games/{id}/move` | Make move (REST) |
| POST | `/api/v1/games/{id}/resign` | Resign game |
| WS | `/api/v1/games/{id}/ws?token=JWT` | Real-time gameplay |

## WebSocket Protocol

**Connect:** `ws://localhost:8000/api/v1/games/{game_id}/ws?token=<JWT>`

**Client → Server:**

```json
{"type": "move", "payload": {"uci": "e2e4"}, "request_id": "abc-123"}
{"type": "resign", "payload": {}}
{"type": "ping", "payload": {}}
```

**Server → Client:**

```json
{"type": "connected", "payload": {"game_id": "...", "user_color": "white", "fen": "..."}}
{"type": "move_ack", "payload": {"move": {...}, "fen": "...", "is_check": false}}
{"type": "engine_move", "payload": {"move": {...}, "fen": "..."}}
{"type": "game_over", "payload": {"result": "white_wins", "reason": "checkmate"}}
{"type": "error", "payload": {"code": "INVALID_MOVE", "message": "..."}}
```

## Response Format

All REST responses use a consistent envelope:

```json
{
  "success": true,
  "message": "OK",
  "data": { }
}
```

## Environment Variables

See `.env.example` for all configuration options.

**Important:** URL-encode special characters in database passwords (`@` → `%40`, `#` → `%23`).

## Testing

```bash
pytest
```

## Architecture

Clean Architecture layers:

1. **API** — HTTP/WebSocket adapters, no business logic
2. **Services** — Business rules, chess logic, engine integration
3. **Repositories** — Database queries only
4. **Models** — SQLAlchemy ORM entities
5. **Schemas** — Pydantic validation and serialization
