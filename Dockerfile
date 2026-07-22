FROM python:3.12-slim

WORKDIR /app

# Minimal deps only — no Stockfish binary in container by default
COPY pyproject.toml README.md requirements-minimal.txt ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir -r requirements-minimal.txt

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "chess-backend migrate && chess-backend serve --host 0.0.0.0 --port ${PORT}"]
