# StatShift

Local fantasy football statistics assistant. Query seeded NFL/fantasy data through a read-only API, or chat with a local LLM for open-ended analysis.

**Streamlit** → **RAG** → **FastAPI (read-only)** → **SQLite**  
**RAG** → **Ollama** → **Gemma**

Factual questions (stats, matchups, injuries) are answered from the database. Conversational prompts go to Gemma.

## Prerequisites

- **Docker (recommended):** Docker Desktop or Docker Engine with Compose v2
- **Or local Python 3.11+** and [Ollama](https://ollama.com) with Gemma (`ollama pull gemma2:2b`)

## Run with Docker

```bash
docker compose up --build
```

First startup pulls `gemma2:2b` into the Ollama container (can take a few minutes). Then open:

**http://localhost:8501**

Optional: API docs at http://localhost:8000/docs

```bash
# Stop
docker compose down

# Reset DB + models (re-seeds fantasy football sample data)
docker compose down -v
```

Services:

| Service | Role | Host port |
|---------|------|-----------|
| `ui` | Streamlit (your browser connects here) | 8501 |
| `api` | FastAPI read-only API | 8000 |
| `ollama` | Gemma inference | 11434 |

Inside the Compose network, the UI talks to `http://api:8000` and `http://ollama:11434`.

## Local setup (without Docker)

```bash
cd StatShift
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
```

## Run (three terminals)

```bash
# 1 — API
uvicorn api.main:app --reload

# 2 — UI
streamlit run app/streamlit_app.py

# 3 — Ollama (if not already running)
ollama serve
```

Or use helper scripts:

```bash
chmod +x scripts/run_api.sh scripts/run_ui.sh
./scripts/run_api.sh
./scripts/run_ui.sh
```

Open http://127.0.0.1:8501 and ask about players, weekly matchups, injuries, or PPR scoring from the seeded data.

If you previously ran an older build with different seed data, delete `data/statshift.db` or run `docker compose down -v` before re-initializing.

## Tests

```bash
python -m unittest discover -s tests -v
```

CI runs the same suite on pull requests and pushes to `main`.

## Configuration

Optional `.env` overrides:

```env
OLLAMA_MODEL=gemma2:2b
OLLAMA_BASE_URL=http://127.0.0.1:11434
API_BASE_URL=http://127.0.0.1:8000
```

## API (read-only)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service + DB check |
| `GET /documents` | List documents |
| `GET /documents/{id}` | Single document |
| `GET /search?q=...` | FTS search for RAG |
| `GET /categories` | Distinct categories |

`POST`, `PUT`, `PATCH`, and `DELETE` return **405** — writes are blocked at the API layer; SQLite is opened in read-only mode for queries.

## Sample data categories

| Category | Examples |
|----------|----------|
| `player` | McCaffrey workload, Chase targets, Kelce red-zone usage |
| `team` | Bills pace and scoring |
| `matchup` | Week 12 RB defensive matchups |
| `injury` | Week 15 practice reports |
| `league` | PPR scoring, passing leaders |
